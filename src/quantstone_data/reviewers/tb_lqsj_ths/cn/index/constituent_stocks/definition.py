from ......reviewer_types import ReviewerDefinition
from .reviewer import review

REVIEWER = ReviewerDefinition(
    dataset_id="tb_lqsj_ths.cn.index.constituent_stocks",
    function=review,
)
