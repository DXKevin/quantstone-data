from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app


def dataset_payload() -> dict:
    return {
        "id": "tb_l2.cn.stock.l2_order.sh",
        "provider": "tb_l2",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "l2_order",
        "market": "sh",
        "display_name": "上海股票逐笔委托",
        "description": "供应商交付的上海市场 L2 逐笔委托数据",
        "primary_key": ["trade_date", "order_no"],
        "time_field": "event_time",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日期",
            },
            {
                "name": "event_time",
                "data_type": "timestamp",
                "nullable": False,
                "description": "委托时间",
            },
            {
                "name": "order_no",
                "data_type": "int64",
                "nullable": False,
                "description": "委托序号",
            },
        ],
    }


def test_dataset_lifecycle(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json=dataset_payload())
        assert created.status_code == 201
        assert created.json()["status"] == "draft"
        assert created.json()["schema"]["primary_key"] == ["trade_date", "order_no"]

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [dataset_payload()["id"]]

        activated = client.post(f"/api/v1/datasets/{dataset_payload()['id']}/activate")
        assert activated.status_code == 200
        assert activated.json()["status"] == "active"

        deleting = client.delete(f"/api/v1/datasets/{dataset_payload()['id']}")
        assert deleting.status_code == 409


def test_dataset_id_must_match_segments(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    payload = dataset_payload()
    payload["id"] = "wrong.id"

    with TestClient(app) as client:
        response = client.post("/api/v1/datasets", json=payload)

    assert response.status_code == 422
    assert "dataset id must be" in response.text


def test_duplicate_dataset_is_rejected(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    with TestClient(app) as client:
        assert client.post("/api/v1/datasets", json=dataset_payload()).status_code == 201
        response = client.post("/api/v1/datasets", json=dataset_payload())

    assert response.status_code == 409
