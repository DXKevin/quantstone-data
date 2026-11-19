import hashlib
import json
import logging
import shutil
import threading
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Annotated
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .collection_protocol import CollectionContext, RateLimitExceeded
from .collection_schemas import (
    CollectionJobCreate,
    CollectionJobRead,
    CollectionJobStatus,
    InputMethod,
)
from .collector_registry import get_operation, validate_operation_parameters
from .collectors.tushare_cn_stock.definition import DAILY_DATASET_ID
from .collectors.tushare_cn_stock.stock_basic import CollectionError, load_token
from .database import get_session
from .execution import run_operation
from .logging_config import log_event
from .models import CatalogPartition, CollectionJob, CollectionRun, Dataset, DatasetSchemaVersion
from .publishing import publish_partition
from .reviewer_registry import review_dataset
from .reviewer_types import ReviewContext
from .schemas import DatasetStatus

router = APIRouter(prefix="/collection-jobs", tags=["collection jobs"])
SessionDep = Annotated[Session, Depends(get_session)]

# 进程内记录正在执行的任务和取消请求；单进程部署下即可生效。
_RUNNING_JOBS: set[str] = set()
_QUEUED_JOBS: set[str] = set()
_CANCEL_REQUESTS: set[str] = set()
_PUBLISHING_JOBS: set[str] = set()
_JOB_STATE_LOCK = threading.Lock()

TERMINAL_JOB_STATUSES = {
    CollectionJobStatus.SUCCEEDED.value,
    CollectionJobStatus.FAILED.value,
    CollectionJobStatus.REVIEW_PASSED.value,
    CollectionJobStatus.REVIEW_FAILED.value,
    CollectionJobStatus.CANCELLED.value,
}
RETRYABLE_JOB_STATUSES = {
    CollectionJobStatus.FAILED.value,
    CollectionJobStatus.REVIEW_FAILED.value,
    CollectionJobStatus.CANCELLED.value,
}

INTERRUPTED_JOB_ERROR = "应用重启时任务仍处于执行状态，已标记为失败；请新建任务继续。"


def serialize_job(job: CollectionJob) -> CollectionJobRead:
    return CollectionJobRead.model_validate(job, from_attributes=True)


def recover_interrupted_jobs(session: Session) -> int:
    """应用启动时结束上一次进程遗留的执行中任务。"""
    jobs = list(
        session.scalars(
            select(CollectionJob).where(
                CollectionJob.status.in_(
                    (
                        CollectionJobStatus.RUNNING.value,
                        CollectionJobStatus.QUEUED.value,
                        CollectionJobStatus.CANCELLING.value,
                    )
                )
            )
        )
    )
    for job in jobs:
        job.status = CollectionJobStatus.FAILED.value
        job.error = INTERRUPTED_JOB_ERROR
    if jobs:
        session.commit()
    return len(jobs)


def _failure_message(error: Exception) -> str:
    if isinstance(error, HTTPException):
        return str(error.detail)
    return str(error) or error.__class__.__name__


def _upstream_failure_message(error: Exception) -> str:
    if isinstance(error, HTTPError):
        reason = f" {error.reason}" if error.reason else ""
        return f"上游数据服务暂时不可用（HTTP {error.code}{reason}），采集器重试后仍失败"
    if isinstance(error, URLError):
        return f"无法连接上游数据服务，采集器重试后仍失败：{error.reason}"
    if isinstance(error, RateLimitExceeded):
        return f"上游数据服务限流，采集器重试后仍失败：{error}"
    return str(error) or error.__class__.__name__


def _is_upstream_failure(error: Exception) -> bool:
    return isinstance(error, (CollectionError, URLError, RateLimitExceeded))


def _mark_job_failed(session: Session, job_id: str, error: Exception) -> None:
    """确保所有执行路径最终都把异常持久化到任务记录。"""
    session.rollback()
    job = session.get(CollectionJob, job_id)
    if job is None:
        return
    message = _failure_message(error)
    if job.status in {
        CollectionJobStatus.CREATED.value,
        CollectionJobStatus.QUEUED.value,
        CollectionJobStatus.RUNNING.value,
        CollectionJobStatus.CANCELLING.value,
        CollectionJobStatus.FAILED.value,
    }:
        job.status = CollectionJobStatus.FAILED.value
        job.error = message
        session.commit()
    log_event(
        "collection_job_failed",
        level=logging.ERROR,
        job_id=job_id,
        dataset_id=job.dataset_id,
        error=message,
    )


