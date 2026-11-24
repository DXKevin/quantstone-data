from ...collector_types import CollectorDefinition, CollectorOperation, CollectorParameter
from .pipeline import collect_order, collect_trade

ORDER_DATASET_ID = "wind.cn.stock.l2_order.sz"
TRADE_DATASET_ID = "wind.cn.stock.l2_trade.sz"

DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "首次采集开始日期"),
    CollectorParameter("end_date", "date", True, "首次采集结束日期"),
)
INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选截止日期，默认当天"),
)


def _operation(
    key: str,
    name: str,
    purpose: str,
    parameters: tuple[CollectorParameter, ...],
    dataset_id: str,
    function,
) -> CollectorOperation:
    return CollectorOperation(
        key=key,
        name=name,
        description="从百度网盘获取 Wind L2 日压缩包，解压深市股票 CSV 并转换为契约 Parquet。",
        purpose=purpose,
        parameters=parameters,
        datasets=(dataset_id,),
        function=function,
    )


OPERATIONS = (
    _operation(
        "l2_order_initial",
        "Wind 深市逐笔委托首次采集",
        "initial",
        DATE_RANGE_PARAMETERS,
        ORDER_DATASET_ID,
        collect_order,
    ),
    _operation(
        "l2_order_incremental",
        "Wind 深市逐笔委托增量采集",
        "incremental",
        INCREMENTAL_PARAMETERS,
        ORDER_DATASET_ID,
        collect_order,
    ),
    _operation(
        "l2_trade_initial",
        "Wind 深市逐笔成交首次采集",
        "initial",
        DATE_RANGE_PARAMETERS,
        TRADE_DATASET_ID,
        collect_trade,
    ),
    _operation(
        "l2_trade_incremental",
        "Wind 深市逐笔成交增量采集",
        "incremental",
        INCREMENTAL_PARAMETERS,
        TRADE_DATASET_ID,
        collect_trade,
    ),
)

COLLECTOR = CollectorDefinition(
    key="wind_l2_sz",
    name="Wind A股 L2（百度网盘）",
    description="按交易日下载 Wind L2 压缩包，生成深市逐笔委托或逐笔成交数据。",
    operations={item.key: item for item in OPERATIONS},
)
