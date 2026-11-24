from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...collector_types import RateLimit
from ...execution import RateLimiter
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .stock_basic import CollectionError, load_api_url, raise_api_error

DATASET_ID = "tushare.cn.index.index_daily"
UNIVERSE_PATH = Path(__file__).with_name("index_daily_universe.json")
CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|CSI|BJ)$")

# 首次采集按年缓存；每次只发两组请求（非 CSI / CSI），每年最多 2 次。
YEAR_CACHE_TTL_SECONDS = 3600
_YEAR_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_YEAR_CACHE_LOCK = threading.Lock()
_YEAR_RATE_LIMIT = RateLimiter(RateLimit(calls=15, period_seconds=60, scope="index_daily_year"))


@dataclass(frozen=True)
class IndexDefinition:
    ts_code: str
    name: str
    start_date: date


def load_index_universe(path: Path = UNIVERSE_PATH) -> tuple[IndexDefinition, ...]:
    """读取并校验指数清单；新增指数只改 JSON，不写死在采集函数里。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CollectionError(f"指数清单不存在：{path}") from error
    except json.JSONDecodeError as error:
        raise CollectionError(f"指数清单不是合法 JSON：{path}") from error

    indices = payload.get("indices") if isinstance(payload, dict) else None
    if not isinstance(indices, list) or not indices:
        raise CollectionError("指数清单 indices 必须是非空数组")
    definitions: list[IndexDefinition] = []
    names: dict[str, str] = {}
    for item in indices:
        if not isinstance(item, dict):
            raise CollectionError("指数清单每项必须是对象")
        code = item.get("ts_code")
        name = item.get("name")
        start_text = item.get("start_date")
        if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
            raise CollectionError(f"非法指数代码：{code!r}")
        if not isinstance(name, str) or not name.strip():
            raise CollectionError(f"指数 {code} 缺少名称")
        if not isinstance(start_text, str):
            raise CollectionError(f"指数 {code} 缺少 start_date")
        try:
            start_date = date.fromisoformat(start_text)
        except ValueError as error:
            raise CollectionError(f"指数 {code} start_date 非法：{start_text}") from error
        if code in names:
            raise CollectionError(f"指数代码重复：{code}")
        names[code] = name.strip()
        definitions.append(IndexDefinition(code, name.strip(), start_date))
    return tuple(definitions)


def call_api(
    token: str,
    trade_date: str,
    fields: list[str],
) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "index_daily",
            "token": token,
            "params": {"trade_date": trade_date},
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare index_daily 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def call_range_api(
    token: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    fields: list[str],
) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "index_daily",
            "token": token,
            "params": {
                "ts_code": ",".join(codes),
                "start_date": start_date,
                "end_date": end_date,
            },
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare index_daily 区间调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def _load_year(token: str, year: int, fields: list[str]) -> list[dict]:
    cache_key = (token, year)
    now = time.monotonic()
    with _YEAR_CACHE_LOCK:
        cached = _YEAR_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < YEAR_CACHE_TTL_SECONDS:
            return cached[1]

    definitions = load_index_universe()
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    active = [item for item in definitions if item.start_date <= year_end]
    groups = (
        [item.ts_code for item in active if not item.ts_code.endswith(".CSI")],
        *[
            [item.ts_code]
            for item in active
            if item.ts_code.endswith(".CSI")
        ],
    )
    rows: list[dict] = []
    if any(groups):
        _YEAR_RATE_LIMIT.acquire()
    for group in groups:
        if not group:
            continue
        start = max(year_start, min(
            (item.start_date for item in definitions if item.ts_code in group),
            default=year_start,
        ))
        fetched = call_range_api(
            token,
            group,
            start.strftime("%Y%m%d"),
            year_end.strftime("%Y%m%d"),
            fields,
        )
        rows.extend(fetched)
    with _YEAR_CACHE_LOCK:
        _YEAR_CACHE[cache_key] = (time.monotonic(), rows)
    return rows


def _normalize(rows: list[dict], field_contracts: list[dict]) -> list[dict]:
    return [
        {
            field["name"]: normalize_value(
                row.get(field.get("source_name") or field["name"]), field["data_type"]
            )
            for field in field_contracts
        }
        for row in rows
    ]


def _collect_rows(
    context: CollectionContext,
    parameters: dict,
    field_contracts: list[dict],
    rows: list[dict],
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    day = date.fromisoformat(trade_date)
    expected = [item for item in load_index_universe() if item.start_date <= day]
    wanted_codes = [item.ts_code for item in expected]
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("trade_date") or "") != trade_date.replace("-", ""):
            continue
        code = row.get("ts_code")
        if isinstance(code, str) and code in wanted_codes:
            by_code[code] = row
    missing = [code for code in wanted_codes if code not in by_code]
    if missing:
        raise CollectionError(
            f"index_daily {trade_date} 未返回指数：{', '.join(missing)}"
        )

    normalized = _normalize(
        [by_code[item.ts_code] for item in expected], field_contracts
    )
    schema = pa.schema(
        [
            pa.field(field["name"], arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / f"trade_date={trade_date}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    artifact = DatasetArtifact(
        dataset_id=DATASET_ID,
        path=target,
        partition={"trade_date": trade_date},
        row_count=table.num_rows,
    )
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={
            "api": "index_daily",
            "api_url": load_api_url(),
            "trade_date": trade_date,
            "indices": wanted_codes,
        },
    )


def collect_daily(
    context: CollectionContext,
    parameters: dict,
    field_contracts: list[dict],
) -> CollectionResult:
    """单日增量路径：一次请求当天全部指数。"""
    trade_date = parameters["trade_date"]
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = call_api(context.token, trade_date.replace("-", ""), source_fields)
    return _collect_rows(context, parameters, field_contracts, rows)

def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = _load_year(context.token, date.fromisoformat(trade_date).year, source_fields)
    return _collect_rows(context, parameters, field_contracts, rows)


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect_daily(context, parameters, field_contracts)
