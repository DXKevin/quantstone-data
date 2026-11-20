from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app
from quantstone_data.overview import _coverage_percent, _serialize_timestamp


def test_coverage_percent_reserves_100_for_complete_coverage() -> None:
    assert _coverage_percent(2886, 2887) == 99.9
    assert _coverage_percent(2887, 2887) == 100.0
    assert _coverage_percent(0, 0) is None


def test_overview_timestamp_keeps_utc_semantics_after_sqlite_round_trip() -> None:
    naive_utc = datetime(2026, 11, 19, 5, 17, 37)
    aware_utc = datetime(2026, 11, 19, 5, 17, 37, tzinfo=UTC)

    assert _serialize_timestamp(naive_utc) == "2026-11-19T05:17:37+00:00"
    assert _serialize_timestamp(aware_utc) == "2026-11-19T05:17:37+00:00"


def test_overview_lists_datasets_with_empty_catalog(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "id": "demo.cn.stock.daily",
                "provider": "demo",
                "region": "cn",
                "instrument": "stock",
                "dataset_name": "daily",
                "market": None,
                "display_name": "测试日线",
                "description": "概览测试",
                "primary_key": ["trade_date", "symbol"],
                "time_field": "trade_date",
                "fields": [
                    {
                        "name": "trade_date",
                        "data_type": "date",
                        "nullable": False,
                        "description": "日期",
                    },
                    {
                        "name": "symbol",
                        "data_type": "string",
                        "nullable": False,
                        "description": "代码",
                    },
                ],
            },
        )
        assert created.status_code == 201, created.text
        response = client.get("/api/v1/overview/datasets")
        daily = client.get("/api/v1/overview/daily-completion")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["dataset_id"] == "demo.cn.stock.daily"
    assert item["partitions"] == 0
    assert item["rows"] == 0
    assert item["coverage_percent"] is None
    assert item["latest_partition"] is None
    assert daily.status_code == 200
    assert daily.json()["days"] == 30
    assert daily.json()["datasets"] == []


def test_collection_overview_counts_jobs(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    payload = {
        "id": "demo.cn.stock.daily",
        "provider": "demo",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "daily",
        "market": None,
        "display_name": "测试日线",
        "description": "采集概览测试",
        "primary_key": ["trade_date", "symbol"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "日期",
            },
            {
                "name": "symbol",
                "data_type": "string",
                "nullable": False,
                "description": "代码",
            },
        ],
    }
    with TestClient(app) as client:
        assert client.post("/api/v1/datasets", json=payload).status_code == 201
        assert client.post("/api/v1/datasets/demo.cn.stock.daily/activate").status_code == 200
        for _ in range(2):
            created = client.post(
                "/api/v1/collection-jobs",
                json={
                    "dataset_id": "demo.cn.stock.daily",
                    "operation": "initial",
                    "input_method": "file_import",
                },
            )
            assert created.status_code == 201, created.text
        response = client.get("/api/v1/overview/collection")

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] == 2
    assert body["awaiting_file"] == 2
    assert body["running"] == 0
    assert len(body["recent_jobs"]) == 2
    assert body["recent_jobs"][0]["display_name"] == "测试日线"

