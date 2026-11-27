from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tb_lqsj_ths import minute_1m
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tb_lqsj_ths.cn.index.minute_1m.reviewer import review


def _contract():
    return next(
        item.contract for item in DATASET_PRESETS if item.contract.id == minute_1m.DATASET_ID
    )


def _fields() -> list[dict]:
    return [item.model_dump() for item in _contract().fields]


def _source_row(code: str, trade_time: str) -> dict:
    return {
        "ths_code": code,
        "trade_time": trade_time,
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 102.0,
        "volume": 12_300.0,
        "turnover": 456_789.0,
        "turnover_rate": 0.1,
    }


def _dataset_schema() -> DatasetSchemaVersion:
    fields = _fields()
    schema = DatasetSchemaVersion(
        version=1,
        primary_key="ths_code,trade_date,bar_time",
        time_field="trade_date",
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


def test_ths_minute_collects_batched_partition(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(minute_1m, "CODE_BATCH_SIZE", 2)
    monkeypatch.setattr(
        minute_1m,
        "_fetch_daily",
        lambda _token, _date: (
            {f"88110{i}.TI": {} for i in range(1, 4)},
            3,
            1,
        ),
    )
    calls: list[list[str]] = []

    def fake_fetch(_token: str, codes: list[str], trade_date: str):
        assert trade_date == "2026-11-25"
        calls.append(codes)
        return (
            [
                _source_row(code, f"{trade_date} 09:31:00")
                for code in codes
            ],
            1,
        )

    monkeypatch.setattr(minute_1m, "_fetch_batch", fake_fetch)
    result = minute_1m.collect_daily(
        CollectionContext("run", tmp_path / "staging", "api-key"),
        {"trade_date": "2026-11-25"},
        _fields(),
    )
    artifact = result.outputs[minute_1m.DATASET_ID][0]
    table = pq.read_table(artifact.path)

    assert calls == [["881101.TI", "881102.TI"], ["881103.TI"]]
    assert artifact.partition == {"trade_date": "2026-11-25"}
    assert table["trade_date"].to_pylist() == [date(2026, 11, 25)] * 3
    assert table["bar_time"].to_pylist() == [93_100] * 3
    assert table["volume"].to_pylist() == [123.0] * 3
    assert table["amount"].to_pylist() == [456_789.0] * 3
    assert result.provenance["minute_codes"] == 3
    assert result.provenance["corrected_negative_amounts"] == 0


def test_ths_minute_corrects_sign_inverted_turnover(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        minute_1m,
        "_fetch_daily",
        lambda _token, _date: ({"881102.TI": {}}, 1, 1),
    )
    source = _source_row("881102.TI", "2022-11-09 09:44:00")
    source["turnover"] = -62_529_620.0
    monkeypatch.setattr(minute_1m, "_fetch_batch", lambda *_args: ([source], 1))

    result = minute_1m.collect_daily(
        CollectionContext("run", tmp_path / "staging", "api-key"),
        {"trade_date": "2022-11-09"},
        _fields(),
    )
    artifact = result.outputs[minute_1m.DATASET_ID][0]
    table = pq.read_table(artifact.path)

    assert table["amount"].to_pylist() == [62_529_620.0]
    assert result.provenance["corrected_negative_amounts"] == 1
    report = review(ReviewContext(artifact.path, _dataset_schema(), date(2022, 11, 9)))
    assert report.passed, report.errors


def test_ths_minute_skips_empty_source_day(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        minute_1m,
        "_fetch_daily",
        lambda _token, _date: ({"881101.TI": {}}, 1, 1),
    )
    monkeypatch.setattr(minute_1m, "_fetch_batch", lambda *_args: ([], 1))
    result = minute_1m.collect_daily(
        CollectionContext("run", tmp_path / "staging", "api-key"),
        {"trade_date": "2010-01-04"},
        _fields(),
    )
    assert result.skipped is True
    assert result.outputs == {}


def test_ths_minute_reviewer_accepts_valid_partition(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {
        "ths_code": "881101.TI",
        "trade_date": date(2026, 11, 25),
        "bar_time": 93_100,
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 102.0,
        "volume": 123.0,
        "amount": 456_789.0,
        "turnover_rate": 0.1,
    }
    path = tmp_path / "minute.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=schema), path)
    report = review(ReviewContext(path, _dataset_schema(), date(2026, 11, 25)))
    assert report.passed, report.errors


def test_ths_minute_reviewer_rejects_invalid_session_time(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {
        "ths_code": "881101.TI",
        "trade_date": date(2026, 11, 25),
        "bar_time": 120_000,
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 102.0,
        "volume": 123.0,
        "amount": 456_789.0,
        "turnover_rate": 0.1,
    }
    path = tmp_path / "minute.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=schema), path)
    report = review(ReviewContext(path, _dataset_schema(), date(2026, 11, 25)))
    assert not report.passed
    assert any(error.get("rule") == "bar_time_session" for error in report.errors)
