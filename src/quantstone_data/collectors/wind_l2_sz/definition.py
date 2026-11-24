from ...collector_types import CollectorDefinition, CollectorOperation, CollectorParameter
from .pipeline import collect_wind_l2

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
) -> CollectorOperation:
    return CollectorOperation(
        key=key,
        name=name,
        description="从百度网盘获取 Wind L2 日压缩包，解压深市股票 CSV 并转换为契约 Parquet。",
        purpose=purpose,
        parameters=parameters,
        datasets=(ORDER_DATASET_ID, TRADE_DATASET_ID),
        function=collect_wind_l2,
    )


OPERATIONS = (
    _operation(
        "wind_l2_initial",
        "Wind 深市 L2 联合首次采集",
        "initial",
        DATE_RANGE_PARAMETERS,
    ),
    _operation(
        "wind_l2_incremental",
        "Wind 深市 L2 联合增量采集",
        "incremental",
        INCREMENTAL_PARAMETERS,
    ),
)

COLLECTOR = CollectorDefinition(
    key="wind_l2_sz",
    name="Wind A股 L2（百度网盘）",
    description="按交易日下载一次 Wind L2 压缩包，联合生成深市逐笔委托和逐笔成交数据。",
    operations={item.key: item for item in OPERATIONS},
)
