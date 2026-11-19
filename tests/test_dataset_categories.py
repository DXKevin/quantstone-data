from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app


def dataset_payload() -> dict:
    return {
        "id": "demo.cn.stock.daily",
        "provider": "demo",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "daily",
        "market": None,
        "display_name": "测试日线",
        "description": "数据集大类测试",
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


def test_dataset_categories_can_organize_datasets(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/dataset-categories",
            json={"name": "A股数据", "description": "中国内地股票数据"},
        )
        assert created.status_code == 201
        category_id = created.json()["id"]
        assert created.json()["dataset_count"] == 0

        duplicate = client.post(
            "/api/v1/dataset-categories", json={"name": "A股数据"}
        )
        assert duplicate.status_code == 409

        dataset = client.post("/api/v1/datasets", json=dataset_payload())
        assert dataset.status_code == 201
        assigned = client.put(
            f"/api/v1/datasets/{dataset.json()['id']}/category",
            json={"category_id": category_id},
        )
        assert assigned.status_code == 200
        assert assigned.json()["category_id"] == category_id

        categories = client.get("/api/v1/dataset-categories")
        assert categories.json()[0]["dataset_count"] == 1
        assert client.get("/api/v1/datasets").json()[0]["category_id"] == category_id

        occupied_delete = client.delete(f"/api/v1/dataset-categories/{category_id}")
        assert occupied_delete.status_code == 409

        renamed = client.patch(
            f"/api/v1/dataset-categories/{category_id}",
            json={"name": "中国A股", "description": None},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "中国A股"

        unassigned = client.put(
            f"/api/v1/datasets/{dataset.json()['id']}/category",
            json={"category_id": None},
        )
        assert unassigned.json()["category_id"] is None
        assert client.delete(f"/api/v1/dataset-categories/{category_id}").status_code == 204
