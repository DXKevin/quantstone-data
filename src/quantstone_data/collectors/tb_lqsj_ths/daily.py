from __future__ import annotations

import time
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .sector_categories import MAX_PAGE, ThsCollectionError, load_api_url

DATASET_ID = "tb_lqsj_ths.cn.index.daily"
PAGE_SIZE = 1000


def normalize_ths_code(value: Any) -> str | None:
    if value is None or value == "":
        return None
    code = str(value)
    if code.startswith("TI."):
        return f"{code[3:]}.TI"
    return code


def call_api(
    api_key: str, trade_date: str, page: int, page_size: int = PAGE_SIZE
) -> tuple[int, list[dict]]:
    body = post_json(
        "tb_lqsj_ths",
        f"{load_api_url()}/api/index/ths_daily",
        {
            "start_time": trade_date,
            "end_time": trade_date,
            "page": page,
            "page_size": page_size,
        },
        headers={"X-API-Key": api_key},
    )
    if body.get("code") != 200:
        raise ThsCollectionError(body.get("msg") or "THS 板块日线接口调用失败")
    data = body.get("data") or {}
    rows = data.get("list") or []
    if not isinstance(rows, list):
        raise ThsCollectionError("THS 板块日线接口的 data.list 不是数组")
    return int(data.get("total") or 0), rows


def _source_value(row: dict, field: dict) -> Any:
    value = row.get(field.get("source_name") or field["name"])
    if field["data_type"] == "date" and isinstance(value, str):
        return value.replace("-", "")
    return value


def _fetch_daily(token: str, trade_date: str) -> tuple[dict[str, dict], int, int]:
    by_code: dict[str, dict] = {}
    expected_total: int | None = None
    raw_count = 0
    pages = 0
    for page in range(MAX_PAGE + 1):
        total, rows = call_api(token, trade_date, page)
        pages += 1
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ThsCollectionError("THS 板块日线分页期间 total 发生变化，请稍后重试")
        if not rows:
            break
        raw_count += len(rows)
        for row in rows:
            if row.get("trade_date") != trade_date:
                raise ThsCollectionError(
                    f"THS 板块日线返回了分区外日期：{row.get('trade_date')}"
                )
            code = normalize_ths_code(row.get("ths_code"))
            if code:
                by_code[code] = {**row, "ths_code": code}
        if raw_count >= total:
            break
    if expected_total is None or raw_count != expected_total:
        raise ThsCollectionError(
            f"THS 板块日线分页不完整：期望 {expected_total or 0} 条，实际 {raw_count} 条"
        )
    return by_code, expected_total, pages


def collect_daily(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    by_code: dict[str, dict] = {}
    expected_total: int | None = None
    pages = 0
    for attempt in range(3):
        try:
            by_code, expected_total, pages = _fetch_daily(context.token, trade_date)
            break
        except ThsCollectionError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))

    normalized = [
        {
            field["name"]: normalize_value(_source_value(row, field), field["data_type"])
            for field in field_contracts
        }
        for _code, row in sorted(by_code.items())
    ]
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
    return CollectionResult(
        outputs={
            DATASET_ID: [
                DatasetArtifact(
                    DATASET_ID,
                    target,
                    {"trade_date": trade_date},
                    table.num_rows,
                )
            ]
        },
        provenance={
            "api": "ths_daily",
            "api_url": load_api_url(),
            "trade_date": trade_date,
            "pages": pages,
            "reported_total": expected_total,
        },
    )


def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect_daily(context, parameters, field_contracts)


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect_daily(context, parameters, field_contracts)
