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
) -> dict[str, str | bool | None]:
    return {
        "name": name,
        "data_type": data_type,
        "nullable": nullable,
        "description": description,
        "unit": unit,
        "source_name": name,
    }


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
)


@router.get("", response_model=list[DatasetPreset])
def list_dataset_presets() -> tuple[DatasetPreset, ...]:
    return DATASET_PRESETS
