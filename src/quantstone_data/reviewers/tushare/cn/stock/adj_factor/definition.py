from ......reviewer_types import ReviewerDefinition
from .reviewer import review

REVIEWER = ReviewerDefinition(
    dataset_id="tushare.cn.stock.adj_factor",
    function=review,
)
