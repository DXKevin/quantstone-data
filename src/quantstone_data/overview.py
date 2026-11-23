"""数据集级概览：把 Catalog 与存储信息聚合成一张数据卡，并提供覆盖热力图。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_session
from .models import CatalogFile, CatalogPartition, CollectionJob, CollectionRun, Dataset

router = APIRouter(prefix="/overview", tags=["overview"])
SessionDep = Annotated[Session, Depends(get_session)]

FAILED_RUN_STATUSES = ("failed", "review_failed")
COVERAGE_DEFAULT_DAYS = 90
DAILY_COMPLETION_DEFAULT_DAYS = 30
COVERAGE_MIN_DAYS = 7
COVERAGE_MAX_DAYS = 400


def _coverage_percent(completed: int, expected: int) -> float | None:
    if expected <= 0:
        return None
    if completed >= expected:
        return 100.0
    return min(round(completed * 100 / expected, 1), 99.9)


def _daily_completion_total(rows: list[dict]) -> dict:
    """汇总所有日更数据集的应完成项，避免对各数据集百分比做简单平均。"""
    complete = sum(int(row.get("complete", 0)) for row in rows)
    expected = sum(int(row.get("expected", 0)) for row in rows)
    return {
        "complete": complete,
        "expected": expected,
        "completion_percent": _coverage_percent(complete, expected),
        "missing": sum(int(row.get("missing", 0)) for row in rows),
        "failed": sum(int(row.get("failed", 0)) for row in rows),
        "abnormal": sum(int(row.get("abnormal", 0)) for row in rows),
        "pending": sum(int(row.get("pending", 0)) for row in rows),
    }


def describe_review_errors(errors: list[dict]) -> str:
    """把审核规则错误压缩成一句可读的中文说明。"""
    parts: list[str] = []
    for item in errors:
        rule = item.get("rule")
        if rule == "not_empty":
            parts.append("接口返回 0 行")
        elif rule == "required_fields":
            missing = ", ".join(item.get("missing") or [])
            parts.append(f"缺少字段：{missing}" if missing else "缺少必需字段")
        elif rule == "primary_key_not_null":
            parts.append("主键存在空值")
        elif rule == "primary_key_unique":
            parts.append("主键存在重复记录")
        elif rule == "partition_matches_trade_date":
            expected = item.get("expected")
            actual = item.get("actual")
            parts.append(f"分区日期不一致（期望 {expected}，实际 {actual}）")
        else:
            detail = item.get("message") or item.get("detail")
            parts.append(f"{rule}：{detail}" if detail else str(rule))
    return "；".join(part for part in parts if part)


def _review_errors_by_partition(data_root: Path, job: CollectionJob | None) -> dict[str, str]:
    if job is None or not job.staged_path:
        return {}
    path = data_root / job.staged_path
    if path.name != "review.json":
        path = path.parent / "review.json"
    if not path.is_file():
        return {}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, str] = {}
    for run in report.get("runs") or []:
        key = run.get("partition_key")
        if key and not run.get("passed"):
            result[key] = describe_review_errors(run.get("errors") or []) or "审核未通过"
    return result


def _open_days(data_root, catalog: CatalogPartition | None) -> list[date]:
    if catalog is None:
        return []
    path = data_root / catalog.file_path
    if not path.is_file():
        return []
    table = pq.read_table(path, columns=["cal_date", "is_open"])
    return [row["cal_date"] for row in table.to_pylist() if row["is_open"] == 1]


def _serialize_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    # SQLite 会丢失 DateTime(timezone=True) 的时区信息；项目写入的时间均为 UTC。
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


@router.get("/collection")
def collection_overview(session: SessionDep) -> dict:
    counts = dict(
        session.execute(
            select(CollectionJob.status, func.count(CollectionJob.id)).group_by(
                CollectionJob.status
            )
        ).all()
    )
    # SQLite 保存的是无时区的 UTC 时间，这里用同样口径计算最近 24 小时。
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    succeeded_24h = session.scalar(
        select(func.count())
        .select_from(CollectionJob)
        .where(
            CollectionJob.status == "succeeded",
            CollectionJob.updated_at >= since,
        )
    )
    failed_24h = session.scalar(
        select(func.count())
        .select_from(CollectionJob)
        .where(
            CollectionJob.status.in_(("failed", "review_failed")),
            CollectionJob.updated_at >= since,
        )
    )
    last_completed_at = session.scalar(
        select(func.max(CollectionJob.updated_at)).where(
            CollectionJob.status == "succeeded"
        )
    )
    recent_jobs = session.scalars(
        select(CollectionJob)
        .order_by(CollectionJob.created_at.desc(), CollectionJob.id.desc())
        .limit(5)
    ).all()
    dataset_names = dict(session.execute(select(Dataset.id, Dataset.display_name)).all())
    return {
        "total_jobs": sum(counts.values()),
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0) + counts.get("cancelling", 0),
        "awaiting_file": counts.get("awaiting_file", 0),
        "staged": counts.get("staged", 0),
        "succeeded_24h": succeeded_24h or 0,
        "failed_24h": failed_24h or 0,
        "last_completed_at": _serialize_timestamp(last_completed_at),
        "recent_jobs": [
            {
                "id": job.id,
                "dataset_id": job.dataset_id,
                "display_name": dataset_names.get(job.dataset_id, job.dataset_id),
                "operation": job.operation,
                "input_method": job.input_method,
                "status": job.status,
                "updated_at": _serialize_timestamp(job.updated_at),
            }
            for job in recent_jobs
        ],
    }


@router.get("/datasets")
def dataset_overview(request: Request, session: SessionDep) -> list[dict]:
    data_root = request.app.state.data_root
    datasets = list(session.scalars(select(Dataset).order_by(Dataset.id)))
    aggregates = {
        row[0]: row
        for row in session.execute(
            select(
                CatalogPartition.dataset_id,
                func.count(CatalogPartition.id),
                func.min(CatalogPartition.partition_key),
                func.max(CatalogPartition.partition_key),
                func.max(CatalogPartition.published_at),
            ).group_by(CatalogPartition.dataset_id)
        )
    }
    file_aggregates = {
        row[0]: row
        for row in session.execute(
            select(
                CatalogFile.dataset_id,
                func.count(CatalogFile.id),
                func.coalesce(func.sum(CatalogFile.row_count), 0),
                func.coalesce(func.sum(CatalogFile.size_bytes), 0),
            ).group_by(CatalogFile.dataset_id)
        )
    }
    missing: dict[str, int] = {}
    for item in session.scalars(select(CatalogFile)):
        if not (data_root / item.path).is_file():
            missing[item.dataset_id] = missing.get(item.dataset_id, 0) + 1

    calendars: dict[str, list[date]] = {}
    for dataset in datasets:
        policy = dataset.storage_policy or {}
        calendar_id = policy.get("calendar_dataset_id")
        if not calendar_id or calendar_id in calendars:
            continue
        latest = session.scalar(
            select(CatalogPartition)
            .where(CatalogPartition.dataset_id == calendar_id)
            .order_by(CatalogPartition.published_at.desc())
            .limit(1)
        )
        calendars[calendar_id] = _open_days(data_root, latest)

    overview: list[dict] = []
    today = date.today()
    for dataset in datasets:
        policy = dataset.storage_policy or {}
        row = aggregates.get(dataset.id)
        partitions = int(row[1]) if row else 0
        first_partition = row[2] if row else None
        latest_partition = row[3] if row else None
        published_at = _serialize_timestamp(row[4]) if row else None
        file_row = file_aggregates.get(dataset.id)
        files = int(file_row[1]) if file_row else 0
        rows = int(file_row[2]) if file_row else 0
        size_bytes = int(file_row[3]) if file_row else 0

        expected_partitions: int | None = None
        coverage_percent: float | None = None
        calendar_id = policy.get("calendar_dataset_id")
        open_days = calendars.get(calendar_id or "", [])
        if open_days and first_partition:
            try:
                start = date.fromisoformat(first_partition)
            except ValueError:
                start = None
            if start is not None:
                upper = min(today, max(open_days))
                expected_partitions = sum(1 for item in open_days if start <= item <= upper)
                coverage_percent = _coverage_percent(partitions, expected_partitions)

        overview.append(
            {
                "dataset_id": dataset.id,
                "display_name": dataset.display_name,
                "status": dataset.status,
                "provider": dataset.provider,
                "region": dataset.region,
                "instrument": dataset.instrument,
                "market": dataset.market,
                "layout": policy.get("layout"),
                "calendar_dataset_id": calendar_id,
                "partitions": partitions,
                "files": files,
                "rows": rows,
                "size_bytes": size_bytes,
                "first_partition": first_partition,
                "latest_partition": latest_partition,
                "published_at": published_at,
                "missing_files": missing.get(dataset.id, 0),
                "expected_partitions": expected_partitions,
                "coverage_percent": coverage_percent,
            }
        )
    return overview

def build_coverage_cells(
    dates: list[date],
    partitions: dict[str, CatalogPartition],
    missing_files: set[str],
    failures: dict[str, str | None],
    today: date,
) -> tuple[dict[str, str], dict[str, dict]]:
    """为每个交易日给出状态；优先级为文件异常 > 已发布 > 运行失败 > 缺失。"""
    cells: dict[str, str] = {}
    details: dict[str, dict] = {}
    for day in dates:
        key = day.isoformat()
        partition = partitions.get(key)
        if partition is not None:
            if key in missing_files:
                cells[key] = "abnormal"
                details[key] = {
                    "row_count": partition.row_count,
                    "file_path": partition.file_path,
                    "error": "Catalog 记录的文件不存在",
                }
            else:
                cells[key] = "complete"
                details[key] = {
                    "row_count": partition.row_count,
                    "file_path": partition.file_path,
                    "error": None,
                }
            continue
        if key in failures:
            cells[key] = "failed"
            details[key] = {
                "row_count": None,
                "file_path": None,
                "error": failures[key] or "采集或审核失败",
            }
            continue
        # 当天尚未采集属于正常状态，不算缺口。
        cells[key] = "pending" if day == today else "missing"
    return cells, details


@router.get("/daily-completion")
def daily_completion(
    request: Request,
    session: SessionDep,
    days: int = DAILY_COMPLETION_DEFAULT_DAYS,
) -> dict:
    """按日分区数据集的最近 N 个交易日汇总完成率。"""
    days = max(COVERAGE_MIN_DAYS, min(days, COVERAGE_MAX_DAYS))
    coverage = dataset_coverage(request, session, days)
    frequencies = dict(session.execute(select(Dataset.id, Dataset.update_frequency)).all())
    historical = dict(session.execute(select(Dataset.id, Dataset.is_historical)).all())
    rows: list[dict] = []
    for item in coverage["datasets"]:
        if historical.get(item["dataset_id"]) or frequencies.get(item["dataset_id"]) != "daily":
            continue
        cells: dict[str, str] = item["cells"]
        summary: dict[str, int] = item["summary"]
        latest_date = max(cells) if cells else None
        expected = (
            summary.get("complete", 0)
            + summary.get("missing", 0)
            + summary.get("failed", 0)
            + summary.get("abnormal", 0)
            + summary.get("pending", 0)
        )
        rows.append(
            {
                "dataset_id": item["dataset_id"],
                "display_name": item["display_name"],
                "layout": "date",
                "latest_trade_date": latest_date,
                "latest_status": cells.get(latest_date) if latest_date else None,
                "complete": summary.get("complete", 0),
                "expected": expected,
                "completion_percent": (
                    round(summary.get("complete", 0) * 100 / expected, 1)
                    if expected
                    else None
                ),
                "missing": summary.get("missing", 0),
                "failed": summary.get("failed", 0),
                "abnormal": summary.get("abnormal", 0),
                "pending": summary.get("pending", 0),
                "last_updated_at": None,
            }
        )

    latest_trade_date = coverage["dates"][-1] if coverage["dates"] else coverage["today"]
    latest_trade_day = date.fromisoformat(latest_trade_date)
    for dataset in session.scalars(select(Dataset).order_by(Dataset.id)):
        policy = dataset.storage_policy or {}
        if dataset.status != "active" or policy.get("layout") != "snapshot":
            continue
        if dataset.is_historical or dataset.update_frequency != "daily":
            continue
        last_published = session.scalar(
            select(func.max(CatalogPartition.published_at)).where(
                CatalogPartition.dataset_id == dataset.id
            )
        )
        last_job = session.scalar(
            select(func.max(CollectionJob.updated_at)).where(
                CollectionJob.dataset_id == dataset.id,
                CollectionJob.status == "succeeded",
            )
        )
        updates = [item for item in (last_published, last_job) if item is not None]
        last_updated = max(updates) if updates else None
        updated_day = last_updated.date() if last_updated is not None else None
        complete = updated_day is not None and updated_day >= latest_trade_day
        rows.append(
            {
                "dataset_id": dataset.id,
                "display_name": dataset.display_name,
                "layout": "snapshot",
                "latest_trade_date": latest_trade_date,
                "latest_status": "complete" if complete else "stale",
                "complete": 1 if complete else 0,
                "expected": 1,
                "completion_percent": 100.0 if complete else 0.0,
                "missing": 0 if complete else 1,
                "failed": 0,
                "abnormal": 0,
                "pending": 0,
                "last_updated_at": _serialize_timestamp(last_updated),
            }
        )

    return {
        "today": coverage["today"],
        "days": days,
        "dates": coverage["dates"],
        "total": _daily_completion_total(rows),
        "datasets": rows,
    }


@router.get("/coverage")
def dataset_coverage(
    request: Request,
    session: SessionDep,
    days: int = COVERAGE_DEFAULT_DAYS,
) -> dict:
    days = max(COVERAGE_MIN_DAYS, min(days, COVERAGE_MAX_DAYS))
    data_root: Path = request.app.state.data_root
    targets: list[tuple[Dataset, str]] = []
    for dataset in session.scalars(select(Dataset).order_by(Dataset.id)):
        policy = dataset.storage_policy or {}
        if dataset.is_historical:
            continue
        calendar_id = policy.get("calendar_dataset_id")
        if policy.get("logical_partition_field") and calendar_id:
            targets.append((dataset, calendar_id))

    calendars: dict[str, list[date]] = {}
    for calendar_id in {item for _, item in targets}:
        latest = session.scalar(
            select(CatalogPartition)
            .where(CatalogPartition.dataset_id == calendar_id)
            .order_by(CatalogPartition.published_at.desc())
            .limit(1)
        )
        calendars[calendar_id] = _open_days(data_root, latest)

    today = date.today()
    axis: list[date] = []
    rows: list[dict] = []
    for dataset, calendar_id in targets:
        open_days = [item for item in calendars.get(calendar_id, []) if item <= today]
        dates = open_days[-days:]
        if not dates:
            rows.append(
                {
                    "dataset_id": dataset.id,
                    "display_name": dataset.display_name,
                    "cells": {},
                    "details": {},
                    "summary": {},
                }
            )
            continue
        if len(dates) > len(axis):
            axis = dates
        partitions = {
            item.partition_key: item
            for item in session.scalars(
                select(CatalogPartition).where(CatalogPartition.dataset_id == dataset.id)
            )
        }
        missing_files = {
            key
            for key, item in partitions.items()
            if not (data_root / item.file_path).is_file()
        }
        failures: dict[str, str | None] = {}
        review_cache: dict[str, dict[str, str]] = {}
        for key, run_error, job_id in session.execute(
            select(CollectionRun.partition_key, CollectionRun.error, CollectionRun.job_id)
            .join(CollectionJob, CollectionJob.id == CollectionRun.job_id)
            .where(
                CollectionJob.dataset_id == dataset.id,
                CollectionJob.status != "cancelled",
                CollectionRun.status.in_(FAILED_RUN_STATUSES),
            )
        ).all():
            if failures.get(key):
                continue
            text = run_error
            if not text:
                if job_id not in review_cache:
                    review_cache[job_id] = _review_errors_by_partition(
                        data_root, session.get(CollectionJob, job_id)
                    )
                text = review_cache[job_id].get(key)
            failures[key] = text or "采集或审核失败"

        cells, details = build_coverage_cells(
            dates, partitions, missing_files, failures, today
        )
        summary = {
            status: sum(1 for value in cells.values() if value == status)
            for status in ("complete", "missing", "failed", "abnormal", "pending")
        }
        rows.append(
            {
                "dataset_id": dataset.id,
                "display_name": dataset.display_name,
                "cells": cells,
                "details": details,
                "summary": summary,
            }
        )

    return {
        "today": today.isoformat(),
        "dates": [item.isoformat() for item in axis],
        "datasets": rows,
    }
