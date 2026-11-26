from ...collector_types import CollectorDefinition, CollectorOperation, RateLimit, RetryPolicy
from .sector_categories import (
    DATASET_ID,
    collect_incremental,
    collect_initial,
    load_api_key,
)

RATE_LIMIT = RateLimit(calls=30, period_seconds=60, scope="ths_index")
RETRY = RetryPolicy(attempts=5, delay_seconds=5, max_delay_seconds=60)

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
)

COLLECTOR = CollectorDefinition(
    key="tb_lqsj_ths_index",
    name="THS 板块数据采集器",
    description="通过 tb_lqsj_ths 数据产品接口采集 THS 板块数据。",
    operations={operation.key: operation for operation in OPERATIONS},
    credential_loader=load_api_key,
)
