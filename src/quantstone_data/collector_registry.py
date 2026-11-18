from dataclasses import dataclass

from .datasets.tushare.cn.stock.daily.collector import (
    collect_daily_incremental,
    collect_daily_initial,
)
from .datasets.tushare.cn.stock.daily.definition import DATASET_ID as DAILY_DATASET_ID
from .datasets.tushare.cn.stock.stock_basic.collector import (
    collect_incremental,
    collect_initial,
)
from .datasets.tushare.cn.stock.stock_basic.definition import DATASET_ID


@dataclass(frozen=True)
class CollectorParameter:
    name: str
    data_type: str
    required: bool
    description: str


@dataclass(frozen=True)
class CollectorOperation:
    key: str
    name: str
    description: str
    purpose: str
    parameters: tuple[CollectorParameter, ...]
    datasets: tuple[str, ...]
    function: object


@dataclass(frozen=True)
class CollectorDefinition:
    key: str
    name: str
    description: str
    operations: dict[str, CollectorOperation]


STOCK_LIST_INITIAL = CollectorOperation(
    key="stock_list_initial",
    name="股票列表首次采集",
    description="首次调用 TuShare stock_basic 接口建立当前上市股票快照。",
    purpose="initial",
    parameters=(),
    datasets=(DATASET_ID,),
    function=collect_initial,
)

STOCK_LIST_INCREMENTAL = CollectorOperation(
    key="stock_list_incremental",
    name="股票列表增量更新",
    description="重新获取 TuShare stock_basic 当前快照，用于更新股票列表。",
    purpose="incremental",
    parameters=(),
    datasets=(DATASET_ID,),
    function=collect_incremental,
)

DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)

DAILY_INITIAL = CollectorOperation(
    key="daily_initial",
    name="日 K 首次采集",
    description="按交易日批次首次采集 TuShare daily 数据。",
    purpose="initial",
    parameters=DATE_RANGE_PARAMETERS,
    datasets=(DAILY_DATASET_ID,),
    function=collect_daily_initial,
)

DAILY_INCREMENTAL = CollectorOperation(
    key="daily_incremental",
    name="日 K 增量更新",
    description="按交易日批次补充 TuShare daily 数据。",
    purpose="incremental",
    parameters=DATE_RANGE_PARAMETERS,
    datasets=(DAILY_DATASET_ID,),
    function=collect_daily_incremental,
)

COLLECTORS = {
    "tushare_cn_stock": CollectorDefinition(
        key="tushare_cn_stock",
        name="TuShare A股采集器",
        description="通过 TuShare Pro API 采集中国内地 A 股数据。",
        operations={
            STOCK_LIST_INITIAL.key: STOCK_LIST_INITIAL,
            STOCK_LIST_INCREMENTAL.key: STOCK_LIST_INCREMENTAL,
            DAILY_INITIAL.key: DAILY_INITIAL,
            DAILY_INCREMENTAL.key: DAILY_INCREMENTAL,
        },
    )
}


def get_collector(key: str) -> CollectorDefinition | None:
    return COLLECTORS.get(key)


def get_operation(collector_key: str, operation_key: str) -> CollectorOperation | None:
    collector = get_collector(collector_key)
    return collector.operations.get(operation_key) if collector else None
