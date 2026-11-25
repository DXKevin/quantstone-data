from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RetryPolicy,
)
from .auction_process import collect_daily, collect_initial

DATASET_ID = "tb.cn.stock.auction_process"
DATES = (
    CollectorParameter("start_date", "date", True, "开始日期"),
    CollectorParameter("end_date", "date", True, "结束日期"),
)
END = (CollectorParameter("end_date", "date", False, "截止日期，默认当天"),)

OPERATIONS = (
    CollectorOperation(
        "auction_process_initial",
        "集合竞价首次采集",
        "按月包建立日分区。",
        "initial",
        DATES,
        (DATASET_ID,),
        collect_initial,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
    CollectorOperation(
        "auction_process_incremental",
        "集合竞价增量更新",
        "读取单日更新文件。",
        "incremental",
        END,
        (DATASET_ID,),
        collect_daily,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
    CollectorOperation(
        "auction_process_repair",
        "集合竞价修复",
        "按日期重新读取单日文件。",
        "repair",
        DATES,
        (DATASET_ID,),
        collect_daily,
        retry=RetryPolicy(attempts=3, delay_seconds=10, max_delay_seconds=60),
    ),
)
COLLECTOR = CollectorDefinition(
    "tb_auction",
    "A股集合竞价（网盘）",
    "从百度网盘采集集合竞价过程数据。",
    {item.key: item for item in OPERATIONS},
)