def _finish_snapshot_cancellation(
    session: Session,
    job: CollectionJob,
    run: CollectionRun,
    run_directory: Path,
    report_path: Path | None = None,
) -> CollectionJobRead:
    run.status = "cancelled"
    run.staged_path = None
    run.error = None
    job.status = CollectionJobStatus.CANCELLED.value
    job.staged_path = None
    job.error = None
    shutil.rmtree(run_directory, ignore_errors=True)
    if report_path is not None:
        report_path.unlink(missing_ok=True)
    session.commit()
    session.refresh(job)
    log_event(
        "collection_job_cancelled",
        job_id=job.id,
        dataset_id=job.dataset_id,
    )
    return serialize_job(job)


def _cancel_snapshot_at_boundary(
    session: Session,
    job: CollectionJob,
    run: CollectionRun,
    run_directory: Path,
    report_path: Path | None = None,
) -> CollectionJobRead | None:
    with _JOB_STATE_LOCK:
        session.refresh(job)
        if (
            job.id not in _CANCEL_REQUESTS
            and job.status != CollectionJobStatus.CANCELLING.value
        ):
            return None
        return _finish_snapshot_cancellation(
            session,
            job,
            run,
            run_directory,
            report_path,
        )


def _begin_snapshot_publish(
    session: Session,
    job: CollectionJob,
    run: CollectionRun,
    run_directory: Path,
    report_path: Path,
) -> CollectionJobRead | None:
    """在同一临界区内确认未取消并进入不可取消的发布阶段。"""
    with _JOB_STATE_LOCK:
        session.refresh(job)
        if (
            job.id in _CANCEL_REQUESTS
            or job.status == CollectionJobStatus.CANCELLING.value
        ):
            return _finish_snapshot_cancellation(
                session,
                job,
                run,
                run_directory,
                report_path,
            )
        _PUBLISHING_JOBS.add(job.id)
        return None


def _finalize_snapshot_review_failure(
    session: Session,
    job: CollectionJob,
    run: CollectionRun,
    run_directory: Path,
    report_path: Path,
    data_root: Path,
) -> CollectionJobRead | None:
    """在同一临界区内处理取消请求或固化审核失败状态。"""
    with _JOB_STATE_LOCK:
        session.refresh(job)
        if (
            job.id in _CANCEL_REQUESTS
            or job.status == CollectionJobStatus.CANCELLING.value
        ):
            return _finish_snapshot_cancellation(
                session,
                job,
                run,
                run_directory,
                report_path,
            )
        run.status = "review_failed"
        job.status = CollectionJobStatus.REVIEW_FAILED.value
        job.staged_path = report_path.relative_to(data_root).as_posix()
        session.commit()
        return None


def _trading_dates(
    dataset: Dataset,
    start_date: date,
    end_date: date,
    data_root: Path,
    session: Session,
) -> list[date]:
    policy = dataset.storage_policy or {}
    calendar_id = policy.get("calendar_dataset_id")
    calendar = session.get(Dataset, calendar_id) if calendar_id else None
    if calendar is None:
        raise HTTPException(
            status_code=409,
            detail=f"请先创建交易日历数据集：{calendar_id or '尚未配置 calendar_dataset_id'}",
        )
    if calendar.status != DatasetStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail=f"请先启用交易日历数据集：{calendar_id}")
    catalog = session.scalar(
        select(CatalogPartition)
        .where(CatalogPartition.dataset_id == calendar_id)
        .order_by(CatalogPartition.published_at.desc())
        .limit(1)
    )
    if catalog is None:
        raise HTTPException(
            status_code=409,
            detail=f"交易日历尚无已发布数据，请先采集交易日历：{calendar_id}",
        )
    calendar_path = data_root / catalog.file_path
    if not calendar_path.is_file():
        raise HTTPException(
            status_code=409,
            detail=f"交易日历文件缺失，请重新发布交易日历：{calendar_id}",
        )
    table = pq.read_table(calendar_path, columns=["cal_date", "is_open"])
    rows = table.to_pylist()
    available_dates = [row["cal_date"] for row in rows]
    if not available_dates or start_date < min(available_dates) or end_date > max(available_dates):
        coverage = (
            f"{min(available_dates)} 至 {max(available_dates)}"
            if available_dates
            else "无有效日期"
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"交易日历覆盖不足（当前 {coverage}），请先更新交易日历至 "
                f"{start_date} 至 {end_date}"
            ),
        )
    return sorted(
        row["cal_date"]
        for row in rows
        if row["is_open"] == 1 and start_date <= row["cal_date"] <= end_date
    )


