from dataclasses import dataclass

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

COLLECTORS = {
    "tushare": CollectorDefinition(
        key="tushare",
        name="TuShare 采集器",
        description="通过 TuShare Pro API 采集数据，不同接口作为独立操作执行。",
        operations={
            STOCK_LIST_INITIAL.key: STOCK_LIST_INITIAL,
            STOCK_LIST_INCREMENTAL.key: STOCK_LIST_INCREMENTAL,
        },
    )
}


def get_collector(key: str) -> CollectorDefinition | None:
    return COLLECTORS.get(key)


def get_operation(collector_key: str, operation_key: str) -> CollectorOperation | None:
    collector = get_collector(collector_key)
    return collector.operations.get(operation_key) if collector else None
