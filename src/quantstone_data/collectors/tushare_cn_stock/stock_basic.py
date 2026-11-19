from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import (
    CollectionContext,
    CollectionResult,
    DatasetArtifact,
    RateLimitExceeded,
)

DEFAULT_API_URL = "https://api.tushare.pro"
# TuShare stock_basic 需要分别请求三种状态；空值不会稳定返回完整股票范围。
DEFAULT_LIST_STATUSES = ("L", "D", "P")
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


def _load_setting(name: str, project_root: Path | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    env_path = (project_root or Path.cwd()) / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip()
    return None


def load_token(project_root: Path | None = None) -> str:
    token = _load_setting("TUSHARE_TOKEN", project_root)
    if token:
        return token
    raise CollectionError("未配置 TUSHARE_TOKEN")


def load_api_url(project_root: Path | None = None) -> str:
    url = _load_setting("TUSHARE_API_URL", project_root) or DEFAULT_API_URL
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CollectionError("TUSHARE_API_URL 必须是有效的 http 或 https 地址")
    if parsed.username or parsed.password:
        raise CollectionError("TUSHARE_API_URL 不能包含用户名或密码")
    return url


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
        load_api_url(),
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
    if data_type == "string":
        return str(value)
    if data_type == "date":
        return datetime.strptime(str(value), "%Y%m%d").date()
    if data_type in {"float32", "float64"}:
        return float(value)
    if data_type in {"int32", "int64"}:
        return int(value)
    if data_type == "boolean":
        return bool(value)
    return value


def _source_value(row: dict, field: dict) -> Any:
    source_name = field.get("source_name") or field["name"]
    value = row.get(source_name)
    # 部分兼容 TuShare 的代理会把退市股票 symbol 经 DataFrame 序列化成 float，
    # 直接转换既会留下“.0”，也会丢失代码前导零。ts_code 中保留了原始代码。
    if source_name == "symbol" and not isinstance(value, str):
        ts_code = row.get("ts_code")
        if isinstance(ts_code, str) and "." in ts_code:
            return ts_code.split(".", 1)[0]
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
                _source_value(row, field), field["data_type"]
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
        provenance={
            "api": "stock_basic",
            "api_url": load_api_url(),
            "list_statuses": list(statuses),
        },
    )


def collect_initial(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)


def collect_incremental(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)
