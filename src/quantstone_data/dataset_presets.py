from fastapi import APIRouter
from pydantic import BaseModel, Field

from .schemas import DatasetCreate

router = APIRouter(prefix="/dataset-presets", tags=["dataset-presets"])


class DatasetPreset(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    category: str
    contract: DatasetCreate


def field(
    name: str,
    data_type: str,
    description: str,
    *,
    nullable: bool = True,
    unit: str | None = None,
    source_name: str | None = None,
) -> dict[str, str | bool | None]:
    return {
        "name": name,
        "data_type": data_type,
        "nullable": nullable,
        "description": description,
        "unit": unit,
        "source_name": source_name or name,
    }


def _zhongtai_order_fields() -> list[dict[str, str | bool | None]]:
    return [
        field("symbol", "string", "证券代码", nullable=False, source_name="SecurityID"),
        field(
            "exchange_code",
            "string",
            "交易所数字证券代码",
            nullable=False,
            source_name="SecurityID",
        ),
        field("trade_date", "date", "交易日", nullable=False, source_name="tradedate"),
        field(
            "event_time",
            "int32",
            "事件时间，HHMMSSmmm",
            nullable=False,
            unit="HHMMSSmmm",
            source_name="TransactTime",
        ),
        field("channel_code", "string", "频道代码", nullable=False, source_name="ChannelNo"),
        field(
            "exchange_order_no", "int64", "交易所委托号", nullable=False, source_name="ApplSeqNum"
        ),
        field(
            "order_type",
            "string",
            "委托类型；0=限价，1=市价，U=本方最优",
            nullable=False,
            source_name="OrderType",
        ),
        field("side", "string", "买卖方向，B=买入，S=卖出", nullable=False, source_name="Side"),
        field(
            "price",
            "int64",
            "委托价格，精度 0.0001 元",
            nullable=False,
            unit="0.0001 元",
            source_name="Price",
        ),
        field(
            "volume", "int64", "委托数量，单位股", nullable=False, unit="股", source_name="OrderQty"
        ),
    ]


def _zhongtai_trade_fields() -> list[dict[str, str | bool | None]]:
    return [
        field("symbol", "string", "证券代码", nullable=False, source_name="SecurityID"),
        field(
            "exchange_code",
            "string",
            "交易所数字证券代码",
            nullable=False,
            source_name="SecurityID",
        ),
        field("trade_date", "date", "交易日", nullable=False, source_name="tradedate"),
        field(
            "event_time",
            "int32",
            "事件时间，HHMMSSmmm",
            nullable=False,
            unit="HHMMSSmmm",
            source_name="tradetime",
        ),
        field("trade_no", "int64", "成交编号", nullable=False, source_name="ApplSeqNum"),
        field(
            "trade_code",
            "string",
            "成交代码；C=撤单，0 或空=成交",
            nullable=True,
            source_name="ExecType",
        ),
        field(
            "order_code",
            "string",
            "委托代码（中泰源无对应字段，导入时填 0 或空）",
            nullable=True,
            source_name="无",
        ),
        field(
            "side",
            "string",
            "BS 标志；由买卖委托时间和序号还原，撤单为空",
            nullable=True,
            source_name="无",
        ),
        field(
            "price",
            "int64",
            "成交价格，精度 0.0001 元",
            nullable=False,
            unit="0.0001 元",
            source_name="Price",
        ),
        field(
            "volume", "int64", "成交数量，单位股", nullable=False, unit="股", source_name="TradeQty"
        ),
        field("ask_order_no", "int64", "叫卖序号", nullable=False, source_name="OfferApplSeqNum"),
        field("bid_order_no", "int64", "叫买序号", nullable=False, source_name="BidApplSeqNum"),
    ]


DATASET_PRESETS = (
    DatasetPreset(
        key="tushare_trade_cal",
        category="TuShare · A股",
        contract=DatasetCreate(
            id="tushare.cn.stock.trade_cal",
            provider="tushare",
            region="cn",
            instrument="stock",
            dataset_name="trade_cal",
            market=None,
            display_name="A股交易日历",
            description="TuShare trade_cal 上交所交易日历；沪深北股票交易所共用交易日安排。",
            update_frequency="monthly",
            time_granularity="day",
            collection_bindings=[
                {
                    "purpose": "initial",
                    "collector_key": "tushare_cn_stock",
                    "operation": "trade_cal_initial",
                    "parameters": {},
                },
                {
                    "purpose": "incremental",
                    "collector_key": "tushare_cn_stock",
                    "operation": "trade_cal_incremental",
                    "parameters": {},
                },
            ],
            storage_policy={
                "logical_partition_field": None,
                "calendar_dataset_id": None,
                "layout": "snapshot",
                "write_strategy": "replace_snapshot",
                "compaction": None,
            },
            primary_key=["exchange", "cal_date"],
            time_field="cal_date",
            fields=[
                field("exchange", "string", "交易所代码", nullable=False),
                field("cal_date", "date", "日历日期", nullable=False),
                field("is_open", "int32", "是否交易", nullable=False),
                field("pretrade_date", "date", "上一交易日"),
            ],
        ),
    ),
    DatasetPreset(
        key="tushare_stock_basic",
        category="TuShare · A股",
        contract=DatasetCreate(
            id="tushare.cn.stock.stock_basic",
            provider="tushare",
            region="cn",
            instrument="stock",
            dataset_name="stock_basic",
            market=None,
            display_name="A股股票列表",
            description="TuShare stock_basic 全部股票基础信息，包含上市、退市和暂停上市状态。",
            update_frequency="daily",
            time_granularity="none",
            collection_bindings=[
                {
                    "purpose": "initial",
                    "collector_key": "tushare_cn_stock",
                    "operation": "stock_basic_initial",
                    "parameters": {},
                },
                {
                    "purpose": "incremental",
                    "collector_key": "tushare_cn_stock",
                    "operation": "stock_basic_incremental",
                    "parameters": {},
                },
            ],
            storage_policy={
                "logical_partition_field": None,
                "calendar_dataset_id": None,
                "layout": "snapshot",
                "write_strategy": "replace_snapshot",
                "compaction": None,
            },
            primary_key=["ts_code"],
            time_field=None,
            fields=[
                field("ts_code", "string", "TS代码", nullable=False),
                field("symbol", "string", "股票代码"),
                field("name", "string", "股票名称"),
                field("area", "string", "地域"),
                field("industry", "string", "所属行业"),
                field("fullname", "string", "股票全称"),
                field("enname", "string", "英文全称"),
                field("cnspell", "string", "拼音缩写"),
                field("market", "string", "市场类型"),
                field("exchange", "string", "交易所代码"),
                field("curr_type", "string", "交易货币"),
                field("list_status", "string", "上市状态"),
                field("list_date", "date", "上市日期"),
                field("delist_date", "date", "退市日期"),
                field("is_hs", "string", "沪深港通标的"),
                field("act_name", "string", "实控人名称"),
                field("act_ent_type", "string", "实控人企业性质"),
            ],
        ),
    ),
    DatasetPreset(
        key="tushare_daily",
        category="TuShare · A股",
        contract=DatasetCreate(
            id="tushare.cn.stock.daily",
            provider="tushare",
            region="cn",
            instrument="stock",
            dataset_name="daily",
            market=None,
            display_name="A股日K",
            description="TuShare daily 未复权日线行情。",
            update_frequency="daily",
            time_granularity="day",
            collection_bindings=[
                {
                    "purpose": "initial",
                    "collector_key": "tushare_cn_stock",
                    "operation": "daily_initial",
                    "parameters": {},
                },
                {
                    "purpose": "incremental",
                    "collector_key": "tushare_cn_stock",
                    "operation": "daily_incremental",
                    "parameters": {},
                },
            ],
            storage_policy={
                "logical_partition_field": "trade_date",
                "calendar_dataset_id": "tushare.cn.stock.trade_cal",
                "layout": "yearly_with_delta",
                "write_strategy": "replace_partition",
                "compaction": "yearly",
            },
            primary_key=["ts_code", "trade_date"],
            time_field="trade_date",
            fields=[
                field("ts_code", "string", "TS代码", nullable=False),
                field("trade_date", "date", "交易日期", nullable=False),
                field("open", "float64", "开盘价"),
                field("high", "float64", "最高价"),
                field("low", "float64", "最低价"),
                field("close", "float64", "收盘价"),
                field("pre_close", "float64", "昨收价"),
                field("change", "float64", "涨跌额"),
                field("pct_chg", "float64", "涨跌幅", unit="%"),
                field("vol", "float64", "成交量", unit="手"),
                field("amount", "float64", "成交额", unit="千元"),
            ],
        ),
    ),
    DatasetPreset(
        key="wind_l2_order_sz",
        category="Wind · A股 L2",
        contract=DatasetCreate(
            id="wind.cn.stock.l2_order.sz",
            provider="wind",
            region="cn",
            instrument="stock",
            dataset_name="l2_order",
            market="sz",
            display_name="Wind A股逐笔委托（深市）",
            description=(
                "Wind A股 L2 逐笔委托（深市），源文件 SZ/YYYYMMDD/order.parquet。"
                "时间格式 HHMMSSmmm，价格精度 0.0001 元。"
            ),
            update_frequency="daily",
            time_granularity="tick",
            collection_bindings=[],
            storage_policy={
                "logical_partition_field": "trade_date",
                "calendar_dataset_id": "tushare.cn.stock.trade_cal",
                "layout": "daily",
                "write_strategy": "replace_partition",
                "compaction": None,
            },
            primary_key=["trade_date", "symbol", "exchange_order_no"],
            time_field="event_time",
            fields=[
                field(
                    "symbol",
                    "string",
                    "万得证券代码",
                    nullable=False,
                    source_name="万得代码",
                ),
                field(
                    "exchange_code",
                    "string",
                    "交易所数字证券代码",
                    nullable=False,
                    source_name="交易所代码",
                ),
                field(
                    "trade_date",
                    "date",
                    "交易日",
                    nullable=False,
                    source_name="自然日",
                ),
                field(
                    "event_time",
                    "int32",
                    "事件时间，HHMMSSmmm",
                    nullable=False,
                    unit="HHMMSSmmm",
                    source_name="时间",
                ),
                field(
                    "channel_code",
                    "string",
                    "频道代码",
                    nullable=False,
                    source_name="委托编号",
                ),
                field(
                    "exchange_order_no",
                    "int64",
                    "交易所委托号",
                    nullable=False,
                    source_name="交易所委托号",
                ),
                field(
                    "order_type",
                    "string",
                    "委托类型；0=限价，1=市价，U=本方最优",
                    nullable=False,
                    source_name="委托类型",
                ),
                field(
                    "side",
                    "string",
                    "买卖方向，B=买入，S=卖出",
                    nullable=False,
                    source_name="委托代码",
                ),
                field(
                    "price",
                    "int64",
                    "委托价格，精度 0.0001 元",
                    nullable=False,
                    unit="0.0001 元",
                    source_name="委托价格",
                ),
                field(
                    "volume",
                    "int64",
                    "委托数量，单位股",
                    nullable=False,
                    unit="股",
                    source_name="委托数量",
                ),
            ],
        ),
    ),
    DatasetPreset(
        key="wind_l2_trade_sz",
        category="Wind · A股 L2",
        contract=DatasetCreate(
            id="wind.cn.stock.l2_trade.sz",
            provider="wind",
            region="cn",
            instrument="stock",
            dataset_name="l2_trade",
            market="sz",
            display_name="Wind A股逐笔成交（深市）",
            description=(
                "Wind A股 L2 逐笔成交（深市），源文件 SZ/YYYYMMDD/trade.parquet。"
                "时间格式 HHMMSSmmm，价格精度 0.0001 元。"
                "成交代码 C=撤单，0 或空=成交。"
            ),
            update_frequency="daily",
            time_granularity="tick",
            collection_bindings=[],
            storage_policy={
                "logical_partition_field": "trade_date",
                "calendar_dataset_id": "tushare.cn.stock.trade_cal",
                "layout": "daily",
                "write_strategy": "replace_partition",
                "compaction": None,
            },
            primary_key=["trade_date", "symbol", "trade_no"],
            time_field="event_time",
            fields=[
                field(
                    "symbol",
                    "string",
                    "万得证券代码",
                    nullable=False,
                    source_name="万得代码",
                ),
                field(
                    "exchange_code",
                    "string",
                    "交易所数字证券代码",
                    nullable=False,
                    source_name="交易所代码",
                ),
                field(
                    "trade_date",
                    "date",
                    "交易日",
                    nullable=False,
                    source_name="自然日",
                ),
                field(
                    "event_time",
                    "int32",
                    "事件时间，HHMMSSmmm",
                    nullable=False,
                    unit="HHMMSSmmm",
                    source_name="时间",
                ),
                field(
                    "trade_no",
                    "int64",
                    "成交编号",
                    nullable=False,
                    source_name="成交编号",
                ),
                field(
                    "trade_code",
                    "string",
                    "成交代码；C=撤单，0 或空=成交",
                    nullable=True,
                    source_name="成交代码",
                ),
                field(
                    "order_code",
                    "string",
                    "委托代码（保留字段）",
                    nullable=True,
                    source_name="委托代码",
                ),
                field(
                    "side",
                    "string",
                    "BS 标志，B=买入，S=卖出",
                    nullable=True,
                    source_name="BS标志",
                ),
                field(
                    "price",
                    "int64",
                    "成交价格，精度 0.0001 元",
                    nullable=False,
                    unit="0.0001 元",
                    source_name="成交价格",
                ),
                field(
                    "volume",
                    "int64",
                    "成交数量，单位股",
                    nullable=False,
                    unit="股",
                    source_name="成交数量",
                ),
                field(
                    "ask_order_no",
                    "int64",
                    "叫卖序号",
                    nullable=False,
                    source_name="叫卖序号",
                ),
                field(
                    "bid_order_no",
                    "int64",
                    "叫买序号",
                    nullable=False,
                    source_name="叫买序号",
                ),
            ],
        ),
    ),
    DatasetPreset(
        key="zhongtai_l2_order_sz",
        category="中泰 · A股 L2",
        contract=DatasetCreate(
            id="zhongtai.cn.stock.l2_order.sz",
            provider="zhongtai",
            region="cn",
            instrument="stock",
            dataset_name="l2_order",
            market="sz",
            display_name="中泰证券 A股逐笔委托（深市）",
            description=(
                "中泰证券历史 L2 逐笔委托（深市），仅历史数据，不再更新；"
                "字段已对齐 Wind 深市 L2 契约。"
            ),
            update_frequency="manual",
            time_granularity="tick",
            is_historical=True,
            collection_bindings=[],
            storage_policy={
                "logical_partition_field": "trade_date",
                "calendar_dataset_id": "tushare.cn.stock.trade_cal",
                "layout": "daily",
                "write_strategy": "replace_partition",
                "compaction": None,
            },
            primary_key=["trade_date", "symbol", "exchange_order_no"],
            time_field="event_time",
            fields=_zhongtai_order_fields(),
        ),
    ),
    DatasetPreset(
        key="zhongtai_l2_trade_sz",
        category="中泰 · A股 L2",
        contract=DatasetCreate(
            id="zhongtai.cn.stock.l2_trade.sz",
            provider="zhongtai",
            region="cn",
            instrument="stock",
            dataset_name="l2_trade",
            market="sz",
            display_name="中泰证券 A股逐笔成交（深市）",
            description=(
                "中泰证券历史 L2 逐笔成交（深市），仅历史数据，不再更新；"
                "字段已对齐 Wind 深市 L2 契约。"
            ),
            update_frequency="manual",
            time_granularity="tick",
            is_historical=True,
            collection_bindings=[],
            storage_policy={
                "logical_partition_field": "trade_date",
                "calendar_dataset_id": "tushare.cn.stock.trade_cal",
                "layout": "daily",
                "write_strategy": "replace_partition",
                "compaction": None,
            },
            primary_key=["trade_date", "symbol", "trade_no"],
            time_field="event_time",
            fields=_zhongtai_trade_fields(),
        ),
    ),
)


@router.get("", response_model=list[DatasetPreset])
def list_dataset_presets() -> tuple[DatasetPreset, ...]:
    return DATASET_PRESETS
