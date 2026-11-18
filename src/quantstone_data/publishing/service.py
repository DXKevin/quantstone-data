import hashlib
import os
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import CatalogPartition, CollectionRun
from .catalog_writer import upsert_partition
from .path_resolver import resolve_partition_target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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
    catalog, previous_path = upsert_partition(
        session,
        dataset_id=dataset_id,
        partition_key=partition_key,
        file_path=relative_target,
        row_count=row_count,
        size_bytes=target.stat().st_size,
        sha256=_sha256(target),
        collection_run_id=run.id,
    )
    if previous_path and previous_path != relative_target:
        (data_root / previous_path).unlink(missing_ok=True)
    run.published_path = relative_target
    run.staged_path = None
    run.status = "succeeded"
    return catalog
