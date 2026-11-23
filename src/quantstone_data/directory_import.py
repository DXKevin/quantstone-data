from __future__ import annotations

import errno
import json
import os
import shutil
import threading
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .import_schemas import ImportJobCreate, ImportJobRead, ImportJobStatus
from .logging_config import log_event
from .models import (
    CatalogPartition,
    CollectionJob,
    CollectionRun,
    Dataset,
    DatasetSchemaVersion,
    ImportJob,
)
from .publishing import publish_partition_transaction
from .publishing.path_resolver import resolve_partition_target
from .reviewer_registry import review_dataset
from .reviewer_types import ReviewContext
from .scanner_registry import SCANNERS, get_scanner_operation

router = APIRouter(tags=["directory imports"])
SessionDep = Annotated[Session, Depends(get_session)]

_CANCEL_REQUESTS: set[str] = set()
_RUNNING_IMPORTS: set[str] = set()
_IMPORT_LOCK = threading.Lock()


def serialize_job(job: ImportJob) -> ImportJobRead:
    return ImportJobRead.model_validate(job, from_attributes=True)


def _allowed_roots(data_root: Path) -> list[Path]:
    roots = [data_root / "imports"]
    configured = os.environ.get("QUANTSTONE_IMPORT_ROOTS", "")
    for item in configured.split(":"):
        value = item.strip()
        if value:
            roots.append(Path(value).expanduser())
    return [item.resolve() for item in roots]


def _resolve_source_root(data_root: Path, value: str) -> Path:
    source = Path(value).expanduser().resolve()
    if not source.is_dir():
        raise HTTPException(status_code=422, detail=f"扫描目录不存在：{source}")
    if not any(source.is_relative_to(root) for root in _allowed_roots(data_root)):
        raise HTTPException(status_code=403, detail="扫描目录不在允许的导入根目录内")
    return source


def _manifest_path(data_root: Path, job_id: str) -> Path:
    return data_root / "imports" / "jobs" / job_id / "manifest.json"


def _relative_manifest_path(data_root: Path, job_id: str) -> str:
    return _manifest_path(data_root, job_id).relative_to(data_root).as_posix()


