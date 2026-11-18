from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_session
from .models import CatalogFile, CatalogPartition, CollectionRun

router = APIRouter(tags=["catalog"])
SessionDep = Annotated[Session, Depends(get_session)]


def serialize_partition(item: CatalogPartition) -> dict:
    return {
        "dataset_id": item.dataset_id,
        "partition_key": item.partition_key,
        "file_path": item.file_path,
        "row_count": item.row_count,
        "size_bytes": item.size_bytes,
        "sha256": item.sha256,
        "collection_run_id": item.collection_run_id,
        "published_at": item.published_at,
    }


@router.get("/catalog/partitions")
def list_catalog_partitions(
    session: SessionDep,
    dataset_id: str | None = None,
) -> list[dict]:
    query = select(CatalogPartition).order_by(
        CatalogPartition.dataset_id,
        CatalogPartition.partition_key.desc(),
    )
    if dataset_id:
        query = query.where(CatalogPartition.dataset_id == dataset_id)
    items = session.scalars(query)
    return [serialize_partition(item) for item in items]


@router.get("/storage/overview")
def storage_overview(request: Request, session: SessionDep) -> dict:
    data_root = request.app.state.data_root
    partition_count = session.scalar(select(func.count(CatalogPartition.id))) or 0
    file_totals = session.execute(
        select(
            func.count(CatalogFile.id),
            func.coalesce(func.sum(CatalogFile.row_count), 0),
            func.coalesce(func.sum(CatalogFile.size_bytes), 0),
        )
    ).one()
    staged_runs = session.scalar(
        select(func.count(CollectionRun.id)).where(CollectionRun.staged_path.is_not(None))
    )
    missing_files = sum(
        1 for item in session.scalars(select(CatalogFile)) if not (data_root / item.path).is_file()
    )
    return {
        "data_root": str(data_root),
        "published_partitions": partition_count,
        "published_files": file_totals[0],
        "published_rows": file_totals[1],
        "published_bytes": file_totals[2],
        "staged_runs": staged_runs or 0,
        "missing_files": missing_files,
    }


@router.get("/collection-jobs/{job_id}/runs")
def list_collection_runs(job_id: str, session: SessionDep) -> list[dict]:
    items = session.scalars(
        select(CollectionRun)
        .where(CollectionRun.job_id == job_id)
        .order_by(CollectionRun.partition_key)
    )
    return [
        {
            "id": item.id,
            "partition_key": item.partition_key,
            "status": item.status,
            "staged_path": item.staged_path,
            "published_path": item.published_path,
            "row_count": item.row_count,
            "error": item.error,
        }
        for item in items
    ]
