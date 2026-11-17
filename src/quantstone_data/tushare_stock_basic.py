from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable
from pathlib import Path
from urllib.request import Request, urlopen

from .models import DatasetSchemaVersion

API_URL = "https://api.tushare.pro"
# 首版按 TuShare 官方默认范围采集当前上市股票。其他状态将在任务参数模型完成后开放，
# 避免低频率账号在一个同步任务中连续请求而触发供应商限流。
LIST_STATUSES = ("L",)


class CollectionError(RuntimeError):
    pass


def load_tushare_token(project_root: Path | None = None) -> str:
    token = os.environ.get("TUSHARE_TOKEN")
    if token:
        return token
    env_path = (project_root or Path.cwd()) / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "TUSHARE_TOKEN" and value.strip():
                return value.strip()
    raise CollectionError("未配置 TUSHARE_TOKEN")


def call_stock_basic(token: str, list_status: str, fields: list[str]) -> list[dict]:
    payload = json.dumps(
        {
            "api_name": "stock_basic",
            "token": token,
            "params": {"exchange": "", "list_status": list_status},
            "fields": ",".join(fields),
        }
    ).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310
        body = json.load(response)
    if body.get("code") != 0:
        raise CollectionError(body.get("msg") or "TuShare 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def collect_stock_basic(
    target: Path,
    fields: list[str],
    token: str,
    statuses: Iterable[str] = LIST_STATUSES,
) -> int:
    rows: list[dict] = []
    for list_status in statuses:
        rows.extend(call_stock_basic(token, list_status, fields))

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def review_stock_basic(source: Path, schema: DatasetSchemaVersion, report_path: Path) -> bool:
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
