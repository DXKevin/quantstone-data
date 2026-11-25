from ......reviewer_types import ReviewerDefinition
from .reviewer import review

REVIEWER = ReviewerDefinition(
    dataset_id="tb_lhsjk.cn.stock.auction_process",
    function=review,
)
