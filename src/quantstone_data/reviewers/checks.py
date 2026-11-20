from datetime import date

import pyarrow as pa

from ..models import DatasetSchemaVersion


def check_required_fields(table: pa.Table, schema: DatasetSchemaVersion) -> list[dict]:
    expected = [field.name for field in schema.fields]
    missing = [name for name in expected if name not in table.column_names]
    return [{"rule": "required_fields", "missing": missing}] if missing else []


def check_not_empty(table: pa.Table) -> list[dict]:
    return [{"rule": "not_empty"}] if table.num_rows == 0 else []


def check_primary_key(table: pa.Table, schema: DatasetSchemaVersion) -> list[dict]:
    fields = schema.primary_key_fields
    if any(field not in table.column_names for field in fields):
        return []
    keys = [tuple(row[field] for field in fields) for row in table.select(fields).to_pylist()]
    errors: list[dict] = []
    if any(any(value is None or value == "" for value in key) for key in keys):
        errors.append({"rule": "primary_key_not_null"})
    if len(keys) != len(set(keys)):
        errors.append({"rule": "primary_key_unique"})
    return errors


def check_partition_date(
    table: pa.Table,
    schema: DatasetSchemaVersion,
    expected: date | None,
) -> list[dict]:
    if expected is None or not schema.time_field or schema.time_field not in table.column_names:
        return []
    actual = set(table[schema.time_field].to_pylist())
    if not actual:
        return []
    if actual == {expected}:
        return []
    return [
        {
            "rule": "partition_matches_trade_date",
            "expected": expected.isoformat(),
            "actual": [item.isoformat() if item else None for item in actual],
        }
    ]
