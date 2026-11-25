from ...collector_types import CollectorDefinition, CollectorOperation, RateLimit
from .etf_basic import collect_incremental, collect_initial

DATASET_ID = "tushare.cn.etf.basic"
RATE_LIMIT = RateLimit(calls=100, period_seconds=60, scope="etf_basic")

OPERATIONS = (
    CollectorOperation(
        key="etf_basic_initial",
        name="ETF基础信息首次采集",
        description="分别获取上市、退市、待上市 ETF，建立完整基础信息快照。",
        purpose="initial",
        parameters=(),
        datasets=(DATASET_ID,),
        function=collect_initial,
        rate_limit=RATE_LIMIT,
    ),
    CollectorOperation(
        key="etf_basic_incremental",
        name="ETF基础信息增量更新",
        description="重新获取上市、退市、待上市 ETF，替换完整基础信息快照。",
        purpose="incremental",
        parameters=(),
        datasets=(DATASET_ID,),
        function=collect_incremental,
        rate_limit=RATE_LIMIT,
    ),
)

COLLECTOR = CollectorDefinition(
    key="tushare_cn_etf",
    name="TuShare ETF 采集器",
    description="通过 TuShare Pro API 采集国内 ETF 基础信息。",
    operations={operation.key: operation for operation in OPERATIONS},
)
