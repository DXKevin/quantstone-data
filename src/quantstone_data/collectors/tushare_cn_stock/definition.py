from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RateLimit,
)
from .daily import (
    collect_daily_incremental,
    collect_daily_initial,
)
from .stock_basic import (
    collect_incremental as collect_stock_basic_incremental,
)
from .stock_basic import (
    collect_initial as collect_stock_basic_initial,
)
from .trade_cal import collect_incremental as collect_trade_cal_incremental
from .trade_cal import collect_initial as collect_trade_cal_initial

DAILY_DATASET_ID = "tushare.cn.stock.daily"
STOCK_BASIC_DATASET_ID = "tushare.cn.stock.stock_basic"
TRADE_CAL_DATASET_ID = "tushare.cn.stock.trade_cal"

DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)

INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选的更新截止日期，默认当天"),
)

# TuShare daily 按账号限制每分钟 50 次；首次与增量共用同一窗口。
DAILY_RATE_LIMIT = RateLimit(calls=50, period_seconds=60, scope="daily")

OPERATIONS = (
    CollectorOperation(
        key="stock_basic_initial",
        name="股票列表首次采集",
        description="分别获取上市、退市和暂停上市股票，建立完整股票列表快照。",
        purpose="initial",
        parameters=(),
        datasets=(STOCK_BASIC_DATASET_ID,),
        function=collect_stock_basic_initial,
    ),
    CollectorOperation(
        key="stock_basic_incremental",
        name="股票列表增量更新",
        description="重新获取上市、退市和暂停上市股票，替换完整股票列表快照。",
        purpose="incremental",
        parameters=(),
        datasets=(STOCK_BASIC_DATASET_ID,),
        function=collect_stock_basic_incremental,
    ),
    CollectorOperation(
        key="daily_initial",
        name="日 K 首次采集",
        description="按交易日批次首次采集 TuShare daily 数据。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_initial,
        rate_limit=DAILY_RATE_LIMIT,
    ),
    CollectorOperation(
        key="daily_incremental",
        name="日 K 增量更新",
        description="从数据集当前水位之后开始补充 TuShare daily 数据。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_incremental,
        rate_limit=DAILY_RATE_LIMIT,
    ),
    CollectorOperation(
        key="trade_cal_initial",
        name="交易日历首次采集",
        description="按日期范围采集 TuShare 上交所交易日历并生成完整快照。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(TRADE_CAL_DATASET_ID,),
        function=collect_trade_cal_initial,
    ),
    CollectorOperation(
        key="trade_cal_incremental",
        name="交易日历增量更新",
        description="重新生成 TuShare 上交所交易日历完整快照。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(TRADE_CAL_DATASET_ID,),
        function=collect_trade_cal_incremental,
    ),
)

COLLECTOR = CollectorDefinition(
    key="tushare_cn_stock",
    name="TuShare A股采集器",
    description="通过 TuShare Pro API 采集中国内地 A 股数据。",
    operations={operation.key: operation for operation in OPERATIONS},
)
