import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.collectors.tushare_cn_stock.stock_basic import CollectionError
from quantstone_data.main import create_app


def dataset_payload(dataset_id: str = "demo.cn.stock.daily") -> dict:
    provider, region, instrument, dataset_name = dataset_id.split(".")
    return {
        "id": dataset_id,
        "provider": provider,
        "region": region,
        "instrument": instrument,
        "dataset_name": dataset_name,
        "market": None,
        "display_name": "测试日线",
        "description": "采集任务测试使用",
        "primary_key": ["trade_date", "symbol"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日期",
            },
            {
                "name": "symbol",
                "data_type": "string",
                "nullable": False,
                "description": "证券代码",
            },
        ],
    }


def trade_calendar_payload() -> dict:
    return {
        "id": "tushare.cn.stock.trade_cal",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "trade_cal",
        "market": None,
        "display_name": "A股交易日历",
        "description": "TuShare trade_cal 上交所交易日历",
        "collection_bindings": [{
            "purpose": "initial",
            "collector_key": "tushare_cn_stock",
            "operation": "trade_cal_initial",
        }],
        "storage_policy": {
            "logical_partition_field": None,
            "calendar_dataset_id": None,
            "layout": "snapshot",
            "write_strategy": "replace_snapshot",
            "compaction": None,
        },
        "primary_key": ["exchange", "cal_date"],
        "time_field": "cal_date",
        "fields": [
            {"name": "exchange", "data_type": "string", "nullable": False, "description": "交易所"},
            {"name": "cal_date", "data_type": "date", "nullable": False, "description": "日历日期"},
            {"name": "is_open", "data_type": "int32", "nullable": False, "description": "是否交易"},
            {
                "name": "pretrade_date",
                "data_type": "date",
                "nullable": True,
                "description": "上一交易日",
            },
        ],
    }


def create_client(tmp_path: Path) -> TestClient:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    return TestClient(app)


def create_dataset(client: TestClient, *, activate: bool = True) -> str:
    dataset_id = dataset_payload()["id"]
    response = client.post("/api/v1/datasets", json=dataset_payload())
    assert response.status_code == 201
    if activate:
        assert client.post(f"/api/v1/datasets/{dataset_id}/activate").status_code == 200
    return dataset_id


def test_date_partition_requires_calendar_dataset_id(tmp_path: Path) -> None:
    payload = dataset_payload()
    payload["storage_policy"] = {
        "logical_partition_field": "trade_date",
        "layout": "daily",
        "write_strategy": "replace_partition",
        "compaction": None,
    }

    with create_client(tmp_path) as client:
        response = client.post("/api/v1/datasets", json=payload)

    assert response.status_code == 422
    assert "calendar_dataset_id" in response.text


def test_date_partition_prompts_to_create_missing_calendar(tmp_path: Path) -> None:
    payload = dataset_payload()
    payload["storage_policy"] = {
        "logical_partition_field": "trade_date",
        "calendar_dataset_id": "tushare.cn.stock.trade_cal",
        "layout": "daily",
        "write_strategy": "replace_partition",
        "compaction": None,
    }

    with create_client(tmp_path) as client:
        assert client.post("/api/v1/datasets", json=payload).status_code == 201
        response = client.post(f"/api/v1/datasets/{payload['id']}/activate")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "请先创建交易日历数据集：tushare.cn.stock.trade_cal"
    )


def test_only_active_datasets_can_create_collection_jobs(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client, activate=False)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "incremental",
                "input_method": "collector",
                "collector_key": "mock",
            },
        )

    assert response.status_code == 409


def test_initial_collection_can_be_created_without_date_range(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "initial",
                "input_method": "file_import",
            },
        )

    assert response.status_code == 201
    assert response.json()["start_date"] is None
    assert response.json()["end_date"] is None


def test_collector_job_requires_a_binding_for_its_purpose(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "incremental",
                "input_method": "collector",
                "collector_key": "mock",
            },
        )

        assert response.status_code == 409

    assert "does not support this collection purpose" in response.text


def test_manual_file_import_is_staged_with_integrity_metadata(tmp_path: Path) -> None:
    content = b"trade_date,symbol\n2026-11-17,600000.SH\n"
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "initial",
                "input_method": "file_import",
                "start_date": "2026-11-17",
                "end_date": "2026-11-17",
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "awaiting_file"

        staged = client.post(
            f"/api/v1/collection-jobs/{created.json()['id']}/file",
            files={"file": ("daily.csv", content, "text/csv")},
        )
        assert staged.status_code == 200
        body = staged.json()
        assert body["status"] == "staged"
        assert body["source_file_name"] == "daily.csv"
        assert body["source_size_bytes"] == len(content)
        assert body["source_sha256"] == hashlib.sha256(content).hexdigest()

        staged_file = tmp_path / "data" / body["staged_path"]
        assert staged_file.read_bytes() == content

        duplicate = client.post(
            f"/api/v1/collection-jobs/{created.json()['id']}/file",
            files={"file": ("daily.csv", content, "text/csv")},
        )

    assert duplicate.status_code == 409


