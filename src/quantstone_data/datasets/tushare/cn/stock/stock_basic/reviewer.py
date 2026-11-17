import csv
import json
from pathlib import Path

from ......models import DatasetSchemaVersion


def review(source: Path, schema: DatasetSchemaVersion, report_path: Path) -> bool:
    expected_fields = [field.source_name or field.name for field in schema.fields]
    primary_key = schema.primary_key_fields
    errors: list[dict] = []
    seen_keys: set[tuple[str, ...]] = set()
    row_count = 0

    with source.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        actual_fields = reader.fieldnames or []
        missing = [field for field in expected_fields if field not in actual_fields]
        if missing:
            errors.append({"rule": "required_fields", "missing": missing})

        for line_number, row in enumerate(reader, start=2):
            row_count += 1
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
