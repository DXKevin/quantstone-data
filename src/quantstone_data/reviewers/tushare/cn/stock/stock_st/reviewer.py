import re

import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import (
    check_not_empty,
    check_partition_date,
    check_primary_key,
    check_required_fields,
)

TS_CODE_PATTERN = re.compile(r"^\d{6}\.(?:SH|SZ|BJ)$")


def _check_ts_codes(table) -> list[dict]:
    if "ts_code" not in table.column_names:
        return []
    invalid = [
        value
        for value in table["ts_code"].to_pylist()
        if not TS_CODE_PATTERN.fullmatch(value or "")
    ]
    return (
        [{"rule": "ts_code_format", "count": len(invalid), "examples": invalid[:5]}]
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
        *_check_ts_codes(table),
    ]
    return ReviewReport(
        reviewer="tushare.cn.stock.stock_st",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
