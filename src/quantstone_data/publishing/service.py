import hashlib
import os
import threading
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..file_cleanup import remove_empty_parent_directories
from ..logging_config import log_event
from ..models import CatalogFile, CatalogPartition, CollectionRun
from .catalog_writer import upsert_file, upsert_partition
from .path_resolver import resolve_partition_target

_CATALOG_WRITE_LOCK = threading.RLock()


def catalog_write_lock() -> threading.RLock:
    """返回进程内 Catalog 写锁；必须只包围短事务，不得覆盖采集和文件解析。"""
    return _CATALOG_WRITE_LOCK


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _drop_unreferenced_file(
    session: Session,
    *,
    data_root: Path,
    path: str,
) -> None:
    """删除被替换的旧文件及其 CatalogFile 记录，但仍被其他分区引用时保留。"""
    stale = session.scalar(select(CatalogFile).where(CatalogFile.path == path))
    if stale is None:
        return
    referenced = session.scalar(
        select(CatalogPartition.id).where(CatalogPartition.file_id == stale.id).limit(1)
    )
    if referenced is None:
        stale_path = data_root / path
        stale_path.unlink(missing_ok=True)
        remove_empty_parent_directories(
            stale_path,
            stop=data_root / "datasets" / stale.dataset_id,
        )
        session.delete(stale)


def publish_partition(
    session: Session,
    *,
    data_root: Path,
    dataset_id: str,
    storage_policy: dict,
    partition_key: str,
    artifact_path: Path,
    row_count: int,
    run: CollectionRun,
    calculate_sha256: bool = True,
) -> CatalogPartition:
    target = resolve_partition_target(
        data_root,
        dataset_id,
        storage_policy,
        partition_key,
        run.id,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(artifact_path, target)
    relative_target = target.relative_to(data_root).as_posix()
    size_bytes = target.stat().st_size
    digest = _sha256(target) if calculate_sha256 else ""
    file_row = upsert_file(
        session,
        dataset_id=dataset_id,
        path=relative_target,
        row_count=row_count,
        size_bytes=size_bytes,
        sha256=digest,
    )
    catalog, previous_path = upsert_partition(
        session,
        dataset_id=dataset_id,
        partition_key=partition_key,
        file_path=relative_target,
        file_id=file_row.id,
        row_count=row_count,
        size_bytes=size_bytes,
        sha256=digest,
        collection_run_id=run.id,
    )
    if previous_path and previous_path != relative_target:
        _drop_unreferenced_file(session, data_root=data_root, path=previous_path)
    run.published_path = relative_target
    run.staged_path = None
    run.status = "succeeded"
    log_event(
        "partition_published",
        job_id=run.job_id,
        run_id=run.id,
        dataset_id=dataset_id,
        partition_key=partition_key,
        file_path=relative_target,
        row_count=row_count,
        size_bytes=size_bytes,
        sha256_calculated=calculate_sha256,
        replaced_path=previous_path,
    )
    return catalog


def publish_partition_transaction(
    session: Session,
    *,
    data_root: Path,
    dataset_id: str,
    storage_policy: dict,
    partition_key: str,
    artifact_path: Path,
    row_count: int,
    run: CollectionRun,
    calculate_sha256: bool = True,
) -> CatalogPartition:
    """在共享短锁中原子发布文件和 Catalog，失败时将文件退回 staging。"""
    target = resolve_partition_target(
        data_root,
        dataset_id,
        storage_policy,
        partition_key,
        run.id,
    )
    with _CATALOG_WRITE_LOCK:
        try:
            catalog = publish_partition(
                session,
                data_root=data_root,
                dataset_id=dataset_id,
                storage_policy=storage_policy,
                partition_key=partition_key,
                artifact_path=artifact_path,
                row_count=row_count,
                run=run,
                calculate_sha256=calculate_sha256,
            )
            session.commit()
            return catalog
        except Exception:
            session.rollback()
            if target.exists() and not artifact_path.exists():
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, artifact_path)
            raise