def _write_manifest(data_root: Path, job_id: str, manifest: dict) -> None:
    path = _manifest_path(data_root, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("manifest.json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def _schema_for(dataset: Dataset) -> DatasetSchemaVersion:
    return next(
        item
        for item in dataset.schemas
        if item.version == dataset.current_schema_version
    )


def _summary(entries: list[dict]) -> dict:
    counts = {
        "ready": sum(1 for item in entries if item["status"] == "ready"),
        "duplicates": sum(1 for item in entries if item["status"] == "duplicate"),
        "invalid": sum(1 for item in entries if item["status"] == "invalid"),
        "rows": sum(
            int(item.get("row_count") or 0)
            for item in entries
            if item["status"] == "ready"
        ),
    }
    return {"files": len(entries), **counts}


def _scan_job(job_id: str, session_factory, data_root: Path) -> None:
    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None:
            return
        if job.id in _CANCEL_REQUESTS:
            job.status = ImportJobStatus.CANCELLED.value
            session.commit()
            return
        job.status = ImportJobStatus.SCANNING.value
        session.commit()
        try:
            dataset = session.get(Dataset, job.dataset_id)
            if dataset is None:
                raise ValueError("数据集不存在")
            operation = get_scanner_operation(job.scanner_key, job.operation)
            if operation is None:
                raise ValueError("扫描器操作不存在")
            schema = _schema_for(dataset)
            source_root = _resolve_source_root(
                data_root, str(job.parameters.get("source_root") or "")
            )
            start = job.parameters.get("start_date")
            end = job.parameters.get("end_date")
            start_date = date.fromisoformat(start) if start else None
            end_date = date.fromisoformat(end) if end else None
            existing = {
                item.partition_key
                for item in session.scalars(
                    select(CatalogPartition).where(
                        CatalogPartition.dataset_id == dataset.id
                    )
                )
            }
            entries: list[dict] = []
            for directory in sorted(source_root.iterdir()):
                if not directory.is_dir() or not directory.name.isdigit():
                    continue
                if len(directory.name) != 8:
                    continue
                try:
                    trade_date = datetime.strptime(directory.name, "%Y%m%d").date()
                except ValueError:
                    continue
                partition_key = trade_date.isoformat()
                if start_date and trade_date < start_date:
                    continue
                if end_date and trade_date > end_date:
                    continue
                source = directory / operation.filename
                entry = {
                    "partition_key": partition_key,
                    "path": str(source),
                    "size_bytes": source.stat().st_size if source.is_file() else None,
                    "mtime": (
                        datetime.fromtimestamp(
                            source.stat().st_mtime, tz=UTC
                        ).isoformat()
                        if source.is_file()
                        else None
                    ),
                    "row_count": None,
                    "status": "invalid",
                    "errors": [],
                }
                if not source.is_file():
                    entry["errors"] = [{"rule": "missing_file", "path": str(source)}]
                    entries.append(entry)
                    continue
                if partition_key in existing:
                    entry["status"] = "duplicate"
                    existing_partition = session.scalar(
                        select(CatalogPartition).where(
                            CatalogPartition.dataset_id == dataset.id,
                            CatalogPartition.partition_key == partition_key,
                        )
                    )
                    entry["row_count"] = (
                        existing_partition.row_count if existing_partition else None
                    )
                    entries.append(entry)
                    continue
                try:
                    report = review_dataset(
                        dataset.id, ReviewContext(source, schema, trade_date)
                    )
                    entry["row_count"] = report.row_count
                    entry["status"] = "ready" if report.passed else "invalid"
                    entry["errors"] = list(report.errors)
                except Exception as error:
                    entry["errors"] = [{"rule": "scan_error", "message": str(error)}]
                entries.append(entry)
                if job.id in _CANCEL_REQUESTS:
                    job.status = ImportJobStatus.CANCELLED.value
                    session.commit()
                    return
            summary = _summary(entries)
            manifest = {
                "job_id": job.id,
                "dataset_id": dataset.id,
                "scanner_key": job.scanner_key,
                "operation": job.operation,
                "source_root": str(source_root),
                "generated_at": datetime.now(UTC).isoformat(),
                "files": entries,
                "summary": summary,
            }
            _write_manifest(data_root, job.id, manifest)
            job.manifest_path = _relative_manifest_path(data_root, job.id)
            job.summary = summary
            if summary["ready"] == 0:
                if summary["duplicates"] > 0 and summary["invalid"] == 0:
                    job.status = ImportJobStatus.SUCCEEDED.value
                    job.error = None
                else:
                    job.status = ImportJobStatus.FAILED.value
                    job.error = "扫描完成，但没有可导入的新文件"
            else:
                job.status = ImportJobStatus.REVIEW_READY.value
                job.error = None
            session.commit()
            log_event(
                "import_scan_completed",
                import_job_id=job.id,
                dataset_id=job.dataset_id,
                summary=summary,
            )
        except Exception as error:
            session.rollback()
            job = session.get(ImportJob, job_id)
            if job is not None:
                job.status = ImportJobStatus.FAILED.value
                job.error = str(error) or error.__class__.__name__
                session.commit()
            log_event(
                "import_scan_failed",
                level=40,
                import_job_id=job_id,
                error=str(error),
                exc_info=True,
            )


def _stage_and_publish(
    session: Session,
    data_root: Path,
    job: ImportJob,
    dataset: Dataset,
    schema: DatasetSchemaVersion,
    entry: dict,
    collection_job: CollectionJob,
) -> None:
    source = Path(entry["path"])
    if not source.is_file():
        raise ValueError(f"源文件不存在：{source}")
    size = source.stat().st_size
    mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=UTC).isoformat()
    if entry.get("size_bytes") != size or entry.get("mtime") != mtime:
        raise ValueError(f"源文件在扫描后发生变化：{source}")
    trade_date = date.fromisoformat(entry["partition_key"])
    run = CollectionRun(
        id=str(uuid4()),
        job_id=collection_job.id,
        partition_key=entry["partition_key"],
        status="importing",
    )
    session.add(run)
    session.commit()
    staging = (
        data_root
        / "staging"
        / "imports"
        / job.id
        / f"{run.id}{source.suffix}"
    )
    staging.parent.mkdir(parents=True, exist_ok=True)
    transfer_mode = str(job.parameters.get("transfer_mode") or "move")
    moved_source = transfer_mode == "move"
    target = resolve_partition_target(
        data_root,
        dataset.id,
        dataset.storage_policy or {},
        entry["partition_key"],
        run.id,
    )
    try:
        if moved_source:
            try:
                os.replace(source, staging)
            except OSError as error:
                if error.errno == errno.EXDEV:
                    raise ValueError(
                        "源目录与数据目录不在同一文件系统，无法快速移动；请改用复制模式"
                    ) from error
                raise
        else:
            shutil.copy2(source, staging)
        report = review_dataset(dataset.id, ReviewContext(staging, schema, trade_date))
        if not report.passed:
            run.status = "review_failed"
            run.error = "；".join(
                str(item.get("rule") or item.get("message")) for item in report.errors
            )
            session.commit()
            raise ValueError(f"{entry['partition_key']} 审核失败：{run.error}")
        publish_partition_transaction(
            session,
            data_root=data_root,
            dataset_id=dataset.id,
            storage_policy=dataset.storage_policy or {},
            partition_key=entry["partition_key"],
            artifact_path=staging,
            row_count=report.row_count,
            run=run,
            calculate_sha256=False,
        )
    except Exception:
        if moved_source and not source.exists():
            restore_from = staging if staging.exists() else target
            if restore_from.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(restore_from, source)
        raise


def _run_import(job_id: str, session_factory, data_root: Path) -> None:
    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None or job.status != ImportJobStatus.REVIEW_READY.value:
            return
        if job.id in _CANCEL_REQUESTS:
            job.status = ImportJobStatus.CANCELLED.value
            session.commit()
            return
        with _IMPORT_LOCK:
            _RUNNING_IMPORTS.add(job.id)
        job.status = ImportJobStatus.IMPORTING.value
        session.commit()
        collection_job: CollectionJob | None = None
        try:
            dataset = session.get(Dataset, job.dataset_id)
            if dataset is None:
                raise ValueError("数据集不存在")
            schema = _schema_for(dataset)
            manifest = json.loads(
                (data_root / str(job.manifest_path)).read_text(encoding="utf-8")
            )
            ready = [item for item in manifest["files"] if item["status"] == "ready"]
            if not ready:
                raise ValueError("清单中没有可导入文件")
            dates = [date.fromisoformat(item["partition_key"]) for item in ready]
            collection_job = CollectionJob(
                id=str(uuid4()),
                dataset_id=dataset.id,
                operation="initial",
                input_method="directory_import",
                status="running",
                start_date=min(dates),
                end_date=max(dates),
                collector_key=job.scanner_key,
                collector_operation=job.operation,
                parameters={"import_job_id": job.id},
            )
            session.add(collection_job)
            session.commit()
            job.collection_job_id = collection_job.id
            session.commit()

            imported = 0
            rows = 0
            for entry in ready:
                if job.id in _CANCEL_REQUESTS:
                    collection_job.status = "cancelled"
                    job.status = ImportJobStatus.CANCELLED.value
                    session.commit()
                    log_event(
                        "import_job_cancelled",
                        import_job_id=job.id,
                        collection_job_id=collection_job.id,
                    )
                    return
                _stage_and_publish(
                    session, data_root, job, dataset, schema, entry, collection_job
                )
                imported += 1
                rows += int(entry.get("row_count") or 0)
                summary = dict(job.summary or {})
                summary["imported"] = imported
                summary["imported_rows"] = rows
                job.summary = summary
                session.commit()
                log_event(
                    "import_partition_published",
                    import_job_id=job.id,
                    collection_job_id=collection_job.id,
                    dataset_id=dataset.id,
                    partition_key=entry["partition_key"],
                    row_count=entry.get("row_count"),
                )
            collection_job.status = "succeeded"
            job.status = ImportJobStatus.SUCCEEDED.value
            job.error = None
            summary = dict(job.summary or {})
            summary["imported"] = imported
            summary["imported_rows"] = rows
            job.summary = summary
            session.commit()
            log_event(
                "import_job_completed",
                import_job_id=job.id,
                collection_job_id=collection_job.id,
                dataset_id=dataset.id,
                imported=imported,
                rows=rows,
            )
        except Exception as error:
            session.rollback()
            job = session.get(ImportJob, job_id)
            if job is not None:
                job.status = ImportJobStatus.FAILED.value
                job.error = str(error) or error.__class__.__name__
                if collection_job is not None:
                    stored_job = session.get(CollectionJob, collection_job.id)
                    if stored_job is not None:
                        stored_job.status = "failed"
                        stored_job.error = job.error
                session.commit()
            log_event(
                "import_job_failed",
                level=40,
                import_job_id=job_id,
                error=str(error),
                exc_info=True,
            )
        finally:
            with _IMPORT_LOCK:
                _RUNNING_IMPORTS.discard(job_id)


def recover_interrupted_import_jobs(session: Session) -> int:
    jobs = list(
        session.scalars(
            select(ImportJob).where(
                ImportJob.status.in_(
                    (
                        ImportJobStatus.SCANNING.value,
                        ImportJobStatus.IMPORTING.value,
                        ImportJobStatus.CANCELLING.value,
                    )
                )
            )
        )
    )
    for job in jobs:
        job.status = ImportJobStatus.FAILED.value
        job.error = "应用重启时导入任务尚未完成，已标记为失败；请重新扫描。"
    if jobs:
        session.commit()
    return len(jobs)


@router.get("/scanners")
def list_scanners() -> list[dict]:
    return [
        {
            "key": scanner.key,
            "name": scanner.name,
            "description": scanner.description,
            "operations": [
                {
                    "key": operation.key,
                    "name": operation.name,
                    "description": operation.description,
                    "dataset_id": operation.dataset_id,
                    "filename": operation.filename,
                }
                for operation in scanner.operations
            ],
        }
        for scanner in SCANNERS.values()
    ]


@router.post(
    "/import-jobs",
    response_model=ImportJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_import_job(
    payload: ImportJobCreate,
    request: Request,
    session: SessionDep,
) -> ImportJobRead:
    dataset = session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != "active":
        raise HTTPException(status_code=409, detail="只有已启用数据集可以导入")
    operation = get_scanner_operation(payload.scanner_key, payload.operation)
    if operation is None:
        raise HTTPException(status_code=404, detail="扫描器操作不存在")
    if operation.dataset_id != dataset.id:
        raise HTTPException(status_code=409, detail="扫描器操作与数据集不匹配")
    if (
        payload.start_date is not None
        and payload.end_date is not None
        and payload.start_date > payload.end_date
    ):
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    source_root = _resolve_source_root(
        request.app.state.data_root, payload.source_root
    )
    job = ImportJob(
        id=str(uuid4()),
        dataset_id=dataset.id,
        scanner_key=payload.scanner_key,
        operation=payload.operation,
        parameters={
            "source_root": str(source_root),
            "start_date": payload.start_date.isoformat() if payload.start_date else None,
            "end_date": payload.end_date.isoformat() if payload.end_date else None,
            "transfer_mode": payload.transfer_mode,
        },
        status=ImportJobStatus.CREATED.value,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    try:
        request.app.state.background_executor.submit(
            job.id,
            partial(
                _scan_job,
                job.id,
                request.app.state.session_factory,
                request.app.state.data_root,
            ),
            resource_key=f"dataset:{job.dataset_id}",
        )
    except RuntimeError as error:
        job.status = ImportJobStatus.FAILED.value
        job.error = "后台任务执行器不可用"
        session.commit()
        raise HTTPException(status_code=503, detail=job.error) from error
    log_event(
        "import_job_created",
        import_job_id=job.id,
        dataset_id=job.dataset_id,
        scanner_key=job.scanner_key,
        operation=job.operation,
        source_root=str(source_root),
        transfer_mode=payload.transfer_mode,
    )
    return serialize_job(job)


@router.get("/import-jobs", response_model=list[ImportJobRead])
def list_import_jobs(
    session: SessionDep,
    dataset_id: str | None = None,
    limit: int = 100,
) -> list[ImportJobRead]:
    query = select(ImportJob).order_by(ImportJob.created_at.desc()).limit(
        max(1, min(limit, 500))
    )
    if dataset_id:
        query = query.where(ImportJob.dataset_id == dataset_id)
    return [serialize_job(job) for job in session.scalars(query)]


@router.get("/import-jobs/{job_id}", response_model=ImportJobRead)
def get_import_job(job_id: str, session: SessionDep) -> ImportJobRead:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    return serialize_job(job)


@router.get("/import-jobs/{job_id}/manifest")
def get_import_manifest(job_id: str, request: Request, session: SessionDep) -> dict:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    if not job.manifest_path:
        raise HTTPException(status_code=409, detail="清单尚未生成")
    path = request.app.state.data_root / job.manifest_path
    if not path.is_file():
        raise HTTPException(status_code=409, detail="清单文件不存在")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/import-jobs/{job_id}/execute", response_model=ImportJobRead)
def execute_import_job(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> ImportJobRead:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    if job.status != ImportJobStatus.REVIEW_READY.value:
        raise HTTPException(status_code=409, detail="只有待审核完成的清单可以导入")
    try:
        request.app.state.background_executor.submit(
            job.id,
            partial(
                _run_import,
                job.id,
                request.app.state.session_factory,
                request.app.state.data_root,
            ),
            resource_key=f"dataset:{job.dataset_id}",
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="后台任务执行器不可用") from error
    log_event("import_job_execute_requested", import_job_id=job.id)
    return serialize_job(job)


@router.post("/import-jobs/{job_id}/cancel", response_model=ImportJobRead)
def cancel_import_job(
    job_id: str,
    request: Request,
    session: SessionDep,
) -> ImportJobRead:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    if job.status in {
        ImportJobStatus.SUCCEEDED.value,
        ImportJobStatus.FAILED.value,
        ImportJobStatus.CANCELLED.value,
    }:
        raise HTTPException(status_code=409, detail="导入任务已结束，无法取消")
    _CANCEL_REQUESTS.add(job.id)
    if request.app.state.background_executor.cancel(job.id):
        _CANCEL_REQUESTS.discard(job.id)
        job.status = ImportJobStatus.CANCELLED.value
    else:
        job.status = ImportJobStatus.CANCELLING.value
    session.commit()
    log_event("import_job_cancel_requested", import_job_id=job.id)
    return serialize_job(job)


# 让扫描/导入任务在启动时的恢复逻辑能找到状态常量。
IMPORT_STATUSES = tuple(item.value for item in ImportJobStatus)
