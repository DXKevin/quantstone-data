from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from quantstone_data.main import create_app
from quantstone_data.overview import build_coverage_cells, describe_review_errors

TODAY = date(2026, 11, 18)


def partition(key: str, rows: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        partition_key=key,
        row_count=rows,
        file_path=f"datasets/demo/delta/{key}.parquet",
    )


def test_coverage_cells_cover_all_states() -> None:
    dates = [date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 19)]
    partitions = {
        "2026-11-16": partition("2026-11-16"),
        "2026-11-17": partition("2026-11-17"),
    }
    missing_files = {"2026-11-17"}
    failures = {"2026-11-18": "频率超限"}

    cells, details = build_coverage_cells(
        dates,
        partitions,
        missing_files,
        failures,
        TODAY,
    )

    assert cells["2026-11-16"] == "complete"
    assert cells["2026-11-17"] == "abnormal"
    assert cells["2026-11-18"] == "failed"
    assert cells["2026-11-19"] == "future"
    assert details["2026-11-16"]["row_count"] == 100
    assert details["2026-11-18"]["error"] == "频率超限"
    assert cells.get("2026-11-20") is None


def test_coverage_cells_mark_missing_partition() -> None:
    cells, details = build_coverage_cells(
        [date(2026, 11, 17)],
        {},
        set(),
        {},
        TODAY,
    )

    assert cells["2026-11-17"] == "missing"
    assert details == {}


def test_today_without_partition_is_pending() -> None:
    cells, _ = build_coverage_cells([TODAY], {}, set(), {}, TODAY)

    assert cells[TODAY.isoformat()] == "pending"


def test_describe_review_errors() -> None:
    text = describe_review_errors(
        [
            {"rule": "not_empty"},
            {
                "rule": "partition_matches_trade_date",
                "expected": "2026-11-18",
                "actual": ["2026-11-17"],
            },
        ]
    )

    assert "接口返回 0 行" in text
    assert "2026-11-18" in text


def test_coverage_endpoint_without_calendar_datasets(tmp_path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/overview/coverage?days=30")

    assert response.status_code == 200
    body = response.json()
    assert body["dates"] == []
    assert body["datasets"] == []