def test_stock_basic_collector_stages_and_reviews_data(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "id": "tushare.cn.stock.stock_basic",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "stock_basic",
        "market": None,
        "display_name": "A股股票列表",
        "description": "TuShare 股票基础信息",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare_cn_stock",
                "operation": "stock_list_initial",
            },
            {
                "purpose": "incremental",
                "collector_key": "tushare_cn_stock",
                "operation": "stock_list_incremental",
            },
        ],
        "primary_key": ["ts_code"],
        "time_field": None,
        "fields": [
            {
                "name": "ts_code",
                "data_type": "string",
                "nullable": False,
                "description": "TS代码",
            },
            {
                "name": "name",
                "data_type": "string",
                "nullable": False,
                "description": "股票名称",
            },
            {
                "name": "list_status",
                "data_type": "string",
                "nullable": False,
                "description": "上市状态",
            },
        ],
    }

    def fake_call(_token: str, list_status: str, _fields: list[str]) -> list[dict]:
        if list_status != "L":
            return []
        return [{"ts_code": "000001.SZ", "name": "平安银行", "list_status": "L"}]

    monkeypatch.setattr(
        "quantstone_data.collectors.tushare_cn_stock.stock_basic.call_api",
        fake_call,
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    with create_client(tmp_path) as client:
        created_dataset = client.post("/api/v1/datasets", json=payload)
        assert created_dataset.status_code == 201
        activated = client.post("/api/v1/datasets/tushare.cn.stock.stock_basic/activate")
        assert activated.status_code == 200
        created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": "tushare.cn.stock.stock_basic",
                "operation": "initial",
                "input_method": "collector",
            },
        )
        assert created.status_code == 201
        assert created.json()["collector_key"] == "tushare_cn_stock"
        assert created.json()["collector_operation"] == "stock_list_initial"

        executed = client.post(f"/api/v1/collection-jobs/{created.json()['id']}/execute")
        review_response = client.get(f"/api/v1/collection-jobs/{created.json()['id']}/review")

        def failing_call(_token: str, _list_status: str, _fields: list[str]) -> list[dict]:
            raise CollectionError("供应商暂时不可用")

        monkeypatch.setattr(
            "quantstone_data.collectors.tushare_cn_stock.stock_basic.call_api",
            failing_call,
        )
        failed_created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": "tushare.cn.stock.stock_basic",
                "operation": "incremental",
                "input_method": "collector",
            },
        )
        failed_executed = client.post(
            f"/api/v1/collection-jobs/{failed_created.json()['id']}/execute"
        )
        failed_record = client.get(
            f"/api/v1/collection-jobs/{failed_created.json()['id']}"
        )

    assert executed.status_code == 200
    body = executed.json()
    assert body["status"] == "review_passed"
    assert review_response.status_code == 200
    assert review_response.json()["row_count"] == 1
    staged_file = tmp_path / "data" / body["staged_path"]
    assert staged_file.suffix == ".parquet"
    report = staged_file.with_name("review.json").read_text(encoding="utf-8")
    assert '"passed": true' in report
    assert failed_executed.status_code == 502
    assert failed_record.json()["status"] == "failed"
    assert failed_record.json()["error"] == "供应商暂时不可用"


