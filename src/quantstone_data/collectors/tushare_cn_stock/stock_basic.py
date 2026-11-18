from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import (
    CollectionContext,
    CollectionResult,
    DatasetArtifact,
    RateLimitExceeded,
)

API_URL = "https://api.tushare.pro"
DEFAULT_LIST_STATUSES = ("L",)
RATE_LIMIT_CODES = {40203, -40203}
RATE_LIMIT_KEYWORDS = ("每分钟", "每小时", "频率", "超过限制", "访问次数")
DEFAULT_RETRY_AFTER = 60.0
DATASET_ID = "tushare.cn.stock.stock_basic"


class CollectionError(RuntimeError):
    pass


def raise_api_error(body: dict, fallback: str) -> NoReturn:
    """把 TuShare 错误响应转换为异常；限流错误单独标记以便重试。"""
    message = body.get("msg") or fallback
    if body.get("code") in RATE_LIMIT_CODES or any(
        keyword in message for keyword in RATE_LIMIT_KEYWORDS
    ):
        raise RateLimitExceeded(message, retry_after=DEFAULT_RETRY_AFTER)
    raise CollectionError(message)


def load_token(project_root: Path | None = None) -> str:
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


def call_api(token: str, list_status: str, fields: list[str]) -> list[dict]:
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
        raise_api_error(body, "TuShare 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def _arrow_type(data_type: str) -> pa.DataType:
    return {
        "string": pa.string(),
        "date": pa.date32(),
        "int32": pa.int32(),
        "int64": pa.int64(),
        "float32": pa.float32(),
        "float64": pa.float64(),
        "boolean": pa.bool_(),
        "timestamp": pa.timestamp("us"),
    }[data_type]


def _convert(value: Any, data_type: str) -> Any:
    if value is None or value == "":
        return None
    if data_type == "date":
        return datetime.strptime(str(value), "%Y%m%d").date()
    if data_type in {"float32", "float64"}:
        return float(value)
    if data_type in {"int32", "int64"}:
        return int(value)
    if data_type == "boolean":
        return bool(value)
    return value


def collect(
    context: CollectionContext,
    field_contracts: list[dict],
    statuses: Iterable[str] = DEFAULT_LIST_STATUSES,
) -> CollectionResult:
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows: list[dict] = []
    for list_status in statuses:
        rows.extend(call_api(context.token, list_status, source_fields))

    normalized = [
        {
            field["name"]: _convert(
                row.get(field.get("source_name") or field["name"]), field["data_type"]
            )
            for field in field_contracts
        }
        for row in rows
    ]
    primary_sort = "ts_code" if any(item["name"] == "ts_code" for item in field_contracts) else None
    if primary_sort:
        normalized.sort(key=lambda row: row[primary_sort] or "")
    schema = pa.schema(
        [
            pa.field(field["name"], _arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / "stock_basic.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    artifact = DatasetArtifact(DATASET_ID, target, {}, table.num_rows)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={"api": "stock_basic", "list_statuses": list(statuses)},
    )


def collect_initial(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)


def collect_incremental(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)
