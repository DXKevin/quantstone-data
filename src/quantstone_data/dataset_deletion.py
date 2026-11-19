"""经过影响审查的数据集批量物理删除。"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import get_session
from .logging_config import log_event
from .models import (
    CatalogFile,
    CatalogPartition,
    CollectionJob,
    CollectionRun,
    Dataset,
    DatasetField,
    DatasetSchemaVersion,
    MaintenanceJob,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])
SessionDep = Annotated[Session, Depends(get_session)]
BUSY_STATUSES = {"queued", "running", "cancelling"}


class DeletionSelection(BaseModel):
    dataset_ids: list[str] = Field(min_length=1, max_length=100)


class DeletionCommit(DeletionSelection):
    review_token: str = Field(min_length=64, max_length=64)
    confirmation: str = Field(min_length=1, max_length=4096)


def _safe_size(path: Path, root: Path) -> tuple[int, int]:
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return 0, 0
    if resolved.is_file():
        return 1, resolved.stat().st_size
    if not resolved.is_dir():
        return 0, 0
    files = [item for item in resolved.rglob("*") if item.is_file()]
    return len(files), sum(item.stat().st_size for item in files)


def _dedupe_paths(paths: list[Path], root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted({item.resolve() for item in paths}, key=lambda item: len(item.parts)):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if any(path == parent or parent in path.parents for parent in result):
            continue
        result.append(path)
    return result


def build_deletion_review(session: Session, data_root: Path, ids: list[str]) -> dict:
    dataset_ids = sorted(set(ids))
    if len(dataset_ids) != len(ids):
        raise HTTPException(status_code=422, detail="数据集 ID 不能重复")
    datasets = list(session.scalars(select(Dataset).where(Dataset.id.in_(dataset_ids))))
    found = {item.id for item in datasets}
    missing = [item for item in dataset_ids if item not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"数据集不存在：{'、'.join(missing)}")

    blockers: list[str] = []
    items: list[dict] = []
    root = data_root.resolve()
    for dataset in sorted(datasets, key=lambda item: item.id):
        jobs = list(
            session.scalars(select(CollectionJob).where(CollectionJob.dataset_id == dataset.id))
        )
        maintenance = list(
            session.scalars(select(MaintenanceJob).where(MaintenanceJob.dataset_id == dataset.id))
        )
        busy = [item.id for item in jobs + maintenance if item.status in BUSY_STATUSES]
        if busy:
            blockers.append(f"{dataset.id} 存在排队或执行中的任务：{'、'.join(busy)}")
        dependents = [
            item.id
            for item in session.scalars(select(Dataset).where(Dataset.id.not_in(dataset_ids)))
            if (item.storage_policy or {}).get("calendar_dataset_id") == dataset.id
        ]
        if dependents:
            blockers.append(f"{dataset.id} 仍被数据集引用：{'、'.join(dependents)}")
        catalog_files = list(
            session.scalars(select(CatalogFile).where(CatalogFile.dataset_id == dataset.id))
        )
        partition_count = (
            session.scalar(
                select(func.count())
                .select_from(CatalogPartition)
                .where(CatalogPartition.dataset_id == dataset.id)
            )
            or 0
        )
        run_count = (
            session.scalar(
                select(func.count())
                .select_from(CollectionRun)
                .join(CollectionJob, CollectionRun.job_id == CollectionJob.id)
                .where(CollectionJob.dataset_id == dataset.id)
            )
            or 0
        )
        paths = [root / "datasets" / dataset.id, root / "revisions" / dataset.id]
        paths += [root / "staging" / job.id for job in jobs]
        paths += [root / "logs" / "collection" / f"{job.id}.log" for job in jobs]
        paths += [root / item.path for item in catalog_files]
        sizes = [_safe_size(path, root) for path in _dedupe_paths(paths, root)]
        items.append(
            {
                "dataset_id": dataset.id,
                "display_name": dataset.display_name,
                "status": dataset.status,
                "collection_jobs": len(jobs),
                "collection_runs": int(run_count),
                "maintenance_jobs": len(maintenance),
                "catalog_files": len(catalog_files),
                "catalog_partitions": int(partition_count),
                "rows": sum(item.row_count for item in catalog_files),
                "physical_files": sum(item[0] for item in sizes),
                "physical_bytes": sum(item[1] for item in sizes),
            }
        )
    confirmation = "永久删除：" + "、".join(dataset_ids)
    snapshot = {
        "dataset_ids": dataset_ids,
        "items": items,
        "blockers": blockers,
        "confirmation_text": confirmation,
    }
    token = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    return {**snapshot, "review_token": token, "can_delete": not blockers}


@router.post("/deletion-review")
def review_dataset_deletion(
    payload: DeletionSelection, request: Request, session: SessionDep
) -> dict:
    return build_deletion_review(session, request.app.state.data_root, payload.dataset_ids)


@router.post("/batch-delete")
def delete_datasets(payload: DeletionCommit, request: Request, session: SessionDep) -> dict:
    review = build_deletion_review(session, request.app.state.data_root, payload.dataset_ids)
    if review["blockers"]:
        raise HTTPException(status_code=409, detail="；".join(review["blockers"]))
    if payload.review_token != review["review_token"]:
        raise HTTPException(status_code=409, detail="数据集状态已变化，请重新执行删除审查")
    if payload.confirmation != review["confirmation_text"]:
        raise HTTPException(status_code=422, detail="删除确认文字不匹配")

    root = request.app.state.data_root.resolve()
    ids = review["dataset_ids"]
    jobs = list(session.scalars(select(CollectionJob).where(CollectionJob.dataset_id.in_(ids))))
    job_ids = [item.id for item in jobs]
    files = list(session.scalars(select(CatalogFile).where(CatalogFile.dataset_id.in_(ids))))
    paths = [root / "datasets" / item for item in ids] + [root / "revisions" / item for item in ids]
    paths += [root / "staging" / item for item in job_ids]
    paths += [root / "logs" / "collection" / f"{item}.log" for item in job_ids]
    paths += [root / item.path for item in files]

    # 先把文件原子移动到同一数据根目录下的临时删除区；数据库提交失败时可恢复。
    trash = root / ".deleting" / uuid4().hex
    moved: list[tuple[Path, Path]] = []
    try:
        trash.mkdir(parents=True)
        for index, path in enumerate(_dedupe_paths(paths, root)):
            if not path.exists():
                continue
            target = trash / str(index)
            shutil.move(path, target)
            moved.append((path, target))

        if job_ids:
            session.execute(delete(CollectionRun).where(CollectionRun.job_id.in_(job_ids)))
        session.execute(delete(CatalogPartition).where(CatalogPartition.dataset_id.in_(ids)))
        session.execute(delete(CatalogFile).where(CatalogFile.dataset_id.in_(ids)))
        session.execute(delete(MaintenanceJob).where(MaintenanceJob.dataset_id.in_(ids)))
        session.execute(delete(CollectionJob).where(CollectionJob.dataset_id.in_(ids)))
        schema_ids = list(
            session.scalars(
                select(DatasetSchemaVersion.id).where(
                    DatasetSchemaVersion.dataset_id.in_(ids)
                )
            )
        )
        if schema_ids:
            session.execute(
                delete(DatasetField).where(DatasetField.schema_version_id.in_(schema_ids))
            )
        session.execute(
            delete(DatasetSchemaVersion).where(DatasetSchemaVersion.dataset_id.in_(ids))
        )
        session.execute(delete(Dataset).where(Dataset.id.in_(ids)))
        session.commit()
    except Exception as error:
        session.rollback()
        for original, staged in reversed(moved):
            if staged.exists() and not original.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(staged, original)
        shutil.rmtree(trash, ignore_errors=True)
        raise HTTPException(status_code=500, detail="物理删除失败，数据集未删除") from error

    shutil.rmtree(trash)
    try:
        trash.parent.rmdir()
    except OSError:
        pass
    log_event("datasets_physically_deleted", dataset_ids=ids, count=len(ids))
    return {"deleted_dataset_ids": ids}