def _execute_daily_job(
    job: CollectionJob,
    operation,
    dataset: Dataset,
    schema: DatasetSchemaVersion,
    data_root: Path,
    session: Session,
) -> CollectionJobRead:
    if job.operation == "incremental" and job.start_date is None:
        latest_partition = session.scalar(
            select(CatalogPartition.partition_key)
            .where(CatalogPartition.dataset_id == job.dataset_id)
            .order_by(CatalogPartition.partition_key.desc())
            .limit(1)
        )
        if latest_partition is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "incremental collection requires an existing partition; "
                    "run initial collection first"
                ),
            )
        job.start_date = date.fromisoformat(latest_partition) + timedelta(days=1)
        configured_end = job.parameters.get("end_date")
        job.end_date = date.fromisoformat(configured_end) if configured_end else date.today()

    if job.start_date is None or job.end_date is None:
        raise HTTPException(status_code=422, detail="daily collection requires a date range")
    if not dataset.storage_policy:
        raise HTTPException(status_code=409, detail="dataset has no storage policy")

    fields = [
        {
            "name": field.name,
            "source_name": field.source_name,
            "data_type": field.data_type,
            "nullable": field.nullable,
        }
        for field in schema.fields
    ]
    reports: list[dict] = []
    token = load_token()
    for trade_date in _trading_dates(
        dataset,
        job.start_date,
        job.end_date,
        data_root,
        session,
    ):
        if job.id in _CANCEL_REQUESTS:
            job.status = CollectionJobStatus.CANCELLED.value
            session.commit()
            session.refresh(job)
            log_event(
                "collection_job_cancelled",
                job_id=job.id,
                dataset_id=job.dataset_id,
            )
            return serialize_job(job)

        partition_key = trade_date.isoformat()
        run = session.scalar(
            select(CollectionRun).where(
                CollectionRun.job_id == job.id,
                CollectionRun.partition_key == partition_key,
            )
        )
        if run is None:
            run = CollectionRun(
                id=str(uuid4()),
                job_id=job.id,
                partition_key=partition_key,
                status="fetching",
            )
            session.add(run)
            session.flush()
        elif run.status == "succeeded":
            continue

        run_directory = data_root / "staging" / job.id / run.id
        context = CollectionContext(run.id, run_directory, token)
        try:
            log_event(
                "collection_run_started",
                job_id=job.id,
                run_id=run.id,
                dataset_id=job.dataset_id,
                collector=job.collector_key,
                operation=job.collector_operation,
                partition_key=partition_key,
            )
            result = run_operation(
                job.collector_key or "unknown",
                operation,
                partial(operation.function, context, {"trade_date": partition_key}, fields),
                job_id=job.id,
            )
            if set(result.outputs) != set(operation.datasets):
                raise CollectionError("collector outputs do not match operation declaration")
            artifact = result.outputs[job.dataset_id][0]
            log_event(
                "collection_artifact_staged",
                job_id=job.id,
                run_id=run.id,
                dataset_id=job.dataset_id,
                partition_key=partition_key,
                row_count=artifact.row_count,
            )
            report = review_dataset(
                job.dataset_id,
                ReviewContext(artifact.path, schema, trade_date),
            ).as_dict()
            report["partition_key"] = partition_key
            reports.append(report)
            run.staged_path = artifact.path.relative_to(data_root).as_posix()
            run.row_count = artifact.row_count
            log_event(
                "review_completed",
                job_id=job.id,
                run_id=run.id,
                dataset_id=job.dataset_id,
                partition_key=partition_key,
                passed=report["passed"],
                error_count=report["error_count"],
            )
            if not report["passed"]:
                run.status = "review_failed"
                job.status = CollectionJobStatus.REVIEW_FAILED.value
                session.commit()
                break

            publish_partition(
                session,
                data_root=data_root,
                dataset_id=job.dataset_id,
                storage_policy=dataset.storage_policy,
                partition_key=partition_key,
                artifact_path=artifact.path,
                row_count=artifact.row_count,
                run=run,
            )
            shutil.rmtree(run_directory, ignore_errors=True)
            session.commit()
        except Exception as error:
            message = (
                _upstream_failure_message(error) if _is_upstream_failure(error) else str(error)
            )
            run.status = "failed"
            run.error = message
            job.status = CollectionJobStatus.FAILED.value
            job.error = message
            session.commit()
            log_event(
                "collection_run_failed",
                level=logging.ERROR,
                exc_info=True,
                job_id=job.id,
                run_id=run.id,
                dataset_id=job.dataset_id,
                partition_key=partition_key,
                error=message,
            )
            if _is_upstream_failure(error):
                raise HTTPException(status_code=502, detail=message) from error
            raise

    report_path = data_root / "staging" / job.id / "review.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    aggregate = {
        "reviewer": job.dataset_id,
        "passed": bool(reports) and all(item["passed"] for item in reports),
        "row_count": sum(item["row_count"] for item in reports),
        "error_count": sum(item["error_count"] for item in reports),
        "runs": reports,
    }
    report_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    if job.status not in {
        CollectionJobStatus.REVIEW_FAILED.value,
        CollectionJobStatus.FAILED.value,
    }:
        job.status = CollectionJobStatus.SUCCEEDED.value
    job.staged_path = report_path.relative_to(data_root).as_posix()
    session.commit()
    session.refresh(job)
    log_event(
        "collection_job_completed",
        job_id=job.id,
        dataset_id=job.dataset_id,
        status=job.status,
        row_count=aggregate["row_count"],
        error_count=aggregate["error_count"],
    )
    return serialize_job(job)


