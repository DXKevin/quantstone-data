from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RetryPolicy,
)
from .minute_1m import collect_incremental, collect_initial

DATASET_ID = "tb_sbkj2077.cn.stock.minute_1m"
DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)
INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选的更新截止日期，默认当天"),
)

OPERATIONS = (
    CollectorOperation(
        key="minute_1m_initial",
        name="沪深股票1分钟首次采集",
        description="按年压缩包建立沪深股票1分钟日分区历史数据。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DATASET_ID,),
        function=collect_initial,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
    CollectorOperation(
        key="minute_1m_repair",
        name="沪深股票1分钟修复",
        description="按日期范围重新采集沪深股票1分钟日包，替换受影响分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DATASET_ID,),
        function=collect_incremental,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
    CollectorOperation(
        key="minute_1m_incremental",
        name="沪深股票1分钟增量更新",
        description="从每日更新压缩包补充沪深股票1分钟数据。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(DATASET_ID,),
        function=collect_incremental,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
)

COLLECTOR = CollectorDefinition(
    key="minute_baidu",
    name="lhsjk_023199 A股分钟数据",
    description="采集供应商 lhsjk_023199 通过百度网盘交付的沪深股票分钟线。",
    operations={operation.key: operation for operation in OPERATIONS},
)
