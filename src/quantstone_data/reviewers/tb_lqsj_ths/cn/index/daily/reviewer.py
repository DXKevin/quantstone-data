from __future__ import annotations

import re

import pyarrow.compute as pc
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
        if row["high"] < max(values) or row["low"] > min(values):
            return [{"rule": "ohlc_relationship", "line": index}]
    return []


def _check_non_negative(table, field: str) -> list[dict]:
    if field not in table.column_names:
        return []
    invalid = pc.sum(pc.less(table[field], 0)).as_py() or 0
    return (
        [{"rule": "non_negative", "field": field, "invalid_rows": invalid}]
        if invalid
        else []
    )


def _check_codes(table) -> list[dict]:
    if "ths_code" not in table.column_names:
        return []
    invalid = sum(
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]{6}[A-Z]?\.TI", value) is None
        for value in table["ths_code"].to_pylist()
    )
    return [{"rule": "ths_code_suffix", "invalid_rows": invalid}] if invalid else []


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_ohlc(table),
        *_check_non_negative(table, "vol"),
        *_check_non_negative(table, "turnover_rate"),
        *_check_codes(table),
    ]
    return ReviewReport(
        reviewer="tb_lqsj_ths.cn.index.daily",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
