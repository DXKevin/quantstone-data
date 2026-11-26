from __future__ import annotations

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)

TYPES = {"S", "R"}


def _check_domain(table) -> list[dict]:
    errors: list[dict] = []
    if "suspend_type" in table.column_names:
        invalid = [
            value
            for value in table["suspend_type"].to_pylist()
            if value not in TYPES
        ]
        if invalid:
            errors.append({"rule": "suspend_type_domain", "count": len(invalid)})
    return errors


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_domain(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.stock.suspend_d",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
