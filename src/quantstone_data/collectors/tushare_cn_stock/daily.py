from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from .stock_basic import API_URL, raise_api_error

DATASET_ID = "tushare.cn.stock.daily"


def _arrow_type(data_type: str) -> pa.DataType:
    return {
        "string": pa.string(),
        "date": pa.date32(),
        "int32": pa.int32(),
        "int64": pa.int64(),
        "float32": pa.float32(),
        "float64": pa.float64(),
        "boolean": pa.bool_(),
        "timestamp": pa.timestamp("us"),
    }[data_type]


def _convert(value: Any, data_type: str) -> Any:
    if value is None or value == "":
        return None
    if data_type == "date":
        return datetime.strptime(str(value), "%Y%m%d").date()
    if data_type in {"float32", "float64"}:
        return float(value)
    if data_type in {"int32", "int64"}:
        return int(value)
    return value


def _call_daily(token: str, trade_date: str, fields: list[str]) -> list[dict]:
    payload = json.dumps(
        {
            "api_name": "daily",
            "token": token,
            "params": {"trade_date": trade_date},
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
        raise_api_error(body, "TuShare daily 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def _collect_daily(
    context: CollectionContext,
    parameters: dict,
    field_contracts: list[dict],
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = _call_daily(context.token, trade_date.replace("-", ""), source_fields)
    normalized = [
        {
            field["name"]: _convert(
                row.get(field.get("source_name") or field["name"]), field["data_type"]
            )
            for field in field_contracts
        }
        for row in rows
    ]
    schema = pa.schema(
        [
            pa.field(field["name"], _arrow_type(field["data_type"]), field["nullable"])
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
        provenance={"api": "daily", "trade_date": trade_date},
    )


def collect_daily_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect_daily(context, parameters, field_contracts)


def collect_daily_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect_daily(context, parameters, field_contracts)
