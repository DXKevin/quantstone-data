from __future__ import annotations

from datetime import date

import pyarrow.parquet as pq

from ......field_types import arrow_type
from ......reviewer_types import ReviewContext, ReviewReport


def _column_index(context: ReviewContext, name: str) -> int | None:
    for index, field in enumerate(context.schema.fields):
        if field.name == name:
            return index
    return None


def review(context: ReviewContext) -> ReviewReport:
    parquet = pq.ParquetFile(context.artifact_path)
    metadata = parquet.metadata
    expected = {
        field.name: arrow_type(field.data_type) for field in context.schema.fields
    }
    errors: list[dict] = []
    actual_names = parquet.schema_arrow.names
    missing = [name for name in expected if name not in actual_names]
    extra = [name for name in actual_names if name not in expected]
    if missing or extra:
        errors.append({"rule": "schema", "missing": missing, "extra": extra})
    else:
        for name, data_type in expected.items():
            actual_type = parquet.schema_arrow.field(name).type
            if actual_type != data_type:
                errors.append(
                    {
                        "rule": "schema",
                        "field": name,
                        "expected": str(data_type),
                        "actual": str(actual_type),
                    }
                )

    if metadata.num_rows == 0:
        errors.append({"rule": "not_empty"})

    for field in context.schema.fields:
        if field.nullable:
            continue
        index = _column_index(context, field.name)
        if index is None:
            continue
        nulls = sum(
            (metadata.row_group(group).column(index).statistics.null_count or 0)
            for group in range(metadata.num_row_groups)
            if metadata.row_group(group).column(index).statistics is not None
        )
        if nulls:
            errors.append({"rule": "required_not_null", "field": field.name, "null_count": nulls})

    date_index = _column_index(context, "trade_date")
    if date_index is not None and context.expected_partition is not None:
        values: set[date] = set()
        for group in range(metadata.num_row_groups):
            stats = metadata.row_group(group).column(date_index).statistics
            if stats is None or stats.min is None or stats.max is None:
                values = set()
                break
            if isinstance(stats.min, date):
                values.add(stats.min)
                values.add(stats.max)
        if values and values != {context.expected_partition}:
            errors.append(
                {
                    "rule": "partition_matches_trade_date",
                    "expected": context.expected_partition.isoformat(),
                    "actual": sorted(item.isoformat() for item in values),
                }
            )

    bar_index = _column_index(context, "bar_time")
    if bar_index is not None:
        for group in range(metadata.num_row_groups):
            stats = metadata.row_group(group).column(bar_index).statistics
            if stats is None or stats.min is None:
                continue
            if stats.min < 93000 or stats.max > 150000:
                errors.append(
                    {
                        "rule": "bar_time_range",
                        "min": stats.min,
                        "max": stats.max,
                    }
                )
                break

    return ReviewReport(
        reviewer="tb_minute.cn.stock.minute_1m",
        passed=not errors,
        row_count=metadata.num_rows,
        errors=tuple(errors),
    )