def _execute_snapshot_job(
    job: CollectionJob,
    operation,
    dataset: Dataset,
    schema: DatasetSchemaVersion,
    data_root: Path,
    session: Session,
) -> CollectionJobRead:
    if not dataset.storage_policy:
        raise HTTPException(status_code=409, detail="dataset has no storage policy")
    run = session.scalar(
        select(CollectionRun).where(
            CollectionRun.job_id == job.id,
            CollectionRun.partition_key == "snapshot",
        )
    )
    if run is None:
        run = CollectionRun(
            id=str(uuid4()),
            job_id=job.id,
            partition_key="snapshot",
            status="fetching",
        )
        session.add(run)
        session.flush()
    run.status = "fetching"
    run.error = None
    session.commit()
    fields = [
        {
            "name": field.name,
            "source_name": field.source_name,
            "data_type": field.data_type,
            "nullable": field.nullable,
        }
        for field in schema.fields
    ]
    run_directory = data_root / "staging" / job.id / run.id
    report_path = data_root / "staging" / job.id / "review.json"
    try:
        log_event(
            "collection_run_started",
            job_id=job.id,
            run_id=run.id,
            dataset_id=job.dataset_id,
            collector=job.collector_key,
            operation=job.collector_operation,
            partition_key="snapshot",
        )
        result = run_operation(
            job.collector_key or "unknown",
            operation,
            lambda: operation.function(
                CollectionContext(run.id, run_directory, load_token()),
                job.parameters,
                fields,
            ),
            job_id=job.id,
        )
        cancelled = _cancel_snapshot_at_boundary(
            session,
            job,
            run,
            run_directory,
        )
        if cancelled is not None:
            return cancelled
        if set(result.outputs) != set(operation.datasets):
            raise CollectionError("collector outputs do not match operation declaration")
        artifacts = result.outputs[job.dataset_id]
        if len(artifacts) != 1:
            raise CollectionError("snapshot collection must produce exactly one artifact")
        artifact = artifacts[0]
        log_event(
            "collection_artifact_staged",
            job_id=job.id,
            run_id=run.id,
            dataset_id=job.dataset_id,
            partition_key="snapshot",
            row_count=artifact.row_count,
        )
        report = review_dataset(
            job.dataset_id,
            ReviewContext(artifact.path, schema),
        ).as_dict()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        run.staged_path = artifact.path.relative_to(data_root).as_posix()
        run.row_count = artifact.row_count
        log_event(
            "review_completed",
            job_id=job.id,
            run_id=run.id,
            dataset_id=job.dataset_id,
            partition_key="snapshot",
            passed=report["passed"],
            error_count=report["error_count"],
        )
        if not report["passed"]:
            cancelled = _finalize_snapshot_review_failure(
                session,
                job,
                run,
                run_directory,
                report_path,
                data_root,
            )
            if cancelled is not None:
                return cancelled
        else:
            cancelled = _begin_snapshot_publish(
                session,
                job,
                run,
                run_directory,
                report_path,
            )
            if cancelled is not None:
                return cancelled
            publish_partition(
                session,
                data_root=data_root,
                dataset_id=job.dataset_id,
                storage_policy=dataset.storage_policy,
                partition_key="snapshot",
                artifact_path=artifact.path,
                row_count=artifact.row_count,
                run=run,
            )
            job.status = CollectionJobStatus.SUCCEEDED.value
            shutil.rmtree(run_directory, ignore_errors=True)
        job.staged_path = report_path.relative_to(data_root).as_posix()
        session.commit()
        session.refresh(job)
        log_event(
            "collection_job_completed",
            job_id=job.id,
            dataset_id=job.dataset_id,
            status=job.status,
            row_count=report["row_count"],
            error_count=report["error_count"],
        )
        return serialize_job(job)
    except (CollectionError, URLError, RateLimitExceeded) as error:
        message = _upstream_failure_message(error)
        run.status = "failed"
        run.error = message
        job.status = CollectionJobStatus.FAILED.value
        job.error = message
        session.commit()
        log_event(
            "collection_run_failed",
            level=logging.ERROR,
            exc_info=True,
            job_id=job.id,
            run_id=run.id,
            dataset_id=job.dataset_id,
            partition_key="snapshot",
            error=message,
        )
        raise HTTPException(status_code=502, detail=message) from error
    except Exception as error:
        run.status = "failed"
        run.error = str(error)
        job.status = CollectionJobStatus.FAILED.value
        job.error = str(error)
        session.commit()
        log_event(
            "collection_run_failed",
            level=logging.ERROR,
            exc_info=True,
            job_id=job.id,
            run_id=run.id,
            dataset_id=job.dataset_id,
            partition_key="snapshot",
            error=str(error),
        )
        raise


