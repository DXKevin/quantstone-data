import pyarrow.compute as pc
import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)


def _check_positive_factor(table) -> list[dict]:
    if "adj_factor" not in table.column_names or table.num_rows == 0:
        return []
    invalid = pc.any(
        pc.or_(pc.is_null(table["adj_factor"]), pc.less_equal(table["adj_factor"], 0))
    ).as_py()
    return [{"rule": "adj_factor_positive"}] if invalid else []


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_positive_factor(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.stock.adj_factor",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
