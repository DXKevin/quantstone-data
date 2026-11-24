from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tushare_cn_stock import index_basic
from quantstone_data.dataset_presets import DATASET_PRESETS


def test_index_basic_collects_every_market_and_normalizes_contract(
    tmp_path: Path, monkeypatch
) -> None:
    requested: list[str] = []

    def fake_call(
        _token: str,
        market: str,
        _fields: list[str],
        *,
        offset: int,
        limit: int,
    ) -> list[dict]:
        assert offset == 0
        assert limit == index_basic.PAGE_LIMIT
        requested.append(market)
        return [
            {
                "ts_code": f"{market}.TI",
                "name": market,
                "fullname": None,
                "market": market,
                "publisher": "发布方",
                "index_type": None,
                "category": "规模指数",
                "base_date": "20000101",
                "base_point": 1000.0,
                "list_date": "20010101",
                "weight_rule": None,
                "desc": None,
                "exp_date": None,
            }
        ]

    monkeypatch.setattr(index_basic, "call_api", fake_call)
    preset = next(
        item.contract for item in DATASET_PRESETS if item.contract.id == index_basic.DATASET_ID
    )
    fields = [field.model_dump() for field in preset.fields]
    result = index_basic.collect(
        CollectionContext("run", tmp_path / "staging", "token"), fields
    )
    artifact = result.outputs[index_basic.DATASET_ID][0]
    table = pq.read_table(artifact.path)

    assert requested == list(index_basic.MARKETS)
    assert table.num_rows == len(index_basic.MARKETS)
    assert table.column("base_date")[0].as_py() == date(2000, 1, 1)
    assert table.column("list_date")[0].as_py() == date(2001, 1, 1)


def test_index_basic_paginates_full_market_pages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(index_basic, "PAGE_LIMIT", 2)
    offsets: list[int] = []

    def fake_call(
        _token: str,
        _market: str,
        _fields: list[str],
        *,
        offset: int,
        limit: int,
    ) -> list[dict]:
        offsets.append(offset)
        rows = [
            {"ts_code": "000001.SH", "name": "一"},
            {"ts_code": "000002.SH", "name": "二"},
            {"ts_code": "000003.SH", "name": "三"},
        ]
        return rows[offset : offset + limit]

    monkeypatch.setattr(index_basic, "call_api", fake_call)
    fields = [
        {
            "name": "ts_code",
            "source_name": "ts_code",
            "data_type": "string",
            "nullable": False,
        },
        {
            "name": "name",
            "source_name": "name",
            "data_type": "string",
            "nullable": False,
        },
    ]
    result = index_basic.collect(
        CollectionContext("run", tmp_path / "staging", "token"), fields, markets=("SSE",)
    )

    assert offsets == [0, 2]
    assert result.outputs[index_basic.DATASET_ID][0].row_count == 3


def test_index_basic_preset_is_complete() -> None:
    preset = next(
        item.contract for item in DATASET_PRESETS if item.contract.id == index_basic.DATASET_ID
    )
    assert preset.instrument == "index"
    assert preset.storage_policy.layout == "snapshot"
    nullable = {field.name: field.nullable for field in preset.fields}
    assert nullable["base_date"] is True
    assert nullable["base_point"] is True
    assert nullable["list_date"] is True
    assert [field.name for field in preset.fields] == [
        "ts_code",
        "name",
        "fullname",
        "market",
        "publisher",
        "index_type",
        "category",
        "base_date",
        "base_point",
        "list_date",
        "weight_rule",
        "desc",
        "exp_date",
    ]
