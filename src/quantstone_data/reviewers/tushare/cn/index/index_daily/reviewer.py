from __future__ import annotations

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)


def _check_ohlc(table) -> list[dict]:
    required = {"open", "high", "low", "close"}
    if not required.issubset(table.column_names):
        return []
    for index, row in enumerate(table.select(sorted(required)).to_pylist(), start=1):
        values = [row[name] for name in required]
        if any(value is None for value in values):
            continue
        if row["high"] < max(row["open"], row["close"], row["low"]):
            return [{"rule": "ohlc_relationship", "line": index}]
        if row["low"] > min(row["open"], row["close"], row["high"]):
            return [{"rule": "ohlc_relationship", "line": index}]
    return []


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_ohlc(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.index.index_daily",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
