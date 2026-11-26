from __future__ import annotations

import re

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)

INDEX_RE = re.compile(r"^\d{6}\.TI$")
STOCK_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def _check_codes(table) -> list[dict]:
    errors: list[dict] = []
    if "index_code" in table.column_names:
        invalid = [
            value
            for value in table["index_code"].to_pylist()
            if not INDEX_RE.fullmatch(str(value or ""))
        ]
        if invalid:
            errors.append({"rule": "index_code_format", "count": len(invalid)})
    if "stock_code" in table.column_names:
        invalid = [
            value
            for value in table["stock_code"].to_pylist()
            if not STOCK_RE.fullmatch(str(value or ""))
        ]
        if invalid:
            errors.append({"rule": "stock_code_format", "count": len(invalid)})
    return errors


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
        *check_partition_date(table, context.schema, context.expected_partition),
        *_check_codes(table),
    ]
    return ReviewReport(
        reviewer="tb_lqsj_ths.cn.index.constituent_stocks",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
