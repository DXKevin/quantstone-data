import hashlib
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..logging_config import log_event
from ..models import CatalogFile, CatalogPartition, CollectionRun
from .catalog_writer import upsert_file, upsert_partition
from .path_resolver import resolve_partition_target


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
        (data_root / path).unlink(missing_ok=True)
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
    digest = _sha256(target)
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
        replaced_path=previous_path,
    )
    return catalog
