import hashlib
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .collection_schemas import (
    CollectionJobCreate,
    CollectionJobRead,
    CollectionJobStatus,
    InputMethod,
)
from .database import get_session
from .dataset_handlers import handler_for
from .models import CollectionJob, Dataset, DatasetSchemaVersion
from .schemas import DatasetStatus
from .tushare_stock_basic import (
    CollectionError,
    collect_stock_basic,
    load_tushare_token,
    review_stock_basic,
)

router = APIRouter(prefix="/collection-jobs", tags=["collection jobs"])
SessionDep = Annotated[Session, Depends(get_session)]


def serialize_job(job: CollectionJob) -> CollectionJobRead:
    return CollectionJobRead.model_validate(job, from_attributes=True)


@router.post("", response_model=CollectionJobRead, status_code=status.HTTP_201_CREATED)
def create_collection_job(payload: CollectionJobCreate, session: SessionDep) -> CollectionJobRead:
    dataset = session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != DatasetStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="only active datasets can be collected")

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
        collector_key=(
            handler_for(payload.dataset_id).collector_key
            if payload.input_method is InputMethod.COLLECTOR
            and handler_for(payload.dataset_id)
            else payload.collector_key
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

    handler = handler_for(job.dataset_id)
    if handler is None or handler.collector_key != "tushare.stock_basic":
        raise HTTPException(status_code=409, detail="dataset has no executable collector")

    dataset = session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.schemas).selectinload(DatasetSchemaVersion.fields))
        .where(Dataset.id == job.dataset_id)
    )
    assert dataset is not None
    schema = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    fields = [field.source_name or field.name for field in schema.fields]
    job_directory = request.app.state.data_root / "staging" / job.id
    target = job_directory / "stock_basic.csv"
    report_path = job_directory / "review.json"

    try:
        row_count = collect_stock_basic(target, fields, load_tushare_token())
        job.source_file_name = target.name
        job.staged_path = target.relative_to(request.app.state.data_root).as_posix()
        job.source_size_bytes = target.stat().st_size
        job.source_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        job.status = CollectionJobStatus.STAGED.value
        passed = review_stock_basic(target, schema, report_path)
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
