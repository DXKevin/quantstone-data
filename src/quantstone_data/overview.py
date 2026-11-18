"""数据集级概览：把 Catalog 与存储信息聚合成一张数据卡。"""

from __future__ import annotations

from datetime import date
from typing import Annotated

import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_session
from .models import CatalogPartition, Dataset

router = APIRouter(prefix="/overview", tags=["overview"])
SessionDep = Annotated[Session, Depends(get_session)]


def _open_days(data_root, catalog: CatalogPartition | None) -> list[date]:
    if catalog is None:
        return []
    path = data_root / catalog.file_path
    if not path.is_file():
        return []
    table = pq.read_table(path, columns=["cal_date", "is_open"])
    return [row["cal_date"] for row in table.to_pylist() if row["is_open"] == 1]


def _serialize_timestamp(value) -> str | None:
    return value.isoformat() if value else None


@router.get("/datasets")
def dataset_overview(request: Request, session: SessionDep) -> list[dict]:
    data_root = request.app.state.data_root
    datasets = list(session.scalars(select(Dataset).order_by(Dataset.id)))
    aggregates = {
        row[0]: row
        for row in session.execute(
            select(
                CatalogPartition.dataset_id,
                func.count(CatalogPartition.id),
                func.count(func.distinct(CatalogPartition.file_path)),
                func.coalesce(func.sum(CatalogPartition.row_count), 0),
                func.coalesce(func.sum(CatalogPartition.size_bytes), 0),
                func.min(CatalogPartition.partition_key),
                func.max(CatalogPartition.partition_key),
                func.max(CatalogPartition.published_at),
            ).group_by(CatalogPartition.dataset_id)
        )
    }
    missing: dict[str, int] = {}
    for item in session.scalars(select(CatalogPartition)):
        if not (data_root / item.file_path).is_file():
            missing[item.dataset_id] = missing.get(item.dataset_id, 0) + 1

    calendars: dict[str, list[date]] = {}
    for dataset in datasets:
        policy = dataset.storage_policy or {}
        calendar_id = policy.get("calendar_dataset_id")
        if not calendar_id or calendar_id in calendars:
            continue
        latest = session.scalar(
            select(CatalogPartition)
            .where(CatalogPartition.dataset_id == calendar_id)
            .order_by(CatalogPartition.published_at.desc())
            .limit(1)
        )
        calendars[calendar_id] = _open_days(data_root, latest)

    overview: list[dict] = []
    today = date.today()
    for dataset in datasets:
        policy = dataset.storage_policy or {}
        row = aggregates.get(dataset.id)
        partitions = int(row[1]) if row else 0
        files = int(row[2]) if row else 0
        rows = int(row[3]) if row else 0
        size_bytes = int(row[4]) if row else 0
        first_partition = row[5] if row else None
        latest_partition = row[6] if row else None
        published_at = _serialize_timestamp(row[7]) if row else None

        expected_partitions: int | None = None
        coverage_percent: float | None = None
        calendar_id = policy.get("calendar_dataset_id")
        open_days = calendars.get(calendar_id or "", [])
        if open_days and first_partition:
            try:
                start = date.fromisoformat(first_partition)
            except ValueError:
                start = None
            if start is not None:
                upper = min(today, max(open_days))
                expected_partitions = sum(1 for item in open_days if start <= item <= upper)
                if expected_partitions:
                    coverage_percent = round(partitions * 100 / expected_partitions, 1)

        overview.append(
            {
                "dataset_id": dataset.id,
                "display_name": dataset.display_name,
                "status": dataset.status,
                "provider": dataset.provider,
                "region": dataset.region,
                "instrument": dataset.instrument,
                "market": dataset.market,
                "layout": policy.get("layout"),
                "calendar_dataset_id": calendar_id,
                "partitions": partitions,
                "files": files,
                "rows": rows,
                "size_bytes": size_bytes,
                "first_partition": first_partition,
                "latest_partition": latest_partition,
                "published_at": published_at,
                "missing_files": missing.get(dataset.id, 0),
                "expected_partitions": expected_partitions,
                "coverage_percent": coverage_percent,
            }
        )
    return overview
