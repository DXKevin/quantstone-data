import json
from pathlib import Path

import pyarrow.parquet as pq

from ......models import DatasetSchemaVersion


def review(source: Path, schema: DatasetSchemaVersion, report_path: Path) -> bool:
    expected_fields = [field.source_name or field.name for field in schema.fields]
    primary_key = schema.primary_key_fields
    errors: list[dict] = []
    seen_keys: set[tuple[str, ...]] = set()
    table = pq.read_table(source)
    row_count = table.num_rows
    missing = [field for field in expected_fields if field not in table.column_names]
    if missing:
        errors.append({"rule": "required_fields", "missing": missing})
    else:
        for line_number, row in enumerate(table.select(primary_key).to_pylist(), start=1):
            key = tuple((row.get(name) or "").strip() for name in primary_key)
            if any(not value for value in key):
                errors.append({"rule": "primary_key_not_null", "line": line_number})
            elif key in seen_keys:
                errors.append(
                    {"rule": "primary_key_unique", "line": line_number, "key": list(key)}
                )
            seen_keys.add(key)

    if row_count == 0:
        errors.append({"rule": "not_empty"})

    report = {
        "reviewer": "tushare.stock_basic",
        "passed": not errors,
        "row_count": row_count,
        "errors": errors[:100],
        "error_count": len(errors),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return not errors
