from __future__ import annotations

from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tushare_cn_etf import fund_adj
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tushare.cn.etf.fund_adj.reviewer import review

DATASET_ID = "tushare.cn.etf.fund_adj"


def _fields() -> list[dict]:
    contract = next(
        item.contract for item in DATASET_PRESETS if item.contract.id == DATASET_ID
    )
    return [item.model_dump() for item in contract.fields]


def test_fund_adj_paginates_all_rows(monkeypatch, tmp_path) -> None:
    offsets: list[int] = []

    def fake_page(token, trade_date, offset, fields):
        offsets.append(offset)
        count = 2000 if offset == 0 else 241
        start = offset
        return [
            {
                "ts_code": f"{start + index + 1:06d}.SH",
                "trade_date": "20261124",
                "adj_factor": 1.0,
            }
            for index in range(count)
        ]

    monkeypatch.setattr(fund_adj, "_call_page", fake_page)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    result = fund_adj.collect_initial(
        context, {"trade_date": "2026-11-24"}, _fields()
    )
    artifact = result.outputs[DATASET_ID][0]
    assert offsets == [0, 2000]
    assert artifact.row_count == 2241
    assert artifact.partition == {"trade_date": "2026-11-24"}
    table = pq.read_table(artifact.path)
    assert table["adj_factor"].length() == 2241


def test_fund_adj_reviewer_accepts_partition(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [
            pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"])
            for item in fields
        ]
    )
    rows = [
        {
            "ts_code": "510300.SH",
            "trade_date": date(2026, 11, 24),
            "adj_factor": 1.0,
        },
        {
            "ts_code": "159919.SZ",
            "trade_date": date(2026, 11, 24),
            "adj_factor": 1.1,
        },
    ]
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
