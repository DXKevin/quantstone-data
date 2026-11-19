from __future__ import annotations

import logging
import threading
from functools import partial
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .logging_config import log_event
from .maintenance_schemas import MaintenanceJobRead, MaintenanceJobStatus
from .models import CatalogPartition, Dataset, MaintenanceJob
from .storage import compact_year

router = APIRouter(tags=["maintenance"])
SessionDep = Annotated[Session, Depends(get_session)]
_MAINTENANCE_LOCK = threading.Lock()
TERMINAL_STATUSES = {
    MaintenanceJobStatus.SUCCEEDED.value,
    MaintenanceJobStatus.FAILED.value,
    MaintenanceJobStatus.CANCELLED.value,
}


def serialize_job(job: MaintenanceJob) -> MaintenanceJobRead:
    return MaintenanceJobRead.model_validate(job, from_attributes=True)


def recover_interrupted_maintenance_jobs(session: Session) -> int:
    jobs = list(
        session.scalars(
            select(MaintenanceJob).where(
                MaintenanceJob.status.in_(
                    (
                        MaintenanceJobStatus.QUEUED.value,
                        MaintenanceJobStatus.RUNNING.value,
                    )
                )
            )
        )
    )
    for job in jobs:
        job.status = MaintenanceJobStatus.FAILED.value
        job.error = "应用重启时维护任务尚未完成，已标记为失败；请重新提交。"
    if jobs:
        session.commit()
    return len(jobs)


def _run_compaction(job_id: str, session_factory, data_root: Path) -> None:
    with session_factory() as session:
        with _MAINTENANCE_LOCK:
            job = session.get(MaintenanceJob, job_id)
            if job is None or job.status == MaintenanceJobStatus.CANCELLED.value:
                return
            if job.status != MaintenanceJobStatus.QUEUED.value:
                return
            job.status = MaintenanceJobStatus.RUNNING.value
            session.commit()
        log_event(
            "maintenance_job_started",
            maintenance_job_id=job.id,
            dataset_id=job.dataset_id,
            operation=job.operation,
            parameters=job.parameters,
        )
        try:
            result = compact_year(
                session,
                data_root,
                job.dataset_id,
                int(job.parameters["year"]),
            )
            if result["status"] == "missing_files":
                raise RuntimeError(
                    "Catalog 指向的源文件缺失：" + "；".join(result["missing_files"])
                )
            job.status = MaintenanceJobStatus.SUCCEEDED.value
            job.result = result
            job.error = None
            session.commit()
            log_event(
                "maintenance_job_completed",
                maintenance_job_id=job.id,
                dataset_id=job.dataset_id,
                operation=job.operation,
                result=result,
            )
        except Exception as error:
            session.rollback()
            job = session.get(MaintenanceJob, job_id)
            if job is not None:
                job.status = MaintenanceJobStatus.FAILED.value
                job.error = str(error) or error.__class__.__name__
                session.commit()
            log_event(
                "maintenance_job_failed",
                level=logging.ERROR,
                exc_info=True,
                maintenance_job_id=job_id,
                dataset_id=job.dataset_id if job else None,
                operation="compact_year",
                error=str(error),
            )


