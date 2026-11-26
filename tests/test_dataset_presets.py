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
            "tushare.cn.index.index_basic",
            "tushare.cn.index.index_daily",
            "tb_sbkj2077.cn.stock.minute_1m",
            "tb_lhsjk.cn.stock.auction_process",
            "tushare.cn.etf.etf_basic",
            "tushare.cn.etf.fund_daily",
            "tushare.cn.etf.fund_adj",
            "tushare.cn.etf.etf_limit",
            "tushare.cn.stock.stk_limit",
            "tushare.cn.stock.suspend_d",
            "tushare.cn.stock.adj_factor",
            "tushare.cn.stock.trade_cal",
            "tushare.cn.stock.namechange",
            "tushare.cn.stock.stock_basic",
            "tushare.cn.stock.stock_st",
            "tushare.cn.stock.daily",
            "tb_xxlpd.cn.stock.l2_order.sz",
            "tb_xxlpd.cn.stock.l2_trade.sz",
            "zhongtai.cn.stock.l2_order.sz",
            "zhongtai.cn.stock.l2_trade.sz",
        ]

        for preset in presets:
            created = client.post("/api/v1/datasets", json=preset["contract"])
            assert created.status_code == 201
            assert created.json()["status"] == "draft"

    contracts = {item["contract"]["id"]: item["contract"] for item in presets}
    index_basic = contracts["tushare.cn.index.index_basic"]
    index_daily = contracts["tushare.cn.index.index_daily"]
    minute_1m = contracts["tb_sbkj2077.cn.stock.minute_1m"]
    etf_basic = contracts["tushare.cn.etf.etf_basic"]
    etf_fund_daily = contracts["tushare.cn.etf.fund_daily"]
    etf_fund_adj = contracts["tushare.cn.etf.fund_adj"]
    etf_limit = contracts["tushare.cn.etf.etf_limit"]
    stk_limit = contracts["tushare.cn.stock.stk_limit"]
    suspend_d = contracts["tushare.cn.stock.suspend_d"]
    adj_factor = contracts["tushare.cn.stock.adj_factor"]
    daily = contracts["tushare.cn.stock.daily"]
    namechange = contracts["tushare.cn.stock.namechange"]
    stock_basic = contracts["tushare.cn.stock.stock_basic"]
    stock_st = contracts["tushare.cn.stock.stock_st"]
    l2_order = contracts["tb_xxlpd.cn.stock.l2_order.sz"]
    l2_trade = contracts["tb_xxlpd.cn.stock.l2_trade.sz"]
    zt_order = contracts["zhongtai.cn.stock.l2_order.sz"]
    zt_trade = contracts["zhongtai.cn.stock.l2_trade.sz"]
    assert l2_order["provider"] == "tb_xxlpd"
    assert index_basic["instrument"] == "index"
    assert index_basic["storage_policy"]["layout"] == "snapshot"
    assert index_basic["primary_key"] == ["ts_code"]
    assert index_daily["instrument"] == "index"
    assert index_daily["update_frequency"] == "daily"
    assert index_daily["primary_key"] == ["ts_code", "trade_date"]
    assert index_daily["storage_policy"]["layout"] == "yearly_with_delta"
    assert index_daily["storage_policy"]["compaction"] == "yearly"
    assert [item["name"] for item in index_daily["fields"]] == [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "change",
        "pct_chg",
        "vol",
        "amount",
    ]
    assert {item["operation"] for item in index_daily["collection_bindings"]} == {
        "index_daily_initial",
        "index_daily_incremental",
        "index_daily_repair",
    }
    assert minute_1m["provider"] == "tb_sbkj2077"
    assert minute_1m["time_granularity"] == "minute"
    assert minute_1m["primary_key"] == ["ts_code", "trade_date", "bar_time"]
    assert minute_1m["storage_policy"]["layout"] == "daily"
    assert [item["name"] for item in minute_1m["fields"]] == [
        "ts_code",
        "trade_date",
        "bar_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "pct_chg",
        "amplitude",
    ]
    assert {item["operation"] for item in minute_1m["collection_bindings"]} == {
        "minute_1m_initial",
        "minute_1m_incremental",
        "minute_1m_repair",
    }
    assert etf_basic["instrument"] == "etf"
    assert etf_basic["storage_policy"]["layout"] == "snapshot"
    assert etf_basic["primary_key"] == ["ts_code"]
    assert [item["name"] for item in etf_basic["fields"]] == [
        "ts_code",
        "csname",
        "extname",
        "cname",
        "index_code",
        "index_name",
        "setup_date",
        "list_date",
        "list_status",
        "exchange",
        "mgr_name",
        "custod_name",
        "mgt_fee",
        "etf_type",
    ]
    assert etf_fund_daily["storage_policy"]["layout"] == "yearly_with_delta"
    assert etf_fund_daily["primary_key"] == ["ts_code", "trade_date"]
    assert [item["name"] for item in etf_fund_daily["fields"]] == [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "change",
        "pct_chg",
        "vol",
        "amount",
    ]
    assert etf_fund_adj["primary_key"] == ["ts_code", "trade_date"]
    assert [item["name"] for item in etf_fund_adj["fields"]] == [
        "ts_code",
        "trade_date",
        "adj_factor",
    ]
    assert etf_limit["primary_key"] == ["ts_code", "trade_date"]
    assert [item["name"] for item in etf_limit["fields"]] == [
        "ts_code",
        "trade_date",
        "pre_close",
        "up_limit",
        "down_limit",
        "asset_type",
        "exchange",
    ]
    assert stk_limit["primary_key"] == ["ts_code", "trade_date"]
    assert [item["name"] for item in stk_limit["fields"]] == [
        "ts_code",
        "trade_date",
        "pre_close",
        "up_limit",
        "down_limit",
        "asset_type",
        "exchange",
    ]
    assert suspend_d["primary_key"] == ["ts_code", "trade_date", "suspend_type"]
    assert [item["name"] for item in suspend_d["fields"]] == [
        "ts_code",
        "trade_date",
        "suspend_timing",
        "suspend_type",
    ]
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
    assert zt_order["provider"] == "zhongtai"
    assert zt_order["is_historical"] is True
    assert zt_order["update_frequency"] == "manual"
    assert zt_order["primary_key"] == ["trade_date", "symbol", "exchange_order_no"]
    assert [item["name"] for item in zt_order["fields"]] == [
        "symbol",
        "exchange_code",
        "trade_date",
        "event_time",
        "channel_code",
        "exchange_order_no",
        "order_type",
        "side",
        "price",
        "volume",
    ]
    assert [item["data_type"] for item in zt_trade["fields"]] == [
        "string",
        "string",
        "date",
        "int32",
        "int64",
        "string",
        "string",
        "string",
        "int64",
        "int64",
        "int64",
        "int64",
    ]
    assert zt_trade["primary_key"] == ["trade_date", "symbol", "trade_no"]
    assert zt_trade["is_historical"] is True
    trade_cal = contracts["tushare.cn.stock.trade_cal"]
    assert trade_cal["update_frequency"] == "monthly"
    assert trade_cal["time_granularity"] == "day"
    assert adj_factor["primary_key"] == ["ts_code", "trade_date"]
    assert adj_factor["storage_policy"]["layout"] == "yearly_with_delta"
    assert adj_factor["storage_policy"]["calendar_dataset_id"] == (
        "tushare.cn.stock.trade_cal"
    )
    assert [item["name"] for item in adj_factor["fields"]] == [
        "ts_code",
        "trade_date",
        "adj_factor",
    ]
    assert stock_basic["update_frequency"] == "daily"
    assert stock_basic["time_granularity"] == "none"
    assert namechange["primary_key"] == ["ts_code", "start_date", "name"]
    assert namechange["storage_policy"]["layout"] == "snapshot"
    assert [item["name"] for item in namechange["fields"]] == [
        "ts_code",
        "name",
        "start_date",
        "end_date",
        "ann_date",
        "change_reason",
    ]
    assert {item["operation"] for item in namechange["collection_bindings"]} == {
        "namechange_initial",
        "namechange_incremental",
    }
    assert daily["update_frequency"] == "daily"
    assert daily["time_granularity"] == "day"
    assert stock_st["primary_key"] == ["ts_code", "trade_date"]
    assert stock_st["storage_policy"]["layout"] == "yearly_with_delta"
    assert stock_st["storage_policy"]["allow_empty_partitions"] is True
    assert daily["storage_policy"]["allow_empty_partitions"] is False
    assert [item["name"] for item in stock_st["fields"]] == [
        "ts_code",
        "name",
        "trade_date",
        "type",
        "type_name",
    ]
    assert {item["operation"] for item in stock_st["collection_bindings"]} == {
        "stock_st_initial",
        "stock_st_incremental",
    }
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
