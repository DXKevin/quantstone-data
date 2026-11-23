import json

from quantstone_data.review_reports import (
    build_directory_import_review,
    write_collection_review,
)


def test_directory_import_review_contains_ready_partitions(tmp_path) -> None:
    manifest = {
        "files": [
            {
                "partition_key": "2026-11-18",
                "status": "ready",
                "row_count": 12,
                "errors": [],
            },
            {
                "partition_key": "2026-11-19",
                "status": "invalid",
                "row_count": 0,
                "errors": [{"rule": "missing_file"}],
            },
        ]
    }

    report = build_directory_import_review("demo.cn.stock.tick", manifest)
    relative_path = write_collection_review(tmp_path, "job-id", report)

    assert report["passed"] is True
    assert report["row_count"] == 12
    assert report["error_count"] == 0
    assert [item["partition_key"] for item in report["runs"]] == ["2026-11-18"]
    stored = json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))
    assert stored == report
