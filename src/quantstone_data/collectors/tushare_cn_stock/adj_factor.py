from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .stock_basic import load_api_url, raise_api_error

DATASET_ID = "tushare.cn.stock.adj_factor"


def _call_adj_factor(token: str, trade_date: str, fields: list[str]) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "adj_factor",
            "token": token,
            "params": {"trade_date": trade_date},
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare adj_factor 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [
        dict(zip(returned_fields, item, strict=False))
        for item in data.get("items") or []
    ]


def _collect_adj_factor(
    context: CollectionContext,
    parameters: dict,
    field_contracts: list[dict],
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = _call_adj_factor(context.token, trade_date.replace("-", ""), source_fields)
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
    normalized.sort(key=lambda row: row.get("ts_code") or "")
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
            "api": "adj_factor",
            "api_url": load_api_url(),
            "trade_date": trade_date,
        },
    )


def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect_adj_factor(context, parameters, field_contracts)


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect_adj_factor(context, parameters, field_contracts)
