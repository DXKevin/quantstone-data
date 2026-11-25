from __future__ import annotations

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)


def _check_factor(table) -> list[dict]:
    if "adj_factor" not in table.column_names:
        return []
    invalid = [
        value
        for value in table["adj_factor"].to_pylist()
        if value is not None and value <= 0
    ]
    return [{"rule": "adj_factor_positive", "count": len(invalid)}] if invalid else []


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_factor(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.etf.fund_adj",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
