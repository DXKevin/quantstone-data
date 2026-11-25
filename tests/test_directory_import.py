from __future__ import annotations

import sqlite3
import time
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from quantstone_data.field_types import arrow_type
from quantstone_data.main import create_app

ORDER_ID = "tb_xxlpd.cn.stock.l2_order.sz"
TRADE_ID = "zhongtai.cn.stock.l2_trade.sz"


def _write_order_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            pa.field("symbol", arrow_type("string"), nullable=False),
            pa.field("exchange_code", arrow_type("string"), nullable=False),
            pa.field("trade_date", arrow_type("date"), nullable=False),
            pa.field("event_time", arrow_type("int32"), nullable=False),
            pa.field("channel_code", arrow_type("string"), nullable=False),
            pa.field("exchange_order_no", arrow_type("int64"), nullable=False),
            pa.field("order_type", arrow_type("string"), nullable=False),
            pa.field("side", arrow_type("string"), nullable=False),
            pa.field("price", arrow_type("int64"), nullable=False),
            pa.field("volume", arrow_type("int64"), nullable=False),
        ]
    )
    table = pa.Table.from_pylist(
        [
            {
                "symbol": "000001.SZ",
                "exchange_code": "000001",
                "trade_date": date(2026, 11, 18),
                "event_time": 93000000,
                "channel_code": "0",
                "exchange_order_no": 1,
                "order_type": "0",
                "side": "B",
                "price": 120000,
                "volume": 100,
            },
            {
                "symbol": "000001.SZ",
                "exchange_code": "000001",
                "trade_date": date(2026, 11, 18),
                "event_time": 93000100,
                "channel_code": "0",
                "exchange_order_no": 2,
                "order_type": "0",
                "side": "S",
                "price": 120100,
                "volume": 200,
            },
        ],
        schema=schema,
    )
    pq.write_table(table, path, compression="zstd")


