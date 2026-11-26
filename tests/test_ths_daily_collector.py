from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tb_lqsj_ths import daily
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tb_lqsj_ths.cn.index.daily.reviewer import review


def _contract():
    return next(item.contract for item in DATASET_PRESETS if item.contract.id == daily.DATASET_ID)


def _fields() -> list[dict]:
    return [item.model_dump() for item in _contract().fields]


def _row(code: int, trade_date: str = "2026-11-25") -> dict:
    return {
        "ths_code": f"{code:06d}.TI",
        "trade_date": trade_date,
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 102.0,
        "pre_close": 100.0,
        "avg_price": 12.5,
        "change": 2.0,
        "pct_change": 2.0,
        "vol": 12345.0,
        "turnover_rate": 1.5,
    }


def _dataset_schema() -> DatasetSchemaVersion:
    fields = _fields()
    schema = DatasetSchemaVersion(
        version=1, primary_key="ths_code,trade_date", time_field="trade_date"
    )
    schema.fields = [
        DatasetField(
            name=item["name"],
            data_type=item["data_type"],
            nullable=item["nullable"],
            description=item["description"],
            position=index,
        )
        for index, item in enumerate(fields)
    ]
    return schema


def test_ths_daily_collects_complete_partition(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(daily, "PAGE_SIZE", 2)
    calls: list[int] = []

    def fake_call(_key: str, trade_date: str, page: int, page_size: int = 2):
        assert trade_date == "2026-11-25"
        assert page_size == 2
        calls.append(page)
        rows = [_row(1), _row(2), _row(3)]
        return len(rows), rows[page * page_size : (page + 1) * page_size]

    monkeypatch.setattr(daily, "call_api", fake_call)
    result = daily.collect_daily(
        CollectionContext("run", tmp_path / "staging", "api-key"),
        {"trade_date": "2026-11-25"},
        _fields(),
    )
    artifact = result.outputs[daily.DATASET_ID][0]
    table = pq.read_table(artifact.path)

    assert calls == [0, 1]
    assert artifact.partition == {"trade_date": "2026-11-25"}
    assert artifact.row_count == 3
    assert table["trade_date"].to_pylist() == [date(2026, 11, 25)] * 3
    assert result.provenance["reported_total"] == 3


def test_ths_daily_rejects_partition_mismatch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        daily,
        "call_api",
        lambda *_args, **_kwargs: (1, [_row(1, "2026-11-24")]),
    )
    try:
        daily.collect_daily(
            CollectionContext("run", tmp_path / "staging", "api-key"),
            {"trade_date": "2026-11-25"},
            _fields(),
        )
    except daily.ThsCollectionError as error:
        assert "分区外日期" in str(error)
    else:
        raise AssertionError("expected partition mismatch to fail")


def test_ths_daily_normalizes_reversed_ti_code(monkeypatch, tmp_path) -> None:
    row = {**_row(1), "ths_code": "TI.700012R"}
    monkeypatch.setattr(daily, "call_api", lambda *_args, **_kwargs: (1, [row]))
    result = daily.collect_daily(
        CollectionContext("run", tmp_path / "staging", "api-key"),
        {"trade_date": "2026-11-25"},
        _fields(),
    )
    table = pq.read_table(result.outputs[daily.DATASET_ID][0].path)
    assert table["ths_code"].to_pylist() == ["700012R.TI"]


def test_ths_daily_reviewer_accepts_valid_partition(tmp_path) -> None:
    fields = _fields()
    arrow_schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {**_row(1), "trade_date": date(2026, 11, 25)}
    path = tmp_path / "daily.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=arrow_schema), path)

    report = review(ReviewContext(path, _dataset_schema(), date(2026, 11, 25)))
    assert report.passed, report.errors


def test_ths_daily_reviewer_rejects_invalid_ohlc(tmp_path) -> None:
    fields = _fields()
    arrow_schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {**_row(1), "trade_date": date(2026, 11, 25), "high": 98.0}
    path = tmp_path / "daily.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=arrow_schema), path)

    report = review(ReviewContext(path, _dataset_schema(), date(2026, 11, 25)))
    assert not report.passed
    assert any(error.get("rule") == "ohlc_relationship" for error in report.errors)


def test_ths_daily_reviewer_accepts_verified_vendor_ohlc_exception(tmp_path) -> None:
    fields = _fields()
    arrow_schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {
        **_row(1, "2021-02-02"),
        "ths_code": "864019.TI",
        "trade_date": date(2021, 2, 2),
        "open": 3920.0,
        "high": 4137.68,
        "low": 3814.13,
        "close": 5242.33,
    }
    path = tmp_path / "daily.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=arrow_schema), path)

    report = review(ReviewContext(path, _dataset_schema(), date(2021, 2, 2)))
    assert report.passed, report.errors
