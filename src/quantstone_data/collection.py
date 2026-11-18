import hashlib
import json
import os
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .collection_protocol import CollectionContext
from .collection_schemas import (
    CollectionJobCreate,
    CollectionJobRead,
    CollectionJobStatus,
    InputMethod,
)
from .collector_registry import get_operation
from .database import get_session
from .datasets.tushare.cn.stock.daily.definition import DATASET_ID as DAILY_DATASET_ID
from .datasets.tushare.cn.stock.daily.reviewer import review_daily
from .datasets.tushare.cn.stock.stock_basic import (
    CollectionError,
    load_token,
    review,
)
from .models import CatalogPartition, CollectionJob, CollectionRun, Dataset, DatasetSchemaVersion
from .schemas import DatasetStatus

router = APIRouter(prefix="/collection-jobs", tags=["collection jobs"])
SessionDep = Annotated[Session, Depends(get_session)]


def serialize_job(job: CollectionJob) -> CollectionJobRead:
    return CollectionJobRead.model_validate(job, from_attributes=True)


def _date_batches(start_date, end_date):
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _execute_daily_job(
    job: CollectionJob,
    operation,
    dataset: Dataset,
    schema: DatasetSchemaVersion,
    data_root: Path,
    session: Session,
) -> CollectionJobRead:
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
    for trade_date in _date_batches(job.start_date, job.end_date):
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
            result = operation.function(
                context,
                {"trade_date": partition_key},
                fields,
            )
            if set(result.outputs) != set(operation.datasets):
                raise CollectionError("collector outputs do not match operation declaration")
            artifact = result.outputs[job.dataset_id][0]
            report = review_daily(artifact.path, schema, trade_date)
            report["partition_key"] = partition_key
            reports.append(report)
            run.staged_path = artifact.path.relative_to(data_root).as_posix()
            run.row_count = artifact.row_count
            if not report["passed"]:
                run.status = "review_failed"
                job.status = CollectionJobStatus.REVIEW_FAILED.value
                session.commit()
                break

            target = (
                data_root
                / "datasets"
                / job.dataset_id
                / "delta"
                / str(trade_date.year)
                / partition_key
                / f"{run.id}.parquet"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(artifact.path, target)
            relative_target = target.relative_to(data_root).as_posix()
            checksum = _sha256(target)
            existing = session.scalar(
                select(CatalogPartition).where(
                    CatalogPartition.dataset_id == job.dataset_id,
                    CatalogPartition.partition_key == partition_key,
                )
            )
            if existing and existing.file_path != relative_target:
                old_path = data_root / existing.file_path
                old_path.unlink(missing_ok=True)
            catalog = existing or CatalogPartition(
                dataset_id=job.dataset_id,
                partition_key=partition_key,
            )
            catalog.file_path = relative_target
            catalog.row_count = artifact.row_count
            catalog.size_bytes = target.stat().st_size
            catalog.sha256 = checksum
            catalog.collection_run_id = run.id
            if existing is None:
                session.add(catalog)
            run.published_path = relative_target
            run.staged_path = None
            run.status = "succeeded"
            shutil.rmtree(run_directory, ignore_errors=True)
            session.commit()
        except Exception as error:
            run.status = "failed"
            run.error = str(error)
            job.status = CollectionJobStatus.FAILED.value
            session.commit()
            raise

    report_path = data_root / "staging" / job.id / "review.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    aggregate = {
        "reviewer": "tushare.daily",
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
    return serialize_job(job)


@router.post("", response_model=CollectionJobRead, status_code=status.HTTP_201_CREATED)
def create_collection_job(payload: CollectionJobCreate, session: SessionDep) -> CollectionJobRead:
    dataset = session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != DatasetStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="only active datasets can be collected")

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
        start_date=payload.start_date,
        end_date=payload.end_date,
        collector_key=(binding["collector_key"] if binding else None),
        collector_operation=(
            binding["operation"] if binding else None
        ),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return serialize_job(job)


@router.post("/{job_id}/execute", response_model=CollectionJobRead)
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

    dataset = session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.schemas).selectinload(DatasetSchemaVersion.fields))
        .where(Dataset.id == job.dataset_id)
    )
    assert dataset is not None
    schema = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    if job.dataset_id == DAILY_DATASET_ID:
        return _execute_daily_job(
            job,
            operation,
            dataset,
            schema,
            request.app.state.data_root,
            session,
        )
    fields = [field.source_name or field.name for field in schema.fields]
    job_directory = request.app.state.data_root / "staging" / job.id
    target = job_directory / "stock_basic.parquet"
    report_path = job_directory / "review.json"

    try:
        row_count = operation.function(target, fields, load_token())
        job.source_file_name = target.name
        job.staged_path = target.relative_to(request.app.state.data_root).as_posix()
        job.source_size_bytes = target.stat().st_size
        job.source_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        job.status = CollectionJobStatus.STAGED.value
        passed = review(target, schema, report_path)
        job.status = (
            CollectionJobStatus.REVIEW_PASSED.value
            if passed
            else CollectionJobStatus.REVIEW_FAILED.value
        )
        if row_count == 0:
            job.status = CollectionJobStatus.REVIEW_FAILED.value
        session.commit()
        session.refresh(job)
    except (CollectionError, OSError) as error:
        session.rollback()
        raise HTTPException(status_code=502, detail=str(error)) from error

    return serialize_job(job)


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
    return json.loads(report_path.read_text(encoding="utf-8"))


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
