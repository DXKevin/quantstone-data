from __future__ import annotations

from datetime import date, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json
from .stock_basic import CollectionError, load_api_url, raise_api_error

DATASET_ID = "tushare.cn.stock.trade_cal"
MAX_INCREMENTAL_RANGE_DAYS = 3000


def _call_trade_cal(token: str, start_date: date, end_date: date, fields: list[str]) -> list[dict]:
    body = post_json(
        "tushare",
        load_api_url(),
        {
            "api_name": "trade_cal",
            "token": token,
            "params": {
                "exchange": "SSE",
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
            },
            "fields": ",".join(fields),
        },
    )
    if body.get("code") != 0:
        raise_api_error(body, "TuShare trade_cal 接口调用失败")
    data = body.get("data") or {}
    returned_fields = data.get("fields") or []
    return [dict(zip(returned_fields, item, strict=False)) for item in data.get("items") or []]


def _collect(
    context: CollectionContext,
    start_date: date,
    end_date: date,
    field_contracts: list[dict],
    *,
    merge_current: bool = False,
) -> CollectionResult:
    source_fields = [item.get("source_name") or item["name"] for item in field_contracts]
    rows = _call_trade_cal(context.token, start_date, end_date, source_fields)
    refreshed = [
        {
            field["name"]: normalize_value(
                row.get(field.get("source_name") or field["name"]), field["data_type"]
            )
            for field in field_contracts
        }
        for row in rows
    ]
    if merge_current:
        if not refreshed:
            raise CollectionError("TuShare trade_cal 增量窗口返回 0 行，拒绝覆盖当前快照")
        if context.current_artifact_path is None or not context.current_artifact_path.is_file():
            raise CollectionError("交易日历增量更新缺少当前快照，请先执行首次采集")
        current = pq.read_table(context.current_artifact_path).to_pylist()
        retained = [
            row
            for row in current
            if row["cal_date"] < start_date or row["cal_date"] > end_date
        ]
        normalized = retained + refreshed
    else:
        normalized = refreshed
    primary_keys = {
        (row["exchange"], row["cal_date"]): row
        for row in normalized
    }
    normalized = list(primary_keys.values())
    normalized.sort(key=lambda row: (row["cal_date"], row["exchange"]))
    schema = pa.schema(
        [
            pa.field(field["name"], arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / "trade_cal.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    artifact = DatasetArtifact(DATASET_ID, target, {}, table.num_rows)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={
            "api": "trade_cal",
            "api_url": load_api_url(),
            "exchange": "SSE",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "merged_current_snapshot": merge_current,
        },
    )


def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return _collect(
        context,
        date.fromisoformat(parameters["start_date"]),
        date.fromisoformat(parameters["end_date"]),
        field_contracts,
    )


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    end_date = (
        date.fromisoformat(parameters["end_date"])
        if parameters.get("end_date")
        else date.today() + timedelta(days=366)
    )
    start_date = end_date - timedelta(days=MAX_INCREMENTAL_RANGE_DAYS - 1)
    return _collect(
        context,
        start_date,
        end_date,
        field_contracts,
        merge_current=True,
    )
