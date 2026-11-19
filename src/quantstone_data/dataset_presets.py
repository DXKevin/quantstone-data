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
            description="TuShare stock_basic 当前上市股票基础信息。",
            collection_bindings=[
                {
                    "purpose": "initial",
                    "collector_key": "tushare_cn_stock",
                    "operation": "stock_list_initial",
                    "parameters": {},
                },
                {
                    "purpose": "incremental",
                    "collector_key": "tushare_cn_stock",
                    "operation": "stock_list_incremental",
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
                field("name", "string", "股票名称", nullable=False),
                field("list_status", "string", "上市状态", nullable=False),
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