@router.post(
    "/datasets/{dataset_id}/compact",
    response_model=MaintenanceJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_compaction_job(
    dataset_id: str,
    request: Request,
    session: SessionDep,
    year: int = Query(ge=1990, le=2100),
) -> MaintenanceJobRead:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != "active":
        raise HTTPException(status_code=409, detail="数据集启用后才能执行年度合并")
    policy = dataset.storage_policy or {}
    if policy.get("layout") != "yearly_with_delta" or policy.get("compaction") != "yearly":
        raise HTTPException(status_code=409, detail="该数据集未配置年度合并策略")

    active = list(
        session.scalars(
            select(MaintenanceJob).where(
                MaintenanceJob.dataset_id == dataset_id,
                MaintenanceJob.operation == "compact_year",
                MaintenanceJob.status.in_(
                    (
                        MaintenanceJobStatus.QUEUED.value,
                        MaintenanceJobStatus.RUNNING.value,
                    )
                ),
            )
        )
    )
    if any(int(item.parameters.get("year", 0)) == year for item in active):
        raise HTTPException(status_code=409, detail=f"{year} 年合并任务已在排队或执行")

    job = MaintenanceJob(
        id=str(uuid4()),
        dataset_id=dataset_id,
        operation="compact_year",
        parameters={"year": year},
        status=MaintenanceJobStatus.QUEUED.value,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    with _MAINTENANCE_LOCK:
        try:
            request.app.state.background_executor.submit(
                job.id,
                partial(
                    _run_compaction,
                    job.id,
                    request.app.state.session_factory,
                    request.app.state.data_root,
                ),
            )
        except RuntimeError as error:
            job.status = MaintenanceJobStatus.FAILED.value
            job.error = "后台任务执行器不可用"
            session.commit()
            raise HTTPException(status_code=503, detail=job.error) from error
        log_event(
            "maintenance_job_queued",
            maintenance_job_id=job.id,
            dataset_id=dataset_id,
            operation=job.operation,
            parameters=job.parameters,
        )
    return serialize_job(job)


@router.post(
    "/datasets/{dataset_id}/compact-all",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_auto_compaction_jobs(
    dataset_id: str,
    request: Request,
    session: SessionDep,
) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != "active":
        raise HTTPException(status_code=409, detail="数据集启用后才能执行年度合并")
    policy = dataset.storage_policy or {}
    if policy.get("layout") != "yearly_with_delta" or policy.get("compaction") != "yearly":
        raise HTTPException(status_code=409, detail="该数据集未配置年度合并策略")

    partition_rows = session.execute(
        select(CatalogPartition.partition_key, CatalogPartition.file_path).where(
            CatalogPartition.dataset_id == dataset_id
        )
    ).all()
    annual_only: dict[str, bool] = {}
    for partition_key, file_path in partition_rows:
        year = partition_key[:4]
        if not year.isdigit() or not 1990 <= int(year) <= 2100:
            continue
        target_rel = f"datasets/{dataset_id}/annual/{year}.parquet"
        annual_only[year] = annual_only.get(year, True) and file_path == target_rel

    candidate_years = sorted(int(year) for year, only in annual_only.items() if not only)
    active_years = {
        int(item.parameters.get("year", 0))
        for item in session.scalars(
            select(MaintenanceJob).where(
                MaintenanceJob.dataset_id == dataset_id,
                MaintenanceJob.operation == "compact_year",
                MaintenanceJob.status.in_(
                    (
                        MaintenanceJobStatus.QUEUED.value,
                        MaintenanceJobStatus.RUNNING.value,
                    )
                ),
            )
        )
    }
    pending_years = [year for year in candidate_years if year not in active_years]
    if not pending_years:
        detail = (
            "没有需要合并的年份"
            if not candidate_years
            else "所有待合并年份都已有排队或执行中的任务"
        )
        raise HTTPException(status_code=409, detail=detail)

    created: list[MaintenanceJob] = []
    for year in pending_years:
        job = MaintenanceJob(
            id=str(uuid4()),
            dataset_id=dataset_id,
            operation="compact_year",
            parameters={"year": year},
            status=MaintenanceJobStatus.QUEUED.value,
        )
        session.add(job)
        created.append(job)
    session.commit()

    with _MAINTENANCE_LOCK:
        for job in created:
            try:
                request.app.state.background_executor.submit(
                    job.id,
                    partial(
                        _run_compaction,
                        job.id,
                        request.app.state.session_factory,
                        request.app.state.data_root,
                    ),
                )
                log_event(
                    "maintenance_job_queued",
                    maintenance_job_id=job.id,
                    dataset_id=dataset_id,
                    operation=job.operation,
                    parameters=job.parameters,
                )
            except RuntimeError:
                job.status = MaintenanceJobStatus.FAILED.value
                job.error = "后台任务执行器不可用"
        session.commit()

    return {
        "jobs": [serialize_job(job) for job in created],
        "skipped_years": sorted(active_years.intersection(candidate_years)),
        "candidate_years": candidate_years,
    }


@router.get("/maintenance-jobs", response_model=list[MaintenanceJobRead])
def list_maintenance_jobs(
    session: SessionDep,
    dataset_id: str | None = None,
) -> list[MaintenanceJobRead]:
    query = select(MaintenanceJob).order_by(MaintenanceJob.created_at.desc())
    if dataset_id:
        query = query.where(MaintenanceJob.dataset_id == dataset_id)
    return [serialize_job(job) for job in session.scalars(query)]


@router.get("/maintenance-jobs/{job_id}", response_model=MaintenanceJobRead)
def get_maintenance_job(job_id: str, session: SessionDep) -> MaintenanceJobRead:
    job = session.get(MaintenanceJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="maintenance job not found")
    return serialize_job(job)


@router.post("/maintenance-jobs/{job_id}/cancel", response_model=MaintenanceJobRead)
def cancel_maintenance_job(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> MaintenanceJobRead:
    with _MAINTENANCE_LOCK:
        job = session.get(MaintenanceJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="maintenance job not found")
        if job.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail="维护任务已结束，无法取消")
        if job.status == MaintenanceJobStatus.RUNNING.value:
            raise HTTPException(status_code=409, detail="年度合并已开始，无法安全取消")
        request.app.state.background_executor.cancel(job.id)
        job.status = MaintenanceJobStatus.CANCELLED.value
        session.commit()
        session.refresh(job)
        log_event(
            "maintenance_job_cancelled",
            maintenance_job_id=job.id,
            dataset_id=job.dataset_id,
            operation=job.operation,
        )
    return serialize_job(job)