@router.post("", response_model=CollectionJobRead, status_code=status.HTTP_201_CREATED)
def create_collection_job(
    payload: CollectionJobCreate,
    request: Request,
    session: SessionDep,
) -> CollectionJobRead:
    dataset = session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != DatasetStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="only active datasets can be collected")
    if dataset.storage_policy and dataset.storage_policy.get("logical_partition_field"):
        calendar_id = dataset.storage_policy.get("calendar_dataset_id")
        calendar = session.get(Dataset, calendar_id) if calendar_id else None
        if calendar is None:
            raise HTTPException(
                status_code=409,
                detail=f"请先创建交易日历数据集：{calendar_id or '尚未配置 calendar_dataset_id'}",
            )
        if calendar.status != DatasetStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail=f"请先启用交易日历数据集：{calendar_id}",
            )
        calendar_catalog = session.scalar(
            select(CatalogPartition)
            .where(CatalogPartition.dataset_id == calendar_id)
            .order_by(CatalogPartition.published_at.desc())
            .limit(1)
        )
        if calendar_catalog is None:
            raise HTTPException(
                status_code=409,
                detail=f"交易日历尚无已发布数据，请先采集交易日历：{calendar_id}",
            )
        if not (request.app.state.data_root / calendar_catalog.file_path).is_file():
            raise HTTPException(
                status_code=409,
                detail=f"交易日历文件缺失，请重新发布交易日历：{calendar_id}",
            )

    binding = next(
        (
            item
            for item in dataset.collection_bindings
            if item["purpose"] == payload.operation.value
        ),
        None,
    )
    if payload.input_method is InputMethod.COLLECTOR and binding is None:
        raise HTTPException(
            status_code=409,
            detail="dataset does not support this collection purpose",
        )

    parameters = dict(binding.get("parameters", {})) if binding else {}
    parameters.update(payload.parameters)
    if payload.start_date:
        parameters["start_date"] = payload.start_date.isoformat()
        parameters["end_date"] = payload.end_date.isoformat()
    if binding:
        operation_definition = get_operation(binding["collector_key"], binding["operation"])
        assert operation_definition is not None
        try:
            validate_operation_parameters(
                operation_definition,
                parameters,
                require_all=True,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    start_date = payload.start_date
    end_date = payload.end_date
    if start_date is None and parameters.get("start_date"):
        start_date = date.fromisoformat(str(parameters["start_date"]))
    if end_date is None and start_date is not None and parameters.get("end_date"):
        end_date = date.fromisoformat(str(parameters["end_date"]))

    job = CollectionJob(
        id=str(uuid4()),
        dataset_id=payload.dataset_id,
        operation=payload.operation.value,
        input_method=payload.input_method.value,
        status=(
            CollectionJobStatus.AWAITING_FILE.value
            if payload.input_method is InputMethod.FILE_IMPORT
            else CollectionJobStatus.CREATED.value
        ),
        start_date=start_date,
        end_date=end_date,
        collector_key=(binding["collector_key"] if binding else None),
        collector_operation=(
            binding["operation"] if binding else None
        ),
        parameters=parameters,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        "collection_job_created",
        job_id=job.id,
        dataset_id=job.dataset_id,
        operation=job.operation,
        input_method=job.input_method,
        collector=job.collector_key,
        collector_operation=job.collector_operation,
    )
    return serialize_job(job)


@router.post(
    "/{job_id}/retry",
    response_model=CollectionJobRead,
    status_code=status.HTTP_201_CREATED,
)
def retry_collection_job(
    job_id: str,
    session: SessionDep,
) -> CollectionJobRead:
    source = session.get(CollectionJob, job_id)
    if source is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if source.input_method != InputMethod.COLLECTOR.value:
        raise HTTPException(status_code=409, detail="只有采集器任务可以重试")
    if source.status not in RETRYABLE_JOB_STATUSES:
        raise HTTPException(status_code=409, detail="只有失败、审核异常或已取消的任务可以重试")
    dataset = session.get(Dataset, source.dataset_id)
    if dataset is None or dataset.status != DatasetStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="只有已启用数据集的任务可以重试")
    operation = (
        get_operation(source.collector_key, source.collector_operation)
        if source.collector_key and source.collector_operation
        else None
    )
    if operation is None or source.dataset_id not in operation.datasets:
        raise HTTPException(status_code=409, detail="原任务绑定的采集器操作已不可用")

    retried_job = CollectionJob(
        id=str(uuid4()),
        dataset_id=source.dataset_id,
        operation=source.operation,
        input_method=InputMethod.COLLECTOR.value,
        status=CollectionJobStatus.CREATED.value,
        start_date=source.start_date,
        end_date=source.end_date,
        collector_key=source.collector_key,
        collector_operation=source.collector_operation,
        parameters=dict(source.parameters or {}),
        retry_of_job_id=source.id,
    )
    session.add(retried_job)
    session.commit()
    session.refresh(retried_job)
    log_event(
        "collection_job_retried",
        job_id=retried_job.id,
        retry_of_job_id=source.id,
        dataset_id=retried_job.dataset_id,
        operation=retried_job.operation,
    )
    return serialize_job(retried_job)


