from __future__ import annotations

from datetime import date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from quantstone_data.field_types import (
    DATA_TYPE_NAMES,
    arrow_type,
    normalize_value,
)
from quantstone_data.main import create_app

CASES = [
    ("string", "000001", "000001"),
    ("int32", 1, 1),
    ("int64", 1, 1),
    ("float32", 1.5, 1.5),
    ("float64", 1.5, 1.5),
    ("boolean", True, True),
    ("date", "20261119", date(2026, 11, 19)),
    ("timestamp", "2026-11-19 09:30:00.123456", datetime(2026, 11, 19, 9, 30, 0, 123456)),
]


def test_supported_types_round_trip_through_parquet(tmp_path) -> None:
    for data_type, source, expected in CASES:
        value = normalize_value(source, data_type)
        table = pa.Table.from_pylist(
            [{"value": value}],
            schema=pa.schema([pa.field("value", arrow_type(data_type))]),
        )
        path = tmp_path / f"{data_type}.parquet"
        pq.write_table(table, path)
        result = pq.read_table(path)
        assert result.schema.field("value").type == arrow_type(data_type)
        assert result.to_pylist()[0]["value"] == expected


def test_normalize_date_accepts_date_objects() -> None:
    assert normalize_value(date(2026, 11, 19), "date") == date(2026, 11, 19)
    assert normalize_value(datetime(2026, 11, 19, 9, 30), "date") == date(2026, 11, 19)


def test_empty_values_stay_empty() -> None:
    assert normalize_value(None, "date") is None
    assert normalize_value("", "string") is None


def test_unsupported_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="不支持的数据类型"):
        arrow_type("decimal")
    with pytest.raises(ValueError, match="不支持的数据类型"):
        normalize_value("1.23", "decimal")


def test_timestamp_rejects_timezone_aware_values() -> None:
    with pytest.raises(ValueError, match="无时区"):
        normalize_value("2026-11-19T09:30:00+08:00", "timestamp")


def test_dataset_api_rejects_unsupported_field_type(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    payload = {
        "id": "sample.cn.stock.demo",
        "provider": "sample",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "demo",
        "display_name": "类型校验样例",
        "primary_key": ["ts_code"],
        "fields": [
            {
                "name": "ts_code",
                "data_type": "decimal(10,2)",
                "nullable": False,
                "description": "代码",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/datasets", json=payload)
    assert response.status_code == 422
    assert "不支持的数据类型" in response.text


def test_data_type_names_match_parquet_mapping() -> None:
    assert set(DATA_TYPE_NAMES) == {item[0] for item in CASES}
