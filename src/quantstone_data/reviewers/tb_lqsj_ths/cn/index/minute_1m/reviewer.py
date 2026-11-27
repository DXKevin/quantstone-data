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

INDEX_RE = re.compile(r"^[0-9]{6}[A-Z]?\.TI$")


def _check_codes(table) -> list[dict]:
    if "ths_code" not in table.column_names:
        return []
    invalid = sum(
        not isinstance(value, str) or INDEX_RE.fullmatch(value) is None
        for value in table["ths_code"].to_pylist()
    )
    return [{"rule": "ths_code_format", "invalid_rows": invalid}] if invalid else []


def _check_bar_times(table) -> list[dict]:
    if "bar_time" not in table.column_names:
        return []
    invalid = 0
    for value in table["bar_time"].to_pylist():
        if value is None or not (
            93_100 <= value <= 113_000 or 130_100 <= value <= 150_000
        ):
            invalid += 1
    return [{"rule": "bar_time_session", "invalid_rows": invalid}] if invalid else []


def _check_non_negative(table, field: str) -> list[dict]:
    if field not in table.column_names:
        return []
    invalid = pc.sum(pc.less(table[field], 0)).as_py() or 0
    return (
        [{"rule": "non_negative", "field": field, "invalid_rows": invalid}]
        if invalid
        else []
    )


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_codes(table),
        *_check_bar_times(table),
        *_check_non_negative(table, "volume"),
        *_check_non_negative(table, "amount"),
        *_check_non_negative(table, "turnover_rate"),
    ]
    return ReviewReport(
        reviewer="tb_lqsj_ths.cn.index.minute_1m",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
