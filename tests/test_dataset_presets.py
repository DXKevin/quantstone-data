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
            "wind.cn.stock.l2_order.sz",
            "wind.cn.stock.l2_trade.sz",
        ]

        for preset in presets:
            created = client.post("/api/v1/datasets", json=preset["contract"])
            assert created.status_code == 201
            assert created.json()["status"] == "draft"

    daily = presets[2]["contract"]
    stock_basic = presets[1]["contract"]
    l2_order = presets[3]["contract"]
    l2_trade = presets[4]["contract"]
    assert l2_order["provider"] == "wind"
    assert l2_order["market"] == "sz"
    assert l2_order["update_frequency"] == "daily"
    assert l2_order["time_granularity"] == "tick"
    assert l2_order["primary_key"] == ["trade_date", "symbol", "exchange_order_no"]
    assert l2_order["fields"][0]["name"] == "symbol"
    assert l2_order["fields"][0]["data_type"] == "string"
    assert l2_order["fields"][1]["name"] == "exchange_code"
    assert l2_order["fields"][1]["data_type"] == "string"
    assert l2_order["fields"][4]["name"] == "channel_code"
    assert l2_order["fields"][4]["data_type"] == "string"
    assert l2_order["fields"][5]["source_name"] == "交易所委托号"
    assert l2_trade["primary_key"] == ["trade_date", "symbol", "trade_no"]
    assert l2_trade["fields"][6]["name"] == "order_code"
    assert l2_trade["fields"][6]["data_type"] == "string"
    assert l2_trade["fields"][6]["source_name"] == "委托代码"
    assert l2_trade["fields"][7]["nullable"] is True
    assert presets[0]["contract"]["update_frequency"] == "monthly"
    assert presets[0]["contract"]["time_granularity"] == "day"
    assert stock_basic["update_frequency"] == "daily"
    assert stock_basic["time_granularity"] == "none"
    assert daily["update_frequency"] == "daily"
    assert daily["time_granularity"] == "day"
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
