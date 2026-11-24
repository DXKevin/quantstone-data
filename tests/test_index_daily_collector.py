from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tushare_cn_stock import index_daily
from quantstone_data.dataset_presets import DATASET_PRESETS


def _field_contracts() -> list[dict]:
    contract = next(
        item.contract
        for item in DATASET_PRESETS
        if item.contract.id == "tushare.cn.index.index_daily"
    )
    return [field.model_dump() for field in contract.fields]


def _rows(day: str = "2026-11-23") -> list[dict]:
    return [
        {
            "ts_code": item.ts_code,
            "trade_date": day.replace("-", ""),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "pre_close": 100.0,
            "change": 1.0,
            "pct_chg": 1.0,
            "vol": 1000.0,
            "amount": 2000.0,
        }
        for item in index_daily.load_index_universe()
    ]


def test_index_universe_contains_main_indices() -> None:
    definitions = index_daily.load_index_universe()
    codes = [item.ts_code for item in definitions]
    assert len(codes) == 13
    assert codes[0] == "000001.SH"
    assert "932000.CSI" in codes
    assert "000985.CSI" in codes
    assert len(codes) == len(set(codes))


def test_index_universe_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "universe.json"
    path.write_text(
        json.dumps(
            {
                "indices": [
                    {"ts_code": "000001.SH", "name": "上证指数", "start_date": "2013-12-31"},
                    {"ts_code": "000001.SH", "name": "重复", "start_date": "2013-12-31"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(index_daily.CollectionError):
        index_daily.load_index_universe(path)


def test_collect_daily_filters_to_universe(monkeypatch, tmp_path: Path) -> None:
    rows = _rows()
    rows.append({**rows[0], "ts_code": "999999.SH"})
    monkeypatch.setattr(
        index_daily,
        "call_api",
        lambda token, trade_date, fields: list(rows),
    )
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    result = index_daily.collect_daily(
        context, {"trade_date": "2026-11-23"}, _field_contracts()
    )
    output = result.outputs["tushare.cn.index.index_daily"][0]
    assert output.row_count == 13
    table = pq.read_table(output.path)
    assert table.num_rows == 13
    assert "999999.SH" not in table["ts_code"].to_pylist()
    assert table["ts_code"].to_pylist()[0] == "000001.SH"
    assert table["trade_date"].to_pylist()[0].isoformat() == "2026-11-23"


def test_collect_daily_skips_index_before_start(monkeypatch, tmp_path: Path) -> None:
    rows = [row for row in _rows("2019-01-02") if row["ts_code"] != "000688.SH"]
    monkeypatch.setattr(
        index_daily,
        "call_api",
        lambda token, trade_date, fields: list(rows),
    )
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    result = index_daily.collect_daily(
        context, {"trade_date": "2019-01-02"}, _field_contracts()
    )
    output = result.outputs["tushare.cn.index.index_daily"][0]
    assert output.row_count == 12
    assert "000688.SH" not in pq.read_table(output.path)["ts_code"].to_pylist()


def test_collect_daily_reports_missing_index(monkeypatch, tmp_path: Path) -> None:
    rows = [row for row in _rows() if row["ts_code"] != "000300.SH"]
    monkeypatch.setattr(
        index_daily,
        "call_api",
        lambda token, trade_date, fields: list(rows),
    )
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
    )
    with pytest.raises(index_daily.CollectionError, match="000300.SH"):
        index_daily.collect_daily(
            context, {"trade_date": "2026-11-23"}, _field_contracts()
        )
