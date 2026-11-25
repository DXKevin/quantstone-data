from ......reviewer_types import ReviewerDefinition
from .reviewer import review

REVIEWER = ReviewerDefinition(
    dataset_id="tb_lhsjk_023199.cn.stock.minute_1m",
    function=review,
)
