from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.collection_protocol import CollectionContext
from quantstone_data.collectors.tb_lqsj_ths import sector_categories
from quantstone_data.dataset_presets import DATASET_PRESETS
from quantstone_data.field_types import arrow_type
from quantstone_data.models import DatasetField, DatasetSchemaVersion
from quantstone_data.reviewer_types import ReviewContext
from quantstone_data.reviewers.tb_lqsj_ths.cn.index.sector_categories.reviewer import review


def _contract():
    return next(
        item.contract
        for item in DATASET_PRESETS
        if item.contract.id == sector_categories.DATASET_ID
    )


def _fields() -> list[dict]:
    return [item.model_dump() for item in _contract().fields]


def _row(code: int, sector_type: str = "N") -> dict:
    return {
        "index_code": f"{code:06d}.TI",
        "name": f"板块{code}",
        "count": code % 100,
        "exchange": "A",
        "list_date": "20260102",
        "type": sector_type,
        "code": f"{code:06d}",
    }


def test_sector_categories_collects_all_pages(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sector_categories, "PAGE_SIZE", 2)
    calls: list[int] = []

    def fake_call(_api_key: str, page: int, page_size: int = 2):
        assert page_size == 2
        calls.append(page)
        rows = [_row(1, "BB"), _row(2, "I"), _row(3, "N")]
        return len(rows), rows[page * page_size : (page + 1) * page_size]

    monkeypatch.setattr(sector_categories, "call_api", fake_call)
    result = sector_categories.collect(
        CollectionContext("run", tmp_path / "staging", "api-key"), _fields()
    )
    artifact = result.outputs[sector_categories.DATASET_ID][0]
    table = pq.read_table(artifact.path)

    assert calls == [0, 1]
    assert artifact.row_count == 3
    assert table.column("index_code").to_pylist() == ["000001.TI", "000002.TI", "000003.TI"]
    assert table.column("list_date")[0].as_py() == date(2026, 1, 2)
    assert result.provenance["reported_total"] == 3


def test_sector_categories_reviewer_accepts_valid_snapshot(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    rows = [{**_row(1, "BB"), "list_date": date(2026, 1, 2)}, {**_row(2), "list_date": None}]
    path = tmp_path / "snapshot.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    dataset_schema = DatasetSchemaVersion(version=1, primary_key="index_code", time_field=None)
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

    report = review(ReviewContext(path, dataset_schema))
    assert report.passed, report.errors


def test_sector_categories_reviewer_rejects_unknown_type(tmp_path) -> None:
    fields = _fields()
    schema = pa.schema(
        [pa.field(item["name"], arrow_type(item["data_type"]), item["nullable"]) for item in fields]
    )
    row = {**_row(1, "UNKNOWN"), "list_date": date(2026, 1, 2)}
    path = tmp_path / "snapshot.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=schema), path)
    dataset_schema = DatasetSchemaVersion(version=1, primary_key="index_code", time_field=None)
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

    report = review(ReviewContext(path, dataset_schema))
    assert not report.passed
    assert any(error.get("code") == "invalid_sector_type" for error in report.errors)
