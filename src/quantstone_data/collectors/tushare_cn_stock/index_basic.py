from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .stock_basic import load_api_url, raise_api_error

DATASET_ID = "tushare.cn.index.index_basic"
MARKETS = ("MSCI", "CSI", "SSE", "SZSE", "CICC", "SW", "OTH")


def call_api(token: str, market: str, fields: list[str]) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "index_basic",
            "token": token,
            "params": {"market": market},
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare index_basic 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def _source_value(row: dict, field: dict) -> Any:
    return row.get(field.get("source_name") or field["name"])


def collect(
    context: CollectionContext,
    field_contracts: list[dict],
    markets: tuple[str, ...] = MARKETS,
) -> CollectionResult:
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    by_code: dict[str, dict] = {}
    for market in markets:
        for row in call_api(context.token, market, source_fields):
            ts_code = row.get("ts_code")
            if ts_code:
                by_code[str(ts_code)] = row

    normalized = [
        {
            field["name"]: normalize_value(
                _source_value(row, field), field["data_type"]
            )
            for field in field_contracts
        }
        for _ts_code, row in sorted(by_code.items())
    ]
    schema = pa.schema(
        [
            pa.field(field["name"], arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / "index_basic.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    artifact = DatasetArtifact(DATASET_ID, target, {}, table.num_rows)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={"api": "index_basic", "api_url": load_api_url(), "markets": list(markets)},
    )


def collect_initial(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)


def collect_incremental(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)
