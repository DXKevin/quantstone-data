from ...collector_types import (
    CollectorDefinition,
    CollectorOperation,
    CollectorParameter,
)
from .daily import (
    collect_daily_incremental,
    collect_daily_initial,
)
from .stock_basic import (
    collect_incremental as collect_stock_list_incremental,
)
from .stock_basic import (
    collect_initial as collect_stock_list_initial,
)

DAILY_DATASET_ID = "tushare.cn.stock.daily"
STOCK_LIST_DATASET_ID = "tushare.cn.stock.stock_basic"

DATE_RANGE_PARAMETERS = (
    CollectorParameter("start_date", "date", True, "采集开始日期"),
    CollectorParameter("end_date", "date", True, "采集结束日期"),
)

INCREMENTAL_PARAMETERS = (
    CollectorParameter("end_date", "date", False, "可选的更新截止日期，默认当天"),
)

OPERATIONS = (
    CollectorOperation(
        key="stock_list_initial",
        name="股票列表首次采集",
        description="首次调用 TuShare stock_basic 接口建立当前上市股票快照。",
        purpose="initial",
        parameters=(),
        datasets=(STOCK_LIST_DATASET_ID,),
        function=collect_stock_list_initial,
    ),
    CollectorOperation(
        key="stock_list_incremental",
        name="股票列表增量更新",
        description="重新获取 TuShare stock_basic 当前快照，用于更新股票列表。",
        purpose="incremental",
        parameters=(),
        datasets=(STOCK_LIST_DATASET_ID,),
        function=collect_stock_list_incremental,
    ),
    CollectorOperation(
        key="daily_initial",
        name="日 K 首次采集",
        description="按交易日批次首次采集 TuShare daily 数据。",
        purpose="initial",
        parameters=DATE_RANGE_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_initial,
    ),
    CollectorOperation(
        key="daily_incremental",
        name="日 K 增量更新",
        description="从数据集当前水位之后开始补充 TuShare daily 数据。",
        purpose="incremental",
        parameters=INCREMENTAL_PARAMETERS,
        datasets=(DAILY_DATASET_ID,),
        function=collect_daily_incremental,
    ),
)

COLLECTOR = CollectorDefinition(
    key="tushare_cn_stock",
    name="TuShare A股采集器",
    description="通过 TuShare Pro API 采集中国内地 A 股数据。",
    operations={operation.key: operation for operation in OPERATIONS},
)
