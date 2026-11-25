from __future__ import annotations

import csv
import zipfile
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tb_lhsjk_023199 import minute_1m
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tb_sbkj2077.cn.stock.minute_1m.reviewer import review


def test_repair_uses_incremental_path() -> None:
    from quantstone_data.collectors.tb_lhsjk_023199.definition import COLLECTOR
    from quantstone_data.collectors.tb_lhsjk_023199.minute_1m import collect_incremental

    assert COLLECTOR.operations["minute_1m_repair"].function is collect_incremental


def _write_csv(path: Path, code: str, rows: list[tuple[str, float, int, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "时间",
                "代码",
                "名称",
                "开盘价",
                "收盘价",
                "最高价",
                "最低价",
                "成交量",
                "成交额",
                "涨幅",
                "振幅",
            ]
        )
        for time_text, price, volume, amount in rows:
            writer.writerow(
                [time_text, code, "测试", price, price, price, price, volume, amount, 0.0, 0.0]
            )


def _make_zip(path: Path) -> None:
    year_dir = path.parent / "csv"
    _write_csv(
        year_dir / "sh600000.csv",
        "sh600000",
        [
            ("2026/11/23 09:30", 10.0, 100, 100000.0),
            ("2026/11/23 09:31", 10.1, 200, 202000.0),
            ("2026/11/24 09:30", 10.2, 300, 306000.0),
        ],
    )
    _write_csv(
        year_dir / "sz000001.csv",
        "sz000001",
        [
            ("2026/11/23 09:30", 12.0, 100, 120000.0),
            ("2026/11/23 09:31", 12.1, 200, 242000.0),
            ("2026/11/24 09:30", 12.2, 300, 366000.0),
        ],
    )
    with zipfile.ZipFile(path, "w") as archive:
        for item in year_dir.iterdir():
            archive.write(item, item.name)


def _schema() -> DatasetSchemaVersion:
    contract = next(
        item.contract
        for item in DATASET_PRESETS
        if item.contract.id == "tb_sbkj2077.cn.stock.minute_1m"
    )
    schema = DatasetSchemaVersion(
        version=1,
        primary_key="ts_code,trade_date,bar_time",
        time_field="trade_date",
    )
    schema.fields = [
        DatasetField(
            name=field.name,
            data_type=field.data_type,
            nullable=field.nullable,
            description=field.description,
            position=index,
        )
        for index, field in enumerate(contract.fields)
    ]
    return schema


def test_daily_zip_builds_contract_artifact(tmp_path: Path) -> None:
    zip_path = tmp_path / "20261123_1min.zip"
    _make_zip(zip_path)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
        data_root=tmp_path / "data",
    )
    artifact = minute_1m._build_daily_artifact(context, zip_path, "2026-11-23")
    table = pq.read_table(artifact.path)
    assert artifact.row_count == 4
    assert table.schema.names == [field.name for field in minute_1m.SCHEMA]
    assert set(table["ts_code"].to_pylist()) == {"600000.SH", "000001.SZ"}
    assert set(table["bar_time"].to_pylist()) == {93000, 93100}


def test_year_cache_partitions_by_trade_date(tmp_path: Path) -> None:
    zip_path = tmp_path / "2026_1min.zip"
    _make_zip(zip_path)
    daily_dir = minute_1m._build_year_partitions(zip_path, tmp_path / "year")
    partitions = sorted(item.name for item in daily_dir.glob("trade_date=*"))
    assert partitions == ["trade_date=2026-11-23", "trade_date=2026-11-24"]
    table = minute_1m._read_daily(daily_dir, "2026-11-23")
    assert table.num_rows == 4


def test_year_cache_ignores_empty_supplier_csv(tmp_path: Path) -> None:
    zip_path = tmp_path / "2026_1min.zip"
    _make_zip(zip_path)
    with zipfile.ZipFile(zip_path, "a") as archive:
        archive.writestr("sh601091_2026.csv", b"")

    daily_dir = minute_1m._build_year_partitions(zip_path, tmp_path / "year")

    assert sorted(item.name for item in daily_dir.glob("trade_date=*")) == [
        "trade_date=2026-11-23",
        "trade_date=2026-11-24",
    ]


def test_year_cache_accepts_unescaped_quote_in_unused_name(tmp_path: Path) -> None:
    zip_path = tmp_path / "2026_1min.zip"
    _make_zip(zip_path)
    malformed = tmp_path / "csv" / "sh601091_2026.csv"
    malformed.write_text(
        "时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额,涨幅,振幅\n"
        '2026/11/23 09:30,sh601091,沈鼓集团",13,13,13,13,100,1300,0,0\n',
        encoding="utf-8-sig",
    )
    with zipfile.ZipFile(zip_path, "a") as archive:
        archive.write(malformed, malformed.name)

    daily_dir = minute_1m._build_year_partitions(zip_path, tmp_path / "year")
    table = minute_1m._read_daily(daily_dir, "2026-11-23")

    assert table.num_rows == 5
    assert "601091.SH" in table["ts_code"].to_pylist()


def test_minute_reviewer_accepts_contract_artifact(tmp_path: Path) -> None:
    zip_path = tmp_path / "20261123_1min.zip"
    _make_zip(zip_path)
    context = CollectionContext(
        run_id="run",
        staging_dir=tmp_path / "staging",
        token="token",
        data_root=tmp_path / "data",
    )
    artifact = minute_1m._build_daily_artifact(context, zip_path, "2026-11-23")
    report = review(
        ReviewContext(artifact.path, _schema(), date(2026, 11, 23))
    )
    assert report.passed, report.errors
    assert report.row_count == 4