def _wait_status(client: TestClient, job_id: str, expected: set[str], timeout: float = 10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in expected:
            return body
        time.sleep(0.05)
    raise AssertionError(f"import job did not reach {expected}: {body}")


def test_directory_import_scans_reviews_and_publishes(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    with TestClient(app) as client:
        presets = {
            item["contract"]["id"]: item["contract"]
            for item in client.get("/api/v1/dataset-presets").json()
        }
        calendar = presets["tushare.cn.stock.trade_cal"]
        assert client.post("/api/v1/datasets", json=calendar).status_code == 201
        assert (
            client.post("/api/v1/datasets/tushare.cn.stock.trade_cal/activate").status_code
            == 200
        )
        order = presets[ORDER_ID]
        assert client.post("/api/v1/datasets", json=order).status_code == 201
        assert client.post(f"/api/v1/datasets/{ORDER_ID}/activate").status_code == 200

        source = (
            tmp_path
            / "data"
            / "imports"
            / "wind_l2"
            / "sz"
            / "20261118"
            / "l2_order.parquet"
        )
        _write_order_file(source)

        created = client.post(
            "/api/v1/import-jobs",
            json={
                "dataset_id": ORDER_ID,
                "scanner_key": "l2_sz_baidu",
                "operation": "import_order",
                "purpose": "repair",
                "source_root": str(source.parent.parent),
            },
        )
        assert created.status_code == 202, created.text
        job_id = created.json()["id"]
        collection_job_id = created.json()["collection_job_id"]
        assert collection_job_id
        ready = _wait_status(client, job_id, {"review_ready"})
        assert ready["summary"]["ready"] == 1
        pending_collection = client.get(
            f"/api/v1/collection-jobs/{collection_job_id}"
        )
        assert pending_collection.status_code == 200
        assert pending_collection.json()["status"] == "review_ready"

        manifest = client.get(f"/api/v1/import-jobs/{job_id}/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["files"][0]["partition_key"] == "2026-11-18"

        executed = client.post(f"/api/v1/import-jobs/{job_id}/execute")
        assert executed.status_code == 200
        completed = _wait_status(client, job_id, {"succeeded", "failed"})
        assert completed["status"] == "succeeded", completed["error"]
        assert completed["collection_job_id"] == collection_job_id

        partitions = client.get(
            f"/api/v1/catalog/partitions?dataset_id={ORDER_ID}"
        )
        assert partitions.status_code == 200
        assert len(partitions.json()) == 1
        assert partitions.json()[0]["row_count"] == 2
        assert partitions.json()[0]["partition_key"] == "2026-11-18"
        assert partitions.json()[0]["sha256"] == ""
        assert not source.exists()

        collection_jobs = client.get("/api/v1/collection-jobs")
        assert collection_jobs.status_code == 200
        assert any(
            item["input_method"] == "directory_import" and item["operation"] == "repair"
            for item in collection_jobs.json()["items"]
        )
        imported_job = next(
            item
            for item in collection_jobs.json()["items"]
            if item["input_method"] == "directory_import"
        )
        review = client.get(f"/api/v1/collection-jobs/{imported_job['id']}/review")
        assert review.status_code == 200
        assert review.json()["passed"] is True
        assert review.json()["row_count"] == 2
        assert review.json()["runs"][0]["partition_key"] == "2026-11-18"


def test_legacy_l2_partition_keys_are_migrated_to_iso_dates(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    data_root = tmp_path / "data"
    app = create_app(database_url, data_root=data_root)
    with TestClient(app) as client:
        presets = {
            item["contract"]["id"]: item["contract"]
            for item in client.get("/api/v1/dataset-presets").json()
        }
        calendar = presets["tushare.cn.stock.trade_cal"]
        assert client.post("/api/v1/datasets", json=calendar).status_code == 201
        assert (
            client.post("/api/v1/datasets/tushare.cn.stock.trade_cal/activate").status_code
            == 200
        )
        assert client.post("/api/v1/datasets", json=presets[ORDER_ID]).status_code == 201
        assert client.post(f"/api/v1/datasets/{ORDER_ID}/activate").status_code == 200
        source = data_root / "imports" / "wind_l2" / "sz" / "20261118" / "l2_order.parquet"
        _write_order_file(source)
        created = client.post(
            "/api/v1/import-jobs",
            json={
                "dataset_id": ORDER_ID,
                "scanner_key": "l2_sz_baidu",
                "operation": "import_order",
                "source_root": str(source.parent.parent),
            },
        )
        ready = _wait_status(client, created.json()["id"], {"review_ready"})
        assert client.post(f"/api/v1/import-jobs/{ready['id']}/execute").status_code == 200
        assert _wait_status(client, ready["id"], {"succeeded"})["status"] == "succeeded"

    with sqlite3.connect(database_path) as database:
        current_path = database.execute(
            "SELECT path FROM catalog_files WHERE dataset_id = ?", (ORDER_ID,)
        ).fetchone()[0]
        compact_path = current_path.replace("/2026-11-18/", "/20261118/")
        current_file = data_root / current_path
        compact_directory = current_file.parent.parent / "20261118"
        current_file.parent.rename(compact_directory)
        database.execute(
            "UPDATE catalog_files SET path = ? WHERE dataset_id = ?",
            (compact_path, ORDER_ID),
        )
        database.execute(
            "UPDATE catalog_partitions SET partition_key = '20261118', file_path = ? "
            "WHERE dataset_id = ?",
            (compact_path, ORDER_ID),
        )
        database.execute(
            "UPDATE collection_runs SET partition_key = '20261118', published_path = ? "
            "WHERE job_id IN "
            "(SELECT id FROM collection_jobs WHERE dataset_id = ?)",
            (compact_path, ORDER_ID),
        )

    with TestClient(create_app(database_url, data_root=data_root)) as restarted:
        partitions = restarted.get(f"/api/v1/catalog/partitions?dataset_id={ORDER_ID}")
        assert partitions.json()[0]["partition_key"] == "2026-11-18"
        migrated_path = partitions.json()[0]["file_path"]
        assert "/2026-11-18/" in migrated_path
        assert (data_root / migrated_path).is_file()
        assert not compact_directory.exists()

    with sqlite3.connect(database_path) as database:
        run_key = database.execute(
            "SELECT r.partition_key FROM collection_runs r "
            "JOIN collection_jobs j ON j.id = r.job_id WHERE j.dataset_id = ?",
            (ORDER_ID,),
        ).fetchone()
        assert run_key == ("2026-11-18",)
        file_path = database.execute(
            "SELECT path FROM catalog_files WHERE dataset_id = ?", (ORDER_ID,)
        ).fetchone()[0]
        run_path = database.execute(
            "SELECT r.published_path FROM collection_runs r "
            "JOIN collection_jobs j ON j.id = r.job_id WHERE j.dataset_id = ?",
            (ORDER_ID,),
        ).fetchone()[0]
        assert file_path == migrated_path
        assert run_path == migrated_path

def _write_zhongtai_trade_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            pa.field("symbol", arrow_type("string"), nullable=False),
            pa.field("exchange_code", arrow_type("string"), nullable=False),
            pa.field("trade_date", arrow_type("date"), nullable=False),
            pa.field("event_time", arrow_type("int32"), nullable=False),
            pa.field("trade_no", arrow_type("int64"), nullable=False),
            pa.field("trade_code", arrow_type("string"), nullable=True),
            pa.field("order_code", arrow_type("string"), nullable=True),
            pa.field("side", arrow_type("string"), nullable=True),
            pa.field("price", arrow_type("int64"), nullable=False),
            pa.field("volume", arrow_type("int64"), nullable=False),
            pa.field("ask_order_no", arrow_type("int64"), nullable=False),
            pa.field("bid_order_no", arrow_type("int64"), nullable=False),
        ]
    )
    rows = [
        {
            "symbol": "000001.SZ",
            "exchange_code": "000001",
            "trade_date": date(2026, 3, 23),
            "event_time": 93000000,
            "trade_no": 10,
            "trade_code": "C",
            "order_code": "0",
            "side": None,
            "price": 0,
            "volume": 100,
            "ask_order_no": 0,
            "bid_order_no": 9,
        },
        {
            "symbol": "000001.SZ",
            "exchange_code": "000001",
            "trade_date": date(2026, 3, 23),
            "event_time": 93000100,
            "trade_no": 11,
            "trade_code": "0",
            "order_code": "0",
            "side": "B",
            "price": 120000,
            "volume": 200,
            "ask_order_no": 8,
            "bid_order_no": 12,
        },
    ]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression="zstd")


def test_zhongtai_trade_directory_import(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    with TestClient(app) as client:
        presets = {
            item["contract"]["id"]: item["contract"]
            for item in client.get("/api/v1/dataset-presets").json()
        }
        calendar = presets["tushare.cn.stock.trade_cal"]
        assert client.post("/api/v1/datasets", json=calendar).status_code == 201
        assert (
            client.post("/api/v1/datasets/tushare.cn.stock.trade_cal/activate").status_code
            == 200
        )
        trade = presets[TRADE_ID]
        assert client.post("/api/v1/datasets", json=trade).status_code == 201
        assert client.post(f"/api/v1/datasets/{TRADE_ID}/activate").status_code == 200

        source = (
            tmp_path
            / "data"
            / "imports"
            / "zhongtai_l2"
            / "sz"
            / "20260323"
            / "l2_trade.parquet"
        )
        _write_zhongtai_trade_file(source)

        created = client.post(
            "/api/v1/import-jobs",
            json={
                "dataset_id": TRADE_ID,
                "scanner_key": "zhongtai_l2_sz",
                "operation": "import_trade",
                "source_root": str(source.parent.parent),
                "transfer_mode": "copy",
            },
        )
        assert created.status_code == 202, created.text
        job_id = created.json()["id"]
        ready = _wait_status(client, job_id, {"review_ready"})
        assert ready["summary"]["ready"] == 1

        executed = client.post(f"/api/v1/import-jobs/{job_id}/execute")
        assert executed.status_code == 200
        completed = _wait_status(client, job_id, {"succeeded", "failed"})
        assert completed["status"] == "succeeded", completed["error"]

        partitions = client.get(f"/api/v1/catalog/partitions?dataset_id={TRADE_ID}")
        assert partitions.status_code == 200
        assert partitions.json()[0]["row_count"] == 2
        assert source.exists()

