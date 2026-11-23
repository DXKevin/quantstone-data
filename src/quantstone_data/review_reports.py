import json
from pathlib import Path


def build_directory_import_review(dataset_id: str, manifest: dict) -> dict:
    """将扫描阶段逐文件审核结果整理为采集任务通用审核报告。"""
    runs = []
    for entry in manifest.get("files", []):
        if entry.get("status") != "ready":
            continue
        errors = list(entry.get("errors") or [])
        runs.append(
            {
                "reviewer": dataset_id,
                "passed": not errors,
                "row_count": int(entry.get("row_count") or 0),
                "error_count": len(errors),
                "errors": errors,
                "partition_key": entry.get("partition_key"),
            }
        )
    return {
        "reviewer": dataset_id,
        "passed": bool(runs) and all(item["passed"] for item in runs),
        "row_count": sum(item["row_count"] for item in runs),
        "error_count": sum(item["error_count"] for item in runs),
        "runs": runs,
    }


def write_collection_review(data_root: Path, collection_job_id: str, report: dict) -> str:
    report_path = data_root / "staging" / collection_job_id / "review.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path.relative_to(data_root).as_posix()
