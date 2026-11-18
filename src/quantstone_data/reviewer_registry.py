from .reviewer_types import ReviewContext, ReviewerDefinition, ReviewReport
from .reviewers.tushare.cn.stock.daily import REVIEWER as TUSHARE_DAILY
from .reviewers.tushare.cn.stock.stock_basic import REVIEWER as TUSHARE_STOCK_BASIC
from .reviewers.tushare.cn.stock.trade_cal import REVIEWER as TUSHARE_TRADE_CAL


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


REVIEWERS = _build_registry((TUSHARE_DAILY, TUSHARE_STOCK_BASIC, TUSHARE_TRADE_CAL))


def review_dataset(dataset_id: str, context: ReviewContext) -> ReviewReport:
    reviewer = REVIEWERS.get(dataset_id)
    if reviewer is None:
        raise LookupError(f"reviewer is not registered for dataset: {dataset_id}")
    return reviewer.function(context)
