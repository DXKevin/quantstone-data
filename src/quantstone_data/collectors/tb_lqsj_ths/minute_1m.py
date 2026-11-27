from __future__ import annotations

from datetime import datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .daily import _fetch_daily, normalize_ths_code
from .sector_categories import MAX_PAGE, ThsCollectionError, load_api_url

DATASET_ID = "tb_lqsj_ths.cn.index.minute_1m"
PAGE_SIZE = 10_000
CODE_BATCH_SIZE = 500


def call_api(
    api_key: str,
    ths_codes: list[str],
    trade_date: str,
    page: int,
    page_size: int = PAGE_SIZE,
) -> tuple[int, list[dict]]:
    body = post_json(
        "tb_lqsj_ths",
        f"{load_api_url()}/api/index/ths_minute",
        {
            "ths_code": ths_codes,
            "level": "1min",
            "start_time": trade_date,
            "end_time": trade_date,
            "page": page,
            "page_size": page_size,
        },
        headers={"X-API-Key": api_key},
    )
    if body.get("code") != 200:
        raise ThsCollectionError(body.get("msg") or "THS 板块分钟接口调用失败")
    data = body.get("data") or {}
    rows = data.get("list") or []
    if not isinstance(rows, list):
        raise ThsCollectionError("THS 板块分钟接口的 data.list 不是数组")
    return int(data.get("total") or 0), rows


def _fetch_batch(token: str, codes: list[str], trade_date: str) -> tuple[list[dict], int]:
    rows: list[dict] = []
    expected_total: int | None = None
    pages = 0
    for page in range(MAX_PAGE + 1):
        total, page_rows = call_api(token, codes, trade_date, page)
        pages += 1
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ThsCollectionError("THS 板块分钟分页期间 total 发生变化，请稍后重试")
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(rows) >= total:
            break
    if expected_total is None or len(rows) != expected_total:
        raise ThsCollectionError(
            f"THS 板块分钟分页不完整：期望 {expected_total or 0} 条，实际 {len(rows)} 条"
        )
    return rows, pages


def _parse_trade_time(value: Any, expected_date: str) -> tuple[str, int]:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError) as error:
        raise ThsCollectionError(f"THS 板块分钟 trade_time 无效：{value}") from error
    trade_date = parsed.date().isoformat()
    if trade_date != expected_date:
        raise ThsCollectionError(f"THS 板块分钟返回了分区外日期：{trade_date}")
    return parsed.strftime("%Y%m%d"), parsed.hour * 10_000 + parsed.minute * 100 + parsed.second


def _normalize_row(row: dict, trade_date: str) -> dict:
    row_date, bar_time = _parse_trade_time(row.get("trade_time"), trade_date)
    code = normalize_ths_code(row.get("ths_code"))
    if not code:
        raise ThsCollectionError("THS 板块分钟缺少 ths_code")
    return {
        **row,
        "ths_code": code,
        "trade_date": row_date,
        "bar_time": bar_time,
        "volume": None if row.get("volume") is None else float(row["volume"]) / 100,
        "amount": row.get("turnover"),
    }


def collect_daily(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    daily_by_code, daily_total, daily_pages = _fetch_daily(context.token, trade_date)
    codes = sorted(daily_by_code)
    by_key: dict[tuple[str, str, int], dict] = {}
    minute_pages = 0
    for start in range(0, len(codes), CODE_BATCH_SIZE):
        rows, pages = _fetch_batch(
            context.token, codes[start : start + CODE_BATCH_SIZE], trade_date
        )
        minute_pages += pages
        for source_row in rows:
            row = _normalize_row(source_row, trade_date)
            key = (row["ths_code"], row["trade_date"], row["bar_time"])
            by_key[key] = row

    if not by_key:
        return CollectionResult(
            outputs={},
            provenance={
                "api": "ths_minute",
                "api_url": load_api_url(),
                "trade_date": trade_date,
                "daily_codes": daily_total,
                "daily_pages": daily_pages,
                "minute_pages": minute_pages,
                "skipped": True,
            },
            skipped=True,
            skip_reason=f"供应商该日无 THS 板块分钟数据：{trade_date}",
        )

    normalized = [
        {
            field["name"]: normalize_value(row.get(field["name"]), field["data_type"])
            for field in field_contracts
        }
        for _key, row in sorted(by_key.items())
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
            "api": "ths_minute",
            "api_url": load_api_url(),
            "trade_date": trade_date,
            "daily_codes": daily_total,
            "daily_pages": daily_pages,
            "minute_pages": minute_pages,
            "minute_codes": len({key[0] for key in by_key}),
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