def _execute_collection_job_background(job_id: str, session_factory, data_root: Path) -> None:
    with session_factory() as session:
        with _JOB_STATE_LOCK:
            job = session.get(CollectionJob, job_id)
            if job is None:
                _QUEUED_JOBS.discard(job_id)
                return
            if job.status in {
                CollectionJobStatus.CANCELLING.value,
                CollectionJobStatus.CANCELLED.value,
            }:
                job.status = CollectionJobStatus.CANCELLED.value
                session.commit()
                _QUEUED_JOBS.discard(job_id)
                _CANCEL_REQUESTS.discard(job_id)
                log_event(
                    "collection_job_cancelled",
                    job_id=job.id,
                    dataset_id=job.dataset_id,
                )
                return
            if job.status != CollectionJobStatus.QUEUED.value:
                _QUEUED_JOBS.discard(job_id)
                return
            _QUEUED_JOBS.discard(job_id)
            _RUNNING_JOBS.add(job_id)
            job.status = CollectionJobStatus.RUNNING.value
            job.error = None
            session.commit()

        try:
            operation = get_operation(job.collector_key or "", job.collector_operation or "")
            if operation is None or job.dataset_id not in operation.datasets:
                raise RuntimeError("dataset has no executable collector")
            dataset = session.scalar(
                select(Dataset)
                .options(
                    selectinload(Dataset.schemas).selectinload(DatasetSchemaVersion.fields)
                )
                .where(Dataset.id == job.dataset_id)
            )
            if dataset is None:
                raise RuntimeError("dataset not found")
            schema = next(
                item
                for item in dataset.schemas
                if item.version == dataset.current_schema_version
            )
            log_event(
                "collection_job_started",
                job_id=job.id,
                dataset_id=job.dataset_id,
                operation=job.operation,
                collector=job.collector_key,
                collector_operation=job.collector_operation,
            )
            _run_collection(job, operation, dataset, schema, data_root, session)
        except Exception as error:
            _mark_job_failed(session, job_id, error)
        finally:
            with _JOB_STATE_LOCK:
                _RUNNING_JOBS.discard(job_id)
                _QUEUED_JOBS.discard(job_id)
                _CANCEL_REQUESTS.discard(job_id)
                _PUBLISHING_JOBS.discard(job_id)


