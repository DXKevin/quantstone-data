from __future__ import annotations

import re

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_primary_key,
    check_required_fields,
)

CODE_RE = re.compile(r"^\d{6}[A-Z]?\.(SH|SZ|OF)$")
STATUSES = {"L", "D", "P"}
EXCHANGES = {"SH", "SZ"}


def _check_domain(table) -> list[dict]:
    errors: list[dict] = []
    if "ts_code" in table.column_names:
        invalid = [
            value
            for value in table["ts_code"].to_pylist()
            if not isinstance(value, str) or not CODE_RE.fullmatch(value)
        ]
        if invalid:
            errors.append({"rule": "ts_code_format", "count": len(invalid), "sample": invalid[:5]})
    if "list_status" in table.column_names:
        invalid = [
            value
            for value in table["list_status"].to_pylist()
            if value not in STATUSES
        ]
        if invalid:
            errors.append({"rule": "list_status_domain", "count": len(invalid)})
    if "exchange" in table.column_names:
        invalid = [
            value for value in table["exchange"].to_pylist() if value not in EXCHANGES
        ]
        if invalid:
            errors.append({"rule": "exchange_domain", "count": len(invalid)})
    return errors


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *_check_domain(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.etf.etf_basic",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
