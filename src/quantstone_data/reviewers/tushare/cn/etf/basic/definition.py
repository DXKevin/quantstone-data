from ......reviewer_types import ReviewerDefinition
from .reviewer import review

REVIEWER = ReviewerDefinition(
    dataset_id="tushare.cn.etf.basic",
    function=review,
)
