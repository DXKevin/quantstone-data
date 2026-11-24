import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import check_not_empty, check_primary_key, check_required_fields


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
    ]
    return ReviewReport(
        reviewer="tushare.cn.index.index_basic",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
