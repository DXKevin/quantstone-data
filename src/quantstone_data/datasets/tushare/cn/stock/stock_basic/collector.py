from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

from .definition import DEFAULT_LIST_STATUSES

API_URL = "https://api.tushare.pro"


class CollectionError(RuntimeError):
    pass


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
        raise CollectionError(body.get("msg") or "TuShare 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def collect(
    target: Path,
    fields: list[str],
    token: str,
    statuses: Iterable[str] = DEFAULT_LIST_STATUSES,
) -> int:
    rows: list[dict] = []
    for list_status in statuses:
        rows.extend(call_api(token, list_status, fields))

    target.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([pa.field(name, pa.string()) for name in fields])
    normalized = [{name: row.get(name) for name in fields} for row in rows]
    pq.write_table(pa.Table.from_pylist(normalized, schema=schema), target, compression="zstd")
    return len(rows)


def collect_initial(target: Path, fields: list[str], token: str) -> int:
    return collect(target, fields, token)


def collect_incremental(target: Path, fields: list[str], token: str) -> int:
    return collect(target, fields, token)
