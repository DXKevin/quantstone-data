from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RateLimit,
)
from .etf_basic import collect_incremental, collect_initial
from .fund_daily import collect_incremental as collect_fund_daily_incremental
from .fund_daily import collect_initial as collect_fund_daily_initial

BASIC_DATASET_ID = "tushare.cn.etf.basic"
FUND_DAILY_DATASET_ID = "tushare.cn.etf.fund_daily"
RATE_LIMIT = RateLimit(calls=100, period_seconds=60, scope="etf_basic")
FUND_DAILY_RATE_LIMIT = RateLimit(calls=50, period_seconds=60, scope="fund_daily")
DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)
INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选的更新截止日期，默认当天"),
)

OPERATIONS = (
    CollectorOperation(
        key="etf_basic_initial",
        name="ETF基础信息首次采集",
        description="分别获取上市、退市、待上市 ETF，建立完整基础信息快照。",
        purpose="initial",
        parameters=(),
        datasets=(BASIC_DATASET_ID,),
        function=collect_initial,
        rate_limit=RATE_LIMIT,
    ),
    CollectorOperation(
        key="etf_basic_incremental",
        name="ETF基础信息增量更新",
        description="重新获取上市、退市、待上市 ETF，替换完整基础信息快照。",
        purpose="incremental",
        parameters=(),
        datasets=(BASIC_DATASET_ID,),
        function=collect_incremental,
        rate_limit=RATE_LIMIT,
    ),
    CollectorOperation(
        key="fund_daily_initial",
        name="场内基金日线首次采集",
        description="按交易日首次采集 TuShare fund_daily 场内基金日线行情。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(FUND_DAILY_DATASET_ID,),
        function=collect_fund_daily_initial,
        rate_limit=FUND_DAILY_RATE_LIMIT,
    ),
    CollectorOperation(
        key="fund_daily_incremental",
        name="场内基金日线增量更新",
        description="从数据集当前水位之后补充 TuShare fund_daily 数据。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(FUND_DAILY_DATASET_ID,),
        function=collect_fund_daily_incremental,
        rate_limit=FUND_DAILY_RATE_LIMIT,
    ),
    CollectorOperation(
        key="fund_daily_repair",
        name="场内基金日线修复",
        description="按交易日重新采集指定日期范围的 fund_daily 数据，替换受影响分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(FUND_DAILY_DATASET_ID,),
        function=collect_fund_daily_incremental,
        rate_limit=FUND_DAILY_RATE_LIMIT,
    ),
)

COLLECTOR = CollectorDefinition(
    key="tushare_cn_etf",
    name="TuShare ETF 采集器",
    description="通过 TuShare Pro API 采集国内 ETF 基础信息。",
    operations={operation.key: operation for operation in OPERATIONS},
)
