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
    stock_basic = presets[1]["contract"]
    assert [item["name"] for item in stock_basic["fields"]] == [
        "ts_code",
        "symbol",
        "name",
        "area",
        "industry",
        "fullname",
        "enname",
        "cnspell",
        "market",
        "exchange",
        "curr_type",
        "list_status",
        "list_date",
        "delist_date",
        "is_hs",
        "act_name",
        "act_ent_type",
    ]
    assert daily["primary_key"] == ["ts_code", "trade_date"]
    assert daily["storage_policy"]["calendar_dataset_id"] == "tushare.cn.stock.trade_cal"
    assert {item["operation"] for item in daily["collection_bindings"]} == {
        "daily_initial",
        "daily_incremental",
    }


def test_legacy_unpublished_stock_basic_contract_is_completed_on_restart(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    data_root = tmp_path / "data"
    legacy_contract = {
        "id": "tushare.cn.stock.stock_basic",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "stock_basic",
        "display_name": "A股股票列表",
        "description": "TuShare stock_basic 当前上市股票基础信息。",
        "primary_key": ["ts_code"],
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

    with TestClient(create_app(database_url, data_root=data_root)) as client:
        assert client.post("/api/v1/datasets", json=legacy_contract).status_code == 201

    with TestClient(create_app(database_url, data_root=data_root)) as restarted:
        dataset = restarted.get("/api/v1/datasets/tushare.cn.stock.stock_basic")
        assert dataset.status_code == 200
        fields = dataset.json()["schema"]["fields"]
        assert len(fields) == 17
        assert dataset.json()["description"] == (
            "TuShare stock_basic 全部股票基础信息，包含上市、退市和暂停上市状态。"
        )
        assert [item["name"] for item in fields] == [
            "ts_code",
            "symbol",
            "name",
            "area",
            "industry",
            "fullname",
            "enname",
            "cnspell",
            "market",
            "exchange",
            "curr_type",
            "list_status",
            "list_date",
            "delist_date",
            "is_hs",
            "act_name",
            "act_ent_type",
        ]
