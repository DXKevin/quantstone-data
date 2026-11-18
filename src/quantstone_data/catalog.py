from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .models import CatalogPartition, CollectionRun

router = APIRouter(tags=["catalog"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/catalog/partitions")
def list_catalog_partitions(dataset_id: str, session: SessionDep) -> list[dict]:
    items = session.scalars(
        select(CatalogPartition)
        .where(CatalogPartition.dataset_id == dataset_id)
        .order_by(CatalogPartition.partition_key)
    )
    return [
        {
            "dataset_id": item.dataset_id,
            "partition_key": item.partition_key,
            "file_path": item.file_path,
            "row_count": item.row_count,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
            "collection_run_id": item.collection_run_id,
            "published_at": item.published_at,
        }
        for item in items
    ]


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
