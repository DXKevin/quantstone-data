from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from ..tushare_cn_stock.stock_basic import load_api_url, raise_api_error

DATASET_ID = "tushare.cn.etf.fund_adj"
PAGE_SIZE = 2000


def _call_page(
    token: str, trade_date: str, offset: int, fields: list[str]
) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "fund_adj",
            "token": token,
            "params": {
                "trade_date": trade_date,
                "offset": offset,
                "limit": PAGE_SIZE,
            },
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare fund_adj 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [
        dict(zip(returned_fields, item, strict=False))
        for item in data.get("items") or []
    ]


def _call_fund_adj(token: str, trade_date: str, fields: list[str]) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = _call_page(token, trade_date, offset, fields)
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _collect(
    context: CollectionContext,
    parameters: dict,
    field_contracts: list[dict],
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    source_fields = [
        item.get("source_name") or item["name"] for item in field_contracts
    ]
    rows = _call_fund_adj(context.token, trade_date.replace("-", ""), source_fields)
    normalized = [
        {
            field["name"]: normalize_value(
                row.get(field.get("source_name") or field["name"]),
                field["data_type"],
            )
            for field in field_contracts
        }
        for row in rows
    ]
    schema = pa.schema(
        [
            pa.field(
                field["name"],
                arrow_type(field["data_type"]),
                field["nullable"],
            )
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
            "api": "fund_adj",
            "api_url": load_api_url(),
            "trade_date": trade_date,
            "page_size": PAGE_SIZE,
        },
    )


def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect(context, parameters, field_contracts)


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect(context, parameters, field_contracts)
