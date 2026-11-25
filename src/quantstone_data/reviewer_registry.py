from .reviewer_types import ReviewContext, ReviewerDefinition, ReviewReport
from .reviewers.tb_lhsjk.cn.stock.auction_process import REVIEWER as TB_AUCTION_PROCESS
from .reviewers.tb_sbkj2077.cn.stock.minute_1m import REVIEWER as TB_MINUTE_1M
from .reviewers.tushare.cn.index.index_basic import REVIEWER as TUSHARE_INDEX_BASIC
from .reviewers.tushare.cn.index.index_daily import REVIEWER as TUSHARE_INDEX_DAILY
from .reviewers.tushare.cn.stock.adj_factor import REVIEWER as TUSHARE_ADJ_FACTOR
from .reviewers.tushare.cn.stock.daily import REVIEWER as TUSHARE_DAILY
from .reviewers.tushare.cn.stock.namechange import REVIEWER as TUSHARE_NAMECHANGE
from .reviewers.tushare.cn.stock.stock_basic import REVIEWER as TUSHARE_STOCK_BASIC
from .reviewers.tushare.cn.stock.stock_st import REVIEWER as TUSHARE_STOCK_ST
from .reviewers.tushare.cn.stock.trade_cal import REVIEWER as TUSHARE_TRADE_CAL
from .reviewers.wind.l2 import ORDER_REVIEWER as WIND_L2_ORDER
from .reviewers.wind.l2 import TRADE_REVIEWER as WIND_L2_TRADE
from .reviewers.wind.l2 import ZHONGTAI_ORDER_REVIEWER as ZHONGTAI_L2_ORDER
from .reviewers.wind.l2 import ZHONGTAI_TRADE_REVIEWER as ZHONGTAI_L2_TRADE


def _build_registry(
    definitions: tuple[ReviewerDefinition, ...],
) -> dict[str, ReviewerDefinition]:
    registry: dict[str, ReviewerDefinition] = {}
    for reviewer in definitions:
        if reviewer.dataset_id in registry:
            raise RuntimeError(f"duplicate reviewer for dataset: {reviewer.dataset_id}")
        if not callable(reviewer.function):
            raise RuntimeError(f"reviewer is not callable: {reviewer.dataset_id}")
        registry[reviewer.dataset_id] = reviewer
    return registry


REVIEWERS = _build_registry(
    (
        TB_AUCTION_PROCESS,
        TUSHARE_INDEX_BASIC,
        TUSHARE_INDEX_DAILY,
        TB_MINUTE_1M,
        TUSHARE_ADJ_FACTOR,
        TUSHARE_DAILY,
        TUSHARE_NAMECHANGE,
        TUSHARE_STOCK_BASIC,
        TUSHARE_STOCK_ST,
        TUSHARE_TRADE_CAL,
        WIND_L2_ORDER,
        WIND_L2_TRADE,
        ZHONGTAI_L2_ORDER,
        ZHONGTAI_L2_TRADE,
    )
)


def review_dataset(dataset_id: str, context: ReviewContext) -> ReviewReport:
    reviewer = REVIEWERS.get(dataset_id)
    if reviewer is None:
        raise LookupError(f"reviewer is not registered for dataset: {dataset_id}")
    return reviewer.function(context)
