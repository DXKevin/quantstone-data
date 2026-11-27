from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
    RateLimit,
    RetryPolicy,
)
from .constituent_stocks import DATASET_ID as CONSTITUENT_DATASET_ID
from .constituent_stocks import collect_incremental as collect_constituent_incremental
from .constituent_stocks import collect_initial as collect_constituent_initial
from .daily import DATASET_ID as DAILY_DATASET_ID
from .daily import collect_incremental as collect_daily_incremental
from .daily import collect_initial as collect_daily_initial
from .minute_1m import DATASET_ID as MINUTE_1M_DATASET_ID
from .minute_1m import collect_incremental as collect_minute_1m_incremental
from .minute_1m import collect_initial as collect_minute_1m_initial
from .sector_categories import (
    DATASET_ID,
    collect_incremental,
    collect_initial,
    load_api_key,
)

RATE_LIMIT = RateLimit(calls=30, period_seconds=60, scope="ths_index")
RETRY = RetryPolicy(attempts=5, delay_seconds=5, max_delay_seconds=60)
DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)
INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选的更新截止日期，默认当天"),
)

OPERATIONS = (
    CollectorOperation(
        key="sector_categories_initial",
        name="THS 板块分类首次采集",
        description="分页获取全部 THS 板块分类，建立完整快照。",
        purpose="initial",
        parameters=(),
        datasets=(DATASET_ID,),
        function=collect_initial,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="sector_categories_incremental",
        name="THS 板块分类更新",
        description="重新获取全部 THS 板块分类并替换完整快照。",
        purpose="incremental",
        parameters=(),
        datasets=(DATASET_ID,),
        function=collect_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="daily_initial",
        name="THS 板块日线首次采集",
        description="按交易日首次采集全部可用 THS 板块日线。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_initial,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="daily_incremental",
        name="THS 板块日线增量更新",
        description="从当前水位之后按交易日补充 THS 板块日线。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="daily_repair",
        name="THS 板块日线修复",
        description="重新采集指定日期范围并替换受影响的日分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="minute_1m_initial",
        name="THS 板块1分钟K首次采集",
        description="按交易日批量采集全部可用 THS 板块1分钟K。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(MINUTE_1M_DATASET_ID,),
        function=collect_minute_1m_initial,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="minute_1m_incremental",
        name="THS 板块1分钟K增量更新",
        description="从当前水位之后按交易日补充 THS 板块1分钟K。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(MINUTE_1M_DATASET_ID,),
        function=collect_minute_1m_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="minute_1m_repair",
        name="THS 板块1分钟K修复",
        description="重新采集指定日期范围并替换受影响的日分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(MINUTE_1M_DATASET_ID,),
        function=collect_minute_1m_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="constituent_stocks_initial",
        name="THS 板块成分股首次采集",
        description="按交易日展开 THS 板块历史成分，一行一只股票。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(CONSTITUENT_DATASET_ID,),
        function=collect_constituent_initial,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="constituent_stocks_incremental",
        name="THS 板块成分股增量更新",
        description="从当前水位之后补充 THS 板块每日成分股。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(CONSTITUENT_DATASET_ID,),
        function=collect_constituent_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
    CollectorOperation(
        key="constituent_stocks_repair",
        name="THS 板块成分股修复",
        description="按交易日重新采集并替换 THS 板块成分股分区。",
        purpose="repair",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(CONSTITUENT_DATASET_ID,),
        function=collect_constituent_incremental,
        rate_limit=RATE_LIMIT,
        retry=RETRY,
    ),
)

COLLECTOR = CollectorDefinition(
    key="tb_lqsj_ths_index",
    name="THS 板块数据采集器",
    description="通过 tb_lqsj_ths 数据产品接口采集 THS 板块数据。",
    operations={operation.key: operation for operation in OPERATIONS},
    credential_loader=load_api_key,
)
