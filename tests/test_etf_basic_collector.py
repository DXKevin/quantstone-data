from __future__ import annotations

from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tushare_cn_etf import etf_basic
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tushare.cn.etf.etf_basic.reviewer import review


def _contract():
    return next(
        item.contract
        for item in DATASET_PRESETS
        if item.contract.id == "tushare.cn.etf.etf_basic"
    )


def _fields() -> list[dict]:
    return [item.model_dump() for item in _contract().fields]


def _row(code: str, status: str) -> dict:
    return {
        "ts_code": code,
        "csname": "测试ETF",
        "extname": "测试ETF",
        "cname": "测试ETF基金",
        "index_code": "000300.SH",
        "index_name": "沪深300指数",
        "setup_date": "20130329",
        "list_date": "20141020",
        "list_status": status,
        "exchange": code.split(".")[-1],
        "mgr_name": "测试基金",
        "custod_name": "测试银行",
        "mgt_fee": 0.15,
        "etf_type": "纯境内",
    }


def test_etf_basic_deduplicates_statuses(monkeypatch, tmp_path) -> None:
    def fake_call(token, status, fields):
        return [_row("510300.SH", status), _row("159919.SZ", status)]

    monkeypatch.setattr(etf_basic, "_call", fake_call)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    result = etf_basic.collect_initial(context, {}, _fields())
    artifact = result.outputs["tushare.cn.etf.etf_basic"][0]
    assert artifact.row_count == 2
    table = pq.read_table(artifact.path)
    assert table["ts_code"].to_pylist() == ["159919.SZ", "510300.SH"]
    assert table["setup_date"].to_pylist()[0].isoformat() == "2013-03-29"
    assert table.schema.names == [item["name"] for item in _fields()]


def test_etf_basic_reviewer_accepts_snapshot(tmp_path) -> None:
    rows = [_row("510300.SH", "L"), _row("159919.SZ", "D"), _row("159908J.SZ", "L")]
    schema = pa.schema(
        [
            pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"])
            for item in _fields()
        ]
    )
    table = pa.Table.from_pylist(
        [
            {
                **row,
                "setup_date": date(2013, 3, 29),
                "list_date": date(2014, 10, 20),
            }
            for row in rows
        ],
        schema=schema,
    )
    path = tmp_path / "snapshot.parquet"
    pq.write_table(table, path)
    dataset_schema = DatasetSchemaVersion(
        version=1, primary_key="ts_code", time_field=None
    )
    dataset_schema.fields = [
        DatasetField(
            name=item["name"],
            data_type=item["data_type"],
            nullable=item["nullable"],
            description=item["description"],
            position=index,
        )
        for index, item in enumerate(_fields())
    ]
    report = review(ReviewContext(path, dataset_schema, None))
    assert report.passed, report.errors
    assert report.row_count == 3
