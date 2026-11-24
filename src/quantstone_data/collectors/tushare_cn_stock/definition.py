from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RateLimit,
    RetryPolicy,
)
from .adj_factor import collect_incremental as collect_adj_factor_incremental
from .adj_factor import collect_initial as collect_adj_factor_initial
from .daily import (
    collect_daily_incremental,
    collect_daily_initial,
)
from .index_basic import collect_incremental as collect_index_basic_incremental
from .index_basic import collect_initial as collect_index_basic_initial
from .index_daily import collect_incremental as collect_index_daily_incremental
from .index_daily import collect_initial as collect_index_daily_initial
from .namechange import collect_incremental as collect_namechange_incremental
from .namechange import collect_initial as collect_namechange_initial
from .stock_basic import (
    collect_incremental as collect_stock_basic_incremental,
)
from .stock_basic import (
    collect_initial as collect_stock_basic_initial,
)
from .stock_st import collect_incremental as collect_stock_st_incremental
from .stock_st import collect_initial as collect_stock_st_initial
from .trade_cal import collect_incremental as collect_trade_cal_incremental
from .trade_cal import collect_initial as collect_trade_cal_initial

DAILY_DATASET_ID = "tushare.cn.stock.daily"
INDEX_BASIC_DATASET_ID = "tushare.cn.index.index_basic"
INDEX_DAILY_DATASET_ID = "tushare.cn.index.index_daily"
ADJ_FACTOR_DATASET_ID = "tushare.cn.stock.adj_factor"
NAMECHANGE_DATASET_ID = "tushare.cn.stock.namechange"
STOCK_BASIC_DATASET_ID = "tushare.cn.stock.stock_basic"
STOCK_ST_DATASET_ID = "tushare.cn.stock.stock_st"
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
# index_daily 每个交易日一次请求；保守限制，避免触发供应商的额度保护。
INDEX_DAILY_RATE_LIMIT = RateLimit(calls=20, period_seconds=60, scope="index_daily")
INDEX_DAILY_RETRY = RetryPolicy(
    attempts=6, delay_seconds=15, max_delay_seconds=120
)
# 当前代理在连续约 180 次请求后返回英文限流提示，保守控制在每分钟 150 次。
ADJ_FACTOR_RATE_LIMIT = RateLimit(calls=150, period_seconds=60, scope="adj_factor")
ADJ_FACTOR_RETRY = RetryPolicy(attempts=5, delay_seconds=5, max_delay_seconds=65)

OPERATIONS = (
    CollectorOperation(
        key="index_basic_initial",
        name="指数基本信息首次采集",
        description="分别获取 TuShare 四个指数市场，建立完整指数基本信息快照。",
        purpose="initial",
        parameters=(),
        datasets=(INDEX_BASIC_DATASET_ID,),
        function=collect_index_basic_initial,
    ),
    CollectorOperation(
        key="index_basic_incremental",
        name="指数基本信息增量更新",
        description="重新获取 TuShare 四个指数市场，替换完整指数基本信息快照。",
        purpose="incremental",
        parameters=(),
        datasets=(INDEX_BASIC_DATASET_ID,),
        function=collect_index_basic_incremental,
    ),
    CollectorOperation(
        key="index_daily_initial",
        name="指数日线首次采集",
        description="按年批量拉取主要指数日线，再逐日写入历史分区。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(INDEX_DAILY_DATASET_ID,),
        function=collect_index_daily_initial,
        retry=INDEX_DAILY_RETRY,
    ),
    CollectorOperation(
        key="index_daily_incremental",
        name="指数日线增量更新",
        description="从数据集当前水位之后补充主要指数日线。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(INDEX_DAILY_DATASET_ID,),
        function=collect_index_daily_incremental,
        rate_limit=INDEX_DAILY_RATE_LIMIT,
        retry=INDEX_DAILY_RETRY,
    ),
    CollectorOperation(
        key="index_daily_repair",
        name="指数日线修复",
        description="按年批量重新拉取指定日期范围的主要指数日线，替换受影响分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(INDEX_DAILY_DATASET_ID,),
        function=collect_index_daily_initial,
        retry=INDEX_DAILY_RETRY,
    ),
    CollectorOperation(
        key="adj_factor_initial",
        name="复权因子首次采集",
        description="按交易日首次采集 TuShare adj_factor 历史数据。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(ADJ_FACTOR_DATASET_ID,),
        function=collect_adj_factor_initial,
        rate_limit=ADJ_FACTOR_RATE_LIMIT,
        retry=ADJ_FACTOR_RETRY,
    ),
    CollectorOperation(
        key="adj_factor_incremental",
        name="复权因子增量更新",
        description="从数据集当前水位之后补充 TuShare adj_factor 每日数据。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(ADJ_FACTOR_DATASET_ID,),
        function=collect_adj_factor_incremental,
        rate_limit=ADJ_FACTOR_RATE_LIMIT,
        retry=ADJ_FACTOR_RETRY,
    ),
    CollectorOperation(
        key="namechange_initial",
        name="股票曾用名首次采集",
        description="获取 TuShare namechange 全部历史记录，建立完整快照。",
        purpose="initial",
        parameters=(),
        datasets=(NAMECHANGE_DATASET_ID,),
        function=collect_namechange_initial,
    ),
    CollectorOperation(
        key="namechange_incremental",
        name="股票曾用名增量更新",
        description="重新获取 TuShare namechange 全部历史记录，替换完整快照。",
        purpose="incremental",
        parameters=(),
        datasets=(NAMECHANGE_DATASET_ID,),
        function=collect_namechange_incremental,
    ),
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
        key="stock_st_initial",
        name="ST 股票列表首次采集",
        description="按交易日首次采集 TuShare stock_st 历史每日列表。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(STOCK_ST_DATASET_ID,),
        function=collect_stock_st_initial,
        rate_limit=DAILY_RATE_LIMIT,
    ),
    CollectorOperation(
        key="stock_st_incremental",
        name="ST 股票列表增量更新",
        description="从数据集当前水位之后补充 TuShare stock_st 每日列表。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(STOCK_ST_DATASET_ID,),
        function=collect_stock_st_incremental,
        rate_limit=DAILY_RATE_LIMIT,
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
