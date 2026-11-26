from __future__ import annotations

from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tb_lqsj_ths import constituent_stocks
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tb_lqsj_ths.cn.index.constituent_stocks.reviewer import (
    review,
)

DATASET_ID = "tb_lqsj_ths.cn.index.constituent_stocks"


def _fields() -> list[dict]:
    contract = next(
        item.contract for item in DATASET_PRESETS if item.contract.id == DATASET_ID
    )
    return [item.model_dump() for item in contract.fields]


def test_constituent_stocks_flattens_boards(monkeypatch, tmp_path) -> None:
    def fake_call(token, trade_date, page):
        assert trade_date == "2026-09-30"
        return 2, [
            {
                "trade_date": trade_date,
                "index_code": "881101.TI",
                "stock_count": 2,
                "stocks": ["688001", "600598.SH"],
            },
            {
                "trade_date": trade_date,
                "index_code": "881102.TI",
                "stock_count": 2,
                "stocks": ["000048.SZ", "000048.SZ"],
            },
        ]

    monkeypatch.setattr(constituent_stocks, "call_api", fake_call)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="key",
    )
    result = constituent_stocks.collect_initial(
        context, {"trade_date": "2026-09-30"}, _fields()
    )
    artifact = result.outputs[DATASET_ID][0]
    table = pq.read_table(artifact.path)
    assert artifact.partition == {"trade_date": "2026-09-30"}
    assert artifact.row_count == 3
    assert table["stock_code"].to_pylist() == [
        "600598.SH",
        "688001.SH",
        "000048.SZ",
    ]


def test_constituent_stocks_skips_empty_source_day(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        constituent_stocks, "call_api", lambda *_args, **_kwargs: (0, [])
    )
    result = constituent_stocks.collect_initial(
        CollectionContext("run", tmp_path / "staging", "key"),
        {"trade_date": "2026-08-25"},
        _fields(),
    )
    assert result.skipped is True
    assert result.outputs == {}


def test_constituent_stocks_reviewer_accepts_partition(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [
            pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"])
            for item in fields
        ]
    )
    rows = [
        {
            "trade_date": date(2026, 9, 30),
            "index_code": "881101.TI",
            "stock_code": "000592.SZ",
        },
        {
            "trade_date": date(2026, 9, 30),
            "index_code": "881102.TI",
            "stock_code": "600598.SH",
        },
    ]
    path = tmp_path / "partition.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    dataset_schema = DatasetSchemaVersion(
        version=1,
        primary_key="trade_date,index_code,stock_code",
        time_field="trade_date",
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
    report = review(ReviewContext(path, dataset_schema, date(2026, 9, 30)))
    assert report.passed, report.errors
    assert report.row_count == 2
