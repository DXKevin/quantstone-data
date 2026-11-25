from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from ..tushare_cn_stock.stock_basic import load_api_url, raise_api_error

DATASET_ID = "tushare.cn.etf.etf_basic"
LIST_STATUSES = ("L", "D", "P")


def _call(token: str, list_status: str, fields: list[str]) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "etf_basic",
            "token": token,
            "params": {"list_status": list_status},
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare etf_basic 接口调用失败")
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
    source_fields = [
        item.get("source_name") or item["name"] for item in field_contracts
    ]
    by_code: dict[str, dict] = {}
    for status in LIST_STATUSES:
        for row in _call(context.token, status, source_fields):
            code = row.get("ts_code")
            if code:
                by_code[str(code)] = row
    normalized = [
        {
            field["name"]: normalize_value(
                row.get(field.get("source_name") or field["name"]),
                field["data_type"],
            )
            for field in field_contracts
        }
        for _code, row in sorted(by_code.items())
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
    target = context.staging_dir / "outputs" / "etf_basic.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    artifact = DatasetArtifact(DATASET_ID, target, {}, table.num_rows)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={
            "api": "etf_basic",
            "api_url": load_api_url(),
            "list_statuses": list(LIST_STATUSES),
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
