from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app


def test_presets_are_valid_contracts_that_create_drafts(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/dataset-presets")
        assert response.status_code == 200
        presets = response.json()
        assert [item["contract"]["id"] for item in presets] == [
            "tushare.cn.stock.trade_cal",
            "tushare.cn.stock.stock_basic",
            "tushare.cn.stock.daily",
        ]

        for preset in presets:
            created = client.post("/api/v1/datasets", json=preset["contract"])
            assert created.status_code == 201
            assert created.json()["status"] == "draft"

    daily = presets[2]["contract"]
    assert daily["primary_key"] == ["ts_code", "trade_date"]
    assert daily["storage_policy"]["calendar_dataset_id"] == "tushare.cn.stock.trade_cal"
    assert {item["operation"] for item in daily["collection_bindings"]} == {
        "daily_initial",
        "daily_incremental",
    }
