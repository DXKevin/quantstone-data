from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CatalogFile, CatalogPartition


def upsert_file(
    session: Session,
    *,
    dataset_id: str,
    path: str,
    row_count: int,
    size_bytes: int,
    sha256: str,
) -> CatalogFile:
    item = session.scalar(select(CatalogFile).where(CatalogFile.path == path))
    if item is None:
        item = CatalogFile(dataset_id=dataset_id, path=path)
        session.add(item)
    item.row_count = row_count
    item.size_bytes = size_bytes
    item.sha256 = sha256
    session.flush()
    return item


def upsert_partition(
    session: Session,
    *,
    dataset_id: str,
    partition_key: str,
    file_path: str,
    file_id: int,
    row_count: int,
    size_bytes: int,
    sha256: str,
    collection_run_id: str,
) -> tuple[CatalogPartition, str | None]:
    catalog = session.scalar(
        select(CatalogPartition).where(
            CatalogPartition.dataset_id == dataset_id,
            CatalogPartition.partition_key == partition_key,
        )
    )
    previous_path = catalog.file_path if catalog else None
    if catalog is None:
        catalog = CatalogPartition(dataset_id=dataset_id, partition_key=partition_key)
        session.add(catalog)
    catalog.file_path = file_path
    catalog.file_id = file_id
    catalog.row_count = row_count
    catalog.size_bytes = size_bytes
    catalog.sha256 = sha256
    catalog.collection_run_id = collection_run_id
    return catalog, previous_path
