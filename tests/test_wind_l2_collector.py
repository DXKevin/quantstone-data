from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collector_registry import COLLECTORS
from quantstone_data.collectors.wind_l2_sz import pipeline
from quantstone_data.collectors.wind_l2_sz.pipeline import (
    ORDER,
    TRADE,
    convert_extracted_day,
)
from quantstone_data.dataset_presets import DATASET_PRESETS


def _write_gbk(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("gbk"))


def test_convert_wind_order_csv_to_contract_parquet(tmp_path: Path) -> None:
    source = tmp_path / "20261118"
    _write_gbk(
        source / "000001.SZ" / "逐笔委托.csv",
        "万得代码,交易所代码,自然日,时间,委托编号,交易所委托号,委托类型,委托代码,委托价格,委托数量\n"
        "000001.SZ,000001,20261118,93000000,1,10001,0,B,18446744073709541616,100\n",
    )
    _write_gbk(
        source / "600000.SH" / "逐笔委托.csv",
        "万得代码,交易所代码,自然日,时间,委托编号,交易所委托号,委托类型,委托代码,委托价格,委托数量\n"
        "600000.SH,600000,20261118,93000000,1,1,0,B,100000,100\n",
    )
    target = tmp_path / "l2_order.parquet"

    rows = convert_extracted_day(source, target, ORDER, date(2026, 11, 18))
    table = pq.read_table(target)

    assert rows == 1
    assert table.schema.equals(ORDER.schema)
    assert table.to_pylist() == [
        {
            "symbol": "000001.SZ",
            "exchange_code": "000001",
            "trade_date": date(2026, 11, 18),
            "event_time": 93000000,
            "channel_code": "1",
            "exchange_order_no": 10001,
            "order_type": "0",
            "side": "B",
            "price": 0,
            "volume": 100,
        }
    ]


def test_convert_wind_trade_csv_preserves_nullable_codes(tmp_path: Path) -> None:
    source = tmp_path / "20261118"
    _write_gbk(
        source / "300001.SZ" / "逐笔成交.csv",
        "万得代码,交易所代码,自然日,时间,成交编号,成交代码,委托代码,BS标志,成交价格,成交数量,叫卖序号,叫买序号\n"
        "300001.SZ,300001,20261118,93000001,20001, , ,B,123400,200,11,12\n",
    )
    target = tmp_path / "l2_trade.parquet"

    rows = convert_extracted_day(source, target, TRADE, date(2026, 11, 18))
    item = pq.read_table(target).to_pylist()[0]

    assert rows == 1
    assert item["trade_code"] is None
    assert item["order_code"] is None
    assert item["side"] == "B"
    assert item["price"] == 123400


def test_wind_collector_and_preset_bindings_are_registered() -> None:
    collector = COLLECTORS["wind_l2_sz"]
    assert set(collector.operations) == {
        "wind_l2_initial",
        "wind_l2_incremental",
    }
    assert all(
        set(operation.datasets) == {ORDER.dataset_id, TRADE.dataset_id}
        for operation in collector.operations.values()
    )
    contracts = {item.contract.id: item.contract for item in DATASET_PRESETS}
    assert [item.operation for item in contracts[ORDER.dataset_id].collection_bindings] == [
        "wind_l2_initial",
        "wind_l2_incremental",
    ]
    assert [item.operation for item in contracts[TRADE.dataset_id].collection_bindings] == [
        "wind_l2_initial",
        "wind_l2_incremental",
    ]


def test_wind_joint_collection_produces_both_outputs(tmp_path: Path, monkeypatch) -> None:
    run_date = date(2026, 11, 18)
    extracted = tmp_path / "downloads" / "wind_l2" / "extracted" / "20261118"
    extracted.mkdir(parents=True)

    def fake_archive(_run_date: date, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()

    def fake_convert(_source: Path, target: Path, spec, _expected: date) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(spec.schema.empty_table(), target)
        return 10 if spec.key == "order" else 20

    monkeypatch.setattr(pipeline, "ensure_archive", fake_archive)
    monkeypatch.setattr(pipeline, "_extract", lambda *_args: extracted)
    monkeypatch.setattr(pipeline, "convert_extracted_day", fake_convert)

    result = pipeline.collect_wind_l2(
        CollectionContext("run", tmp_path / "staging", "", data_root=tmp_path),
        {"trade_date": run_date.isoformat()},
        [],
    )

    assert set(result.outputs) == {ORDER.dataset_id, TRADE.dataset_id}
    assert result.outputs[ORDER.dataset_id][0].row_count == 10
    assert result.outputs[TRADE.dataset_id][0].row_count == 20
    assert not extracted.exists()
