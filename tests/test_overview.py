from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app


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

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["dataset_id"] == "demo.cn.stock.daily"
    assert item["partitions"] == 0
    assert item["rows"] == 0
    assert item["coverage_percent"] is None
    assert item["latest_partition"] is None
