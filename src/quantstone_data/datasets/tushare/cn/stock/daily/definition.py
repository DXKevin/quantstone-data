DATASET_ID = "tushare.cn.stock.daily"


def dataset_contract() -> dict:
    fields = [
        ("ts_code", "string", False, "TS股票代码", None),
        ("trade_date", "date", False, "交易日期", None),
        ("open", "float64", True, "开盘价", "元"),
        ("high", "float64", True, "最高价", "元"),
        ("low", "float64", True, "最低价", "元"),
        ("close", "float64", True, "收盘价", "元"),
        ("pre_close", "float64", True, "昨收价", "元"),
        ("change", "float64", True, "涨跌额", "元"),
        ("pct_chg", "float64", True, "涨跌幅", "%"),
        ("vol", "float64", True, "成交量", "手"),
        ("amount", "float64", True, "成交额", "千元"),
    ]
    return {
        "display_name": "A股日K",
        "description": "TuShare daily 接口提供的A股未复权日线行情。",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare_cn_stock",
                "operation": "daily_initial",
            },
            {
                "purpose": "incremental",
                "collector_key": "tushare_cn_stock",
                "operation": "daily_incremental",
            },
        ],
        "storage_policy": {
            "logical_partition_field": "trade_date",
            "layout": "yearly_with_delta",
            "write_strategy": "replace_partition",
            "compaction": "yearly",
        },
        "primary_key": ["ts_code", "trade_date"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": name,
                "data_type": data_type,
                "nullable": nullable,
                "description": description,
                "unit": unit,
                "source_name": name,
            }
            for name, data_type, nullable, description, unit in fields
        ],
    }
