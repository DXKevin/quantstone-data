from dataclasses import dataclass

from .datasets.tushare.cn.stock.stock_basic.collector import collect
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
    parameters: tuple[CollectorParameter, ...]
    datasets: tuple[str, ...]
    handler: object


@dataclass(frozen=True)
class CollectorDefinition:
    key: str
    name: str
    description: str
    operations: dict[str, CollectorOperation]


STOCK_BASIC = CollectorOperation(
    key="stock_basic",
    name="股票列表",
    description="调用 TuShare stock_basic 接口采集当前上市股票基础信息。",
    parameters=(),
    datasets=(DATASET_ID,),
    handler=collect,
)

COLLECTORS = {
    "tushare": CollectorDefinition(
        key="tushare",
        name="TuShare 采集器",
        description="通过 TuShare Pro API 采集数据，不同接口作为独立操作执行。",
        operations={STOCK_BASIC.key: STOCK_BASIC},
    )
}


def get_collector(key: str) -> CollectorDefinition | None:
    return COLLECTORS.get(key)


def get_operation(collector_key: str, operation_key: str) -> CollectorOperation | None:
    collector = get_collector(collector_key)
    return collector.operations.get(operation_key) if collector else None