@router.post(
    "/{job_id}/execute",
    response_model=CollectionJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def execute_collection_job(job_id: str, request: Request, session: SessionDep) -> CollectionJobRead:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if job.input_method != InputMethod.COLLECTOR.value:
        raise HTTPException(status_code=409, detail="job is not a collector job")
    if job.status != CollectionJobStatus.CREATED.value:
        raise HTTPException(status_code=409, detail="job has already been executed")

    if not job.collector_key or not job.collector_operation:
        raise HTTPException(status_code=409, detail="dataset has no collector binding")
    operation = get_operation(job.collector_key, job.collector_operation)
    if operation is None or job.dataset_id not in operation.datasets:
        raise HTTPException(status_code=409, detail="dataset has no executable collector")
    if len(operation.datasets) > 1:
        raise HTTPException(status_code=501, detail="joint collection execution is not implemented")

    data_root: Path = request.app.state.data_root
    with _JOB_STATE_LOCK:
        session.refresh(job)
        if job.status != CollectionJobStatus.CREATED.value:
            raise HTTPException(status_code=409, detail="job has already been executed")
        _QUEUED_JOBS.add(job.id)
        job.status = CollectionJobStatus.QUEUED.value
        job.error = None
        session.commit()
        try:
            request.app.state.background_executor.submit(
                job.id,
                partial(
                    _execute_collection_job_background,
                    job.id,
                    request.app.state.session_factory,
                    data_root,
                ),
            )
        except RuntimeError as error:
            _QUEUED_JOBS.discard(job.id)
            job.status = CollectionJobStatus.CREATED.value
            session.commit()
            raise HTTPException(status_code=503, detail="后台任务执行器不可用") from error
        log_event(
            "collection_job_queued",
            job_id=job.id,
            dataset_id=job.dataset_id,
            operation=job.operation,
            collector=job.collector_key,
            collector_operation=job.collector_operation,
        )
    return serialize_job(job)


def _run_collection(
    job: CollectionJob,
    operation,
    dataset: Dataset,
    schema: DatasetSchemaVersion,
    data_root: Path,
    session: Session,
) -> CollectionJobRead:
    if job.dataset_id == DAILY_DATASET_ID:
        return _execute_daily_job(
            job,
            operation,
            dataset,
            schema,
            data_root,
            session,
        )
    if dataset.storage_policy and dataset.storage_policy.get("layout") == "snapshot":
        return _execute_snapshot_job(
            job,
            operation,
            dataset,
            schema,
            data_root,
            session,
        )
    fields = [field.source_name or field.name for field in schema.fields]
    job_directory = data_root / "staging" / job.id
    target = job_directory / "stock_basic.parquet"
    report_path = job_directory / "review.json"

    try:
        row_count = run_operation(
            job.collector_key or "unknown",
            operation,
            lambda: operation.function(target, fields, load_token()),
            job_id=job.id,
        )
        job.source_file_name = target.name
        job.staged_path = target.relative_to(data_root).as_posix()
        job.source_size_bytes = target.stat().st_size
        job.source_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        job.status = CollectionJobStatus.STAGED.value
        report = review_dataset(
            job.dataset_id,
            ReviewContext(target, schema),
        ).as_dict()
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        passed = report["passed"]
        job.status = (
            CollectionJobStatus.REVIEW_PASSED.value
            if passed
            else CollectionJobStatus.REVIEW_FAILED.value
        )
        if row_count == 0:
            job.status = CollectionJobStatus.REVIEW_FAILED.value
        session.commit()
        session.refresh(job)
        log_event(
            "review_completed",
            job_id=job.id,
            dataset_id=job.dataset_id,
            passed=passed,
            error_count=report["error_count"],
            row_count=report["row_count"],
        )
    except (CollectionError, OSError) as error:
        message = _upstream_failure_message(error)
        session.rollback()
        log_event(
            "collection_job_failed",
            level=logging.ERROR,
            exc_info=True,
            job_id=job.id,
            dataset_id=job.dataset_id,
            error=message,
        )
        raise HTTPException(status_code=502, detail=message) from error

    return serialize_job(job)


@router.post("/{job_id}/cancel", response_model=CollectionJobRead)
def cancel_collection_job(job_id: str, request: Request, session: SessionDep) -> CollectionJobRead:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    with _JOB_STATE_LOCK:
        session.refresh(job)
        if job.status in TERMINAL_JOB_STATUSES:
            raise HTTPException(status_code=409, detail="任务已结束，无法取消")
        if job.id in _PUBLISHING_JOBS:
            raise HTTPException(status_code=409, detail="任务正在发布，已无法安全取消")

        if job.id in _QUEUED_JOBS:
            if request.app.state.background_executor.cancel(job.id):
                _QUEUED_JOBS.discard(job.id)
                job.status = CollectionJobStatus.CANCELLED.value
                log_event(
                    "collection_job_cancelled",
                    job_id=job.id,
                    dataset_id=job.dataset_id,
                )
            else:
                job.status = CollectionJobStatus.CANCELLING.value
                _CANCEL_REQUESTS.add(job.id)
                log_event(
                    "collection_job_cancel_requested",
                    job_id=job.id,
                    dataset_id=job.dataset_id,
                )
        elif job.id in _RUNNING_JOBS:
            # 先落库再登记取消请求，避免与执行线程写回 CANCELLED 的顺序竞争。
            job.status = CollectionJobStatus.CANCELLING.value
            session.commit()
            _CANCEL_REQUESTS.add(job.id)
            log_event(
                "collection_job_cancel_requested",
                job_id=job.id,
                dataset_id=job.dataset_id,
            )
        else:
            job.status = CollectionJobStatus.CANCELLED.value
            log_event(
                "collection_job_cancelled",
                job_id=job.id,
                dataset_id=job.dataset_id,
            )
        session.commit()
    session.refresh(job)
    return serialize_job(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection_job(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> Response:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if job.id in _RUNNING_JOBS or job.id in _QUEUED_JOBS or job.status in {
        CollectionJobStatus.QUEUED.value,
        CollectionJobStatus.RUNNING.value,
        CollectionJobStatus.CANCELLING.value,
    }:
        raise HTTPException(status_code=409, detail="请先取消正在执行的任务")

    dataset_id = job.dataset_id
    session.execute(delete(CollectionRun).where(CollectionRun.job_id == job_id))
    session.delete(job)
    session.commit()
    shutil.rmtree(request.app.state.data_root / "staging" / job_id, ignore_errors=True)
    log_event(
        "collection_job_deleted",
        job_id=job_id,
        dataset_id=dataset_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/progress")
def collection_job_progress(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> dict:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")

    counts = dict(
        session.execute(
            select(CollectionRun.status, func.count(CollectionRun.id))
            .where(CollectionRun.job_id == job_id)
            .group_by(CollectionRun.status)
        ).all()
    )
    latest_partition = session.scalar(
        select(func.max(CollectionRun.partition_key)).where(
            CollectionRun.job_id == job_id,
            CollectionRun.status == "succeeded",
        )
    )
    expected_total: int | None = None
    dataset = session.get(Dataset, job.dataset_id)
    if (
        dataset is not None
        and dataset.storage_policy
        and dataset.storage_policy.get("logical_partition_field")
        and job.start_date is not None
        and job.end_date is not None
    ):
        try:
            expected_total = len(
                _trading_dates(
                    dataset,
                    job.start_date,
                    job.end_date,
                    request.app.state.data_root,
                    session,
                )
            )
        except HTTPException:
            expected_total = None

    succeeded = counts.get("succeeded", 0)
    failed = counts.get("failed", 0)
    return {
        "job_id": job.id,
        "status": job.status,
        "expected_total": expected_total,
        "succeeded": succeeded,
        "failed": failed,
        "processed": succeeded + failed,
        "latest_partition": latest_partition,
        "percent": (
            round(succeeded * 100 / expected_total, 1) if expected_total else None
        ),
    }


@router.get("", response_model=list[CollectionJobRead])
def list_collection_jobs(
    session: SessionDep,
    dataset_id: str | None = None,
) -> list[CollectionJobRead]:
    query = select(CollectionJob).order_by(CollectionJob.created_at.desc())
    if dataset_id:
        query = query.where(CollectionJob.dataset_id == dataset_id)
    return [serialize_job(job) for job in session.scalars(query)]


@router.get("/{job_id}", response_model=CollectionJobRead)
def get_collection_job(job_id: str, session: SessionDep) -> CollectionJobRead:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    return serialize_job(job)


@router.get("/{job_id}/review")
def get_collection_review(job_id: str, request: Request, session: SessionDep) -> dict:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if not job.staged_path:
        raise HTTPException(status_code=409, detail="job has no staged review result")
    report_path = (request.app.state.data_root / job.staged_path).parent / "review.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="review report not found")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # 早期报告曾保存采集器接口名；审核器没有独立 ID，对外始终使用目标数据集 ID。
    report["reviewer"] = job.dataset_id
    return report


@router.post("/{job_id}/file", response_model=CollectionJobRead)
async def stage_import_file(
    job_id: str,
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> CollectionJobRead:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if job.input_method != InputMethod.FILE_IMPORT.value:
        raise HTTPException(status_code=409, detail="job does not accept a file")
    if job.status != CollectionJobStatus.AWAITING_FILE.value:
        raise HTTPException(status_code=409, detail="job file has already been staged")

    file_name = Path(file.filename or "").name
    if not file_name or file_name in {".", ".."}:
        raise HTTPException(status_code=422, detail="file name is required")
    if len(file_name) > 255:
        raise HTTPException(status_code=422, detail="file name is too long")

    data_root: Path = request.app.state.data_root
    job_directory = data_root / "staging" / job.id
    job_directory.mkdir(parents=True, exist_ok=True)
    target = job_directory / file_name
    digest = hashlib.sha256()
    size = 0

    try:
        with target.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="empty files cannot be staged")

        job.source_file_name = file_name
        job.staged_path = target.relative_to(data_root).as_posix()
        job.source_size_bytes = size
        job.source_sha256 = digest.hexdigest()
        job.status = CollectionJobStatus.STAGED.value
        session.commit()
        session.refresh(job)
        log_event(
            "file_staged",
            job_id=job.id,
            dataset_id=job.dataset_id,
            file_name=file_name,
            size_bytes=size,
            sha256=digest.hexdigest(),
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail="staging file already exists") from error
    except HTTPException:
        raise
    except Exception:
        target.unlink(missing_ok=True)
        session.rollback()
        raise
    finally:
        await file.close()

    return serialize_job(job)
