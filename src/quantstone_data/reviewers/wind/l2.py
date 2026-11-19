from __future__ import annotations

from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from ...field_types import arrow_type
from ...models import DatasetSchemaVersion
from ...reviewer_types import ReviewContext, ReviewerDefinition, ReviewReport


def _expected_schema(schema: DatasetSchemaVersion) -> pa.Schema:
    return pa.schema(
        [
            pa.field(field.name, arrow_type(field.data_type), nullable=field.nullable)
            for field in schema.fields
        ]
    )


def _column_index(schema: DatasetSchemaVersion, name: str) -> int | None:
    for index, field in enumerate(schema.fields):
        if field.name == name:
            return index
    return None


def _review(context: ReviewContext, dataset_id: str) -> ReviewReport:
    path = context.artifact_path
    parquet = pq.ParquetFile(path)
    metadata = parquet.metadata
    expected = _expected_schema(context.schema)
    errors: list[dict] = []

    actual_names = parquet.schema_arrow.names
    expected_names = expected.names
    missing = [name for name in expected_names if name not in actual_names]
    extra = [name for name in actual_names if name not in expected_names]
    if missing or extra:
        errors.append({"rule": "schema", "missing": missing, "extra": extra})
    else:
        for field in expected:
            actual_type = parquet.schema_arrow.field(field.name).type
            if actual_type != field.type:
                errors.append(
                    {
                        "rule": "schema",
                        "field": field.name,
                        "expected": str(field.type),
                        "actual": str(actual_type),
                    }
                )

    if metadata.num_rows == 0:
        errors.append({"rule": "not_empty"})

    for index, field in enumerate(context.schema.fields):
        if field.nullable:
            continue
        nulls = 0
        for row_group in range(metadata.num_row_groups):
            statistics = metadata.row_group(row_group).column(index).statistics
            if statistics is not None and statistics.null_count is not None:
                nulls += statistics.null_count
        if nulls:
            rule = (
                "primary_key_not_null"
                if field.name in context.schema.primary_key_fields
                else "required_not_null"
            )
            errors.append(
                {
                    "rule": rule,
                    "field": field.name,
                    "null_count": nulls,
                }
            )

    date_index = _column_index(context.schema, "trade_date")
    if date_index is not None and context.expected_partition is not None:
        actual_dates: set[date] = set()
        for row_group in range(metadata.num_row_groups):
            statistics = metadata.row_group(row_group).column(date_index).statistics
            if statistics is None or statistics.min is None or statistics.max is None:
                actual_dates = set()
                break
            if isinstance(statistics.min, date):
                actual_dates.add(statistics.min)
                actual_dates.add(statistics.max)
            else:
                actual_dates = set()
                break
        if actual_dates and actual_dates != {context.expected_partition}:
            errors.append(
                {
                    "rule": "partition_matches_trade_date",
                    "expected": context.expected_partition.isoformat(),
                    "actual": sorted(item.isoformat() for item in actual_dates),
                }
            )
        elif not actual_dates:
            column = pq.read_table(path, columns=["trade_date"])["trade_date"]
            values = set(column.to_pylist())
            if values != {context.expected_partition}:
                errors.append(
                    {
                        "rule": "partition_matches_trade_date",
                        "expected": context.expected_partition.isoformat(),
                        "actual": sorted(
                            item.isoformat() if item else None for item in values
                        ),
                    }
                )

    return ReviewReport(
        reviewer=dataset_id,
        passed=not errors,
        row_count=metadata.num_rows,
        errors=tuple(errors),
    )


ORDER_REVIEWER = ReviewerDefinition(
    dataset_id="wind.cn.stock.l2_order.sz",
    function=lambda context: _review(context, "wind.cn.stock.l2_order.sz"),
)
TRADE_REVIEWER = ReviewerDefinition(
    dataset_id="wind.cn.stock.l2_trade.sz",
    function=lambda context: _review(context, "wind.cn.stock.l2_trade.sz"),
)
ZHONGTAI_ORDER_REVIEWER = ReviewerDefinition(
    dataset_id="zhongtai.cn.stock.l2_order.sz",
    function=lambda context: _review(context, "zhongtai.cn.stock.l2_order.sz"),
)
ZHONGTAI_TRADE_REVIEWER = ReviewerDefinition(
    dataset_id="zhongtai.cn.stock.l2_trade.sz",
    function=lambda context: _review(context, "zhongtai.cn.stock.l2_trade.sz"),
)
