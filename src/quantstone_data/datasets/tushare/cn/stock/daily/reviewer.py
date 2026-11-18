from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from ......models import DatasetSchemaVersion


def review_daily(path: Path, schema: DatasetSchemaVersion, expected_date: date) -> dict:
    table = pq.ParquetFile(path).read()
    errors: list[dict] = []
    expected_fields = [field.name for field in schema.fields]
    missing = [name for name in expected_fields if name not in table.column_names]
    if missing:
        errors.append({"rule": "required_fields", "missing": missing})
    if table.num_rows == 0:
        errors.append({"rule": "not_empty"})

    if not missing:
        rows = table.select(schema.primary_key_fields).to_pylist()
        keys = [tuple(row[name] for name in schema.primary_key_fields) for row in rows]
        if any(any(value is None for value in key) for key in keys):
            errors.append({"rule": "primary_key_not_null"})
        if len(keys) != len(set(keys)):
            errors.append({"rule": "primary_key_unique"})

        if schema.time_field and schema.time_field in table.column_names:
            dates = set(table[schema.time_field].to_pylist())
            if dates != {expected_date}:
                errors.append(
                    {
                        "rule": "partition_matches_trade_date",
                        "expected": expected_date.isoformat(),
                        "actual": [item.isoformat() if item else None for item in dates],
                    }
                )

    return {
        "reviewer": "tushare.daily",
        "passed": not errors,
        "row_count": table.num_rows,
        "errors": errors,
        "error_count": len(errors),
    }
