from __future__ import annotations

from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tushare_cn_etf import fund_daily
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tushare.cn.etf.fund_daily.reviewer import review

DATASET_ID = "tushare.cn.etf.fund_daily"


def _fields() -> list[dict]:
    contract = next(
        item.contract for item in DATASET_PRESETS if item.contract.id == DATASET_ID
    )
    return [item.model_dump() for item in contract.fields]


def _row(code: str, trade_date: str) -> dict:
    return {
        "ts_code": code,
        "trade_date": trade_date,
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "pre_close": 1.0,
        "change": 0.05,
        "pct_chg": 5.0,
        "vol": 100.0,
        "amount": 10.0,
    }


def test_fund_daily_writes_partition(monkeypatch, tmp_path) -> None:
    def fake_call(token, trade_date, fields):
        assert trade_date == "20261124"
        return [_row("510300.SH", trade_date), _row("159919.SZ", trade_date)]

    monkeypatch.setattr(fund_daily, "_call_fund_daily", fake_call)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    result = fund_daily.collect_initial(
        context, {"trade_date": "2026-11-24"}, _fields()
    )
    artifact = result.outputs[DATASET_ID][0]
    assert artifact.partition == {"trade_date": "2026-11-24"}
    assert artifact.row_count == 2
    table = pq.read_table(artifact.path)
    assert table["trade_date"].to_pylist()[0].isoformat() == "2026-11-24"
    assert table["ts_code"].to_pylist() == ["510300.SH", "159919.SZ"]


def test_fund_daily_reviewer_accepts_partition(tmp_path) -> None:
    fields = _fields()
    rows = [
        {
            **_row("510300.SH", "20261124"),
            "trade_date": date(2026, 11, 24),
        },
        {
            **_row("159919.SZ", "20261124"),
            "trade_date": date(2026, 11, 24),
        },
    ]
    schema = pa.schema(
        [
            pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"])
            for item in fields
        ]
    )
    path = tmp_path / "partition.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    dataset_schema = DatasetSchemaVersion(
        version=1, primary_key="ts_code,trade_date", time_field="trade_date"
    )
    dataset_schema.fields = [
        DatasetField(
            name=item["name"],
            data_type=item["data_type"],
            nullable=item["nullable"],
            description=item["description"],
            position=index,
        )
        for index, item in enumerate(fields)
    ]
    report = review(ReviewContext(path, dataset_schema, date(2026, 11, 24)))
    assert report.passed, report.errors
    assert report.row_count == 2
