from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .stock_basic import load_api_url, raise_api_error

DATASET_ID = "tushare.cn.stock.namechange"


def call_api(token: str, fields: list[str]) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "namechange",
            "token": token,
            "params": {},
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare namechange 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [
        dict(zip(returned_fields, item, strict=False))
        for item in data.get("items") or []
    ]


def collect(
    context: CollectionContext,
    field_contracts: list[dict],
) -> CollectionResult:
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = call_api(context.token, source_fields)
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
    normalized.sort(
        key=lambda row: (
            row.get("ts_code") or "",
            str(row.get("start_date") or ""),
            row.get("name") or "",
        )
    )
    schema = pa.schema(
        [
            pa.field(field["name"], arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / "namechange.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    return CollectionResult(
        outputs={DATASET_ID: [DatasetArtifact(DATASET_ID, target, {}, table.num_rows)]},
        provenance={"api": "namechange", "api_url": load_api_url(), "params": {}},
    )


def collect_initial(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)


def collect_incremental(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)