def test_daily_collection_publishes_parquet_and_catalog(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "id": "tushare.cn.stock.daily",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "daily",
        "market": None,
        "display_name": "A股日K",
        "description": "TuShare daily 接口",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare_cn_stock",
                "operation": "daily_initial",
            }
        ],
        "storage_policy": {
            "logical_partition_field": "trade_date",
            "calendar_dataset_id": "tushare.cn.stock.trade_cal",
            "layout": "yearly_with_delta",
            "write_strategy": "replace_partition",
            "compaction": "yearly",
        },
        "primary_key": ["ts_code", "trade_date"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "ts_code",
                "data_type": "string",
                "nullable": False,
                "description": "TS代码",
            },
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日期",
            },
            {
                "name": "close",
                "data_type": "float64",
                "nullable": False,
                "description": "收盘价",
            },
        ],
    }

    collected_dates: list[str] = []

    def fake_daily(_token: str, trade_date: str, _fields: list[str]) -> list[dict]:
        collected_dates.append(trade_date)
        return [
            {"ts_code": "000001.SZ", "trade_date": trade_date, "close": 10.5},
            {"ts_code": "600000.SH", "trade_date": trade_date, "close": 12.3},
        ]

    def fake_trade_cal(_token, _start_date, _end_date, _fields):
        return [
            {
                "exchange": "SSE",
                "cal_date": "20261117",
                "is_open": 0,
                "pretrade_date": "20261116",
            },
            {
                "exchange": "SSE",
                "cal_date": "20261118",
                "is_open": 1,
                "pretrade_date": "20261116",
            },
        ]

    monkeypatch.setattr(
        "quantstone_data.collectors.tushare_cn_stock.daily._call_daily",
        fake_daily,
    )
    monkeypatch.setattr(
        "quantstone_data.collectors.tushare_cn_stock.trade_cal._call_trade_cal",
        fake_trade_cal,
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    with create_client(tmp_path) as client:
        assert client.post("/api/v1/datasets", json=trade_calendar_payload()).status_code == 201
        activated = client.post("/api/v1/datasets/tushare.cn.stock.trade_cal/activate")
        assert activated.status_code == 200
        calendar_job = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": "tushare.cn.stock.trade_cal",
                "operation": "initial",
                "input_method": "collector",
                "parameters": {"start_date": "2026-11-17", "end_date": "2026-11-18"},
            },
        )
        calendar_executed = client.post(
            f"/api/v1/collection-jobs/{calendar_job.json()['id']}/execute"
        )
        assert calendar_executed.status_code == 200
        assert client.post("/api/v1/datasets", json=payload).status_code == 201
        assert client.post("/api/v1/datasets/tushare.cn.stock.daily/activate").status_code == 200
        created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": "tushare.cn.stock.daily",
                "operation": "initial",
                "input_method": "collector",
                "parameters": {
                    "start_date": "2026-11-17",
                    "end_date": "2026-11-18",
                },
            },
        )
        assert created.json()["start_date"] == "2026-11-17"
        assert created.json()["end_date"] == "2026-11-18"
        executed = client.post(f"/api/v1/collection-jobs/{created.json()['id']}/execute")
        runs = client.get(f"/api/v1/collection-jobs/{created.json()['id']}/runs")
        catalog = client.get("/api/v1/catalog/partitions?dataset_id=tushare.cn.stock.daily")
        storage = client.get("/api/v1/storage/overview")

    assert executed.status_code == 200
    assert executed.json()["status"] == "succeeded"
    assert runs.json()[0]["row_count"] == 2
    assert runs.json()[0]["status"] == "succeeded"
    assert collected_dates == ["20261118"]
    assert catalog.json()[0]["partition_key"] == "2026-11-18"
    assert storage.status_code == 200
    assert storage.json()["published_files"] == 2
    assert storage.json()["published_partitions"] == 2
    assert storage.json()["published_rows"] == 4
    assert storage.json()["missing_files"] == 0
    published = tmp_path / "data" / catalog.json()[0]["file_path"]
    assert published.suffix == ".parquet"
    assert published.is_file()


def test_trade_calendar_publishes_snapshot(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "id": "tushare.cn.stock.trade_cal",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "trade_cal",
        "market": None,
        "display_name": "A股交易日历",
        "description": "TuShare trade_cal 上交所交易日历",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare_cn_stock",
                "operation": "trade_cal_initial",
            }
        ],
        "storage_policy": {
            "logical_partition_field": None,
            "layout": "snapshot",
            "write_strategy": "replace_snapshot",
            "compaction": None,
        },
        "primary_key": ["exchange", "cal_date"],
        "time_field": "cal_date",
        "fields": [
            {"name": "exchange", "data_type": "string", "nullable": False, "description": "交易所"},
            {"name": "cal_date", "data_type": "date", "nullable": False, "description": "日历日期"},
            {"name": "is_open", "data_type": "int32", "nullable": False, "description": "是否交易"},
            {
                "name": "pretrade_date",
                "data_type": "date",
                "nullable": True,
                "description": "上一交易日",
            },
        ],
    }

    def fake_trade_cal(_token, start_date, _end_date, _fields):
        return [
            {
                "exchange": "SSE",
                "cal_date": start_date.strftime("%Y%m%d"),
                "is_open": 1,
                "pretrade_date": None,
            }
        ]

    monkeypatch.setattr(
        "quantstone_data.collectors.tushare_cn_stock.trade_cal._call_trade_cal",
        fake_trade_cal,
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    with create_client(tmp_path) as client:
        assert client.post("/api/v1/datasets", json=payload).status_code == 201
        assert (
            client.post("/api/v1/datasets/tushare.cn.stock.trade_cal/activate").status_code == 200
        )
        created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": "tushare.cn.stock.trade_cal",
                "operation": "initial",
                "input_method": "collector",
                "parameters": {"start_date": "2026-01-01", "end_date": "2026-12-31"},
            },
        )
        executed = client.post(f"/api/v1/collection-jobs/{created.json()['id']}/execute")
        catalog = client.get("/api/v1/catalog/partitions?dataset_id=tushare.cn.stock.trade_cal")

    assert executed.status_code == 200
    assert executed.json()["status"] == "succeeded"
    assert catalog.json()[0]["partition_key"] == "snapshot"
    assert (tmp_path / "data" / catalog.json()[0]["file_path"]).is_file()
