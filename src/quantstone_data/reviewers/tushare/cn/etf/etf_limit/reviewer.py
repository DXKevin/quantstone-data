from __future__ import annotations

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)

EXCHANGES = {"SSE", "SZSE"}


def _check_prices(table) -> list[dict]:
    required = {"up_limit", "down_limit"}
    if not required.issubset(table.column_names):
        return []
    invalid = [
        row
        for row in table.select(sorted(required)).to_pylist()
        if row["up_limit"] is not None
        and row["down_limit"] is not None
        and row["up_limit"] < row["down_limit"]
    ]
    return [{"rule": "limit_order", "count": len(invalid)}] if invalid else []


def _check_exchange(table) -> list[dict]:
    if "exchange" not in table.column_names:
        return []
    invalid = [
        value for value in table["exchange"].to_pylist() if value not in EXCHANGES
    ]
    return [{"rule": "exchange_domain", "count": len(invalid)}] if invalid else []


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_prices(table),
        *_check_exchange(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.etf.etf_limit",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
