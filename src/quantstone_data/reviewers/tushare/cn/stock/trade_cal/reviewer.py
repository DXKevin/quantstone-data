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
    if "is_open" in table.column_names:
        values = set(table["is_open"].to_pylist())
        invalid = sorted(value for value in values if value not in {0, 1})
        if invalid:
            errors.append({"rule": "is_open_enum", "invalid": invalid})
    return ReviewReport(
        reviewer="tushare.cn.stock.trade_cal",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
