from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .sector_categories import MAX_PAGE, ThsCollectionError, load_api_url

DATASET_ID = "tb_lqsj_ths.cn.index.constituent_stocks"
PAGE_SIZE = 1000


def call_api(
    api_key: str, trade_date: str, page: int, page_size: int = PAGE_SIZE
) -> tuple[int, list[dict]]:
    body = post_json(
        "tb_lqsj_ths",
        f"{load_api_url()}/api/index/ths_constituent_stocks_history",
        {
            "trade_date": trade_date,
            "page": page,
            "page_size": page_size,
        },
        headers={"X-API-Key": api_key},
    )
    if body.get("code") != 200:
        raise ThsCollectionError(body.get("msg") or "THS 板块成分接口调用失败")
    data = body.get("data") or {}
    rows = data.get("list") or []
    if not isinstance(rows, list):
        raise ThsCollectionError("THS 板块成分接口的 data.list 不是数组")
    return int(data.get("total") or 0), rows


def _source_value(row: dict, field: dict) -> Any:
    value = row.get(field.get("source_name") or field["name"])
    if field["data_type"] == "date" and isinstance(value, str):
        return value.replace("-", "")
    return value


def _flatten(
    token: str, trade_date: str
) -> tuple[list[dict], int, int]:
    """Return one source row per stock, plus board count and pages read."""
    by_key: dict[tuple[str, str, str], dict] = {}
    expected_boards: int | None = None
    raw_boards = 0
    pages = 0
    for page in range(MAX_PAGE + 1):
        total, boards = call_api(token, trade_date, page)
        pages += 1
        if expected_boards is None:
            expected_boards = total
        elif total != expected_boards:
            raise ThsCollectionError("THS 板块成分分页期间 total 发生变化，请稍后重试")
        if not boards:
            break
        raw_boards += len(boards)
        for board in boards:
            board_date = board.get("trade_date")
            if board_date != trade_date:
                raise ThsCollectionError(
                    f"THS 板块成分返回了分区外日期：{board_date}"
                )
            index_code = str(board.get("index_code") or "").strip()
            if not index_code:
                raise ThsCollectionError("THS 板块成分缺少 index_code")
            stocks = board.get("stocks") or []
            if not isinstance(stocks, list):
                raise ThsCollectionError(
                    f"THS 板块 {index_code} 的 stocks 不是数组"
                )
            for raw_code in stocks:
                stock_code = str(raw_code or "").strip()
                if not stock_code:
                    continue
                by_key[(trade_date, index_code, stock_code)] = {
                    "trade_date": trade_date,
                    "index_code": index_code,
                    "stock_code": stock_code,
                }
        if raw_boards >= expected_boards:
            break
    if expected_boards is None or raw_boards != expected_boards:
        raise ThsCollectionError(
            f"THS 板块成分分页不完整：期望 {expected_boards or 0} 个板块，"
            f"实际 {raw_boards} 个"
        )
    return (
        [by_key[key] for key in sorted(by_key)],
        expected_boards,
        pages,
    )


def collect_daily(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    source_rows, boards, pages = _flatten(context.token, trade_date)
    normalized = [
        {
            field["name"]: normalize_value(_source_value(row, field), field["data_type"])
            for field in field_contracts
        }
        for row in source_rows
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
            "api": "ths_constituent_stocks_history",
            "api_url": load_api_url(),
            "trade_date": trade_date,
            "boards": boards,
            "pages": pages,
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
