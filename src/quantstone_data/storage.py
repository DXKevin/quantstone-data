"""数据读取与文件合并：读取时按文件分组，合并时减少小文件数量。"""

from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CatalogFile, CatalogPartition, Dataset
from .publishing.catalog_writer import upsert_file


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_dataset_rows(
    session: Session,
    data_root: Path,
    dataset_id: str,
    start: date | None = None,
    end: date | None = None,
    limit: int = 1000,
) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise KeyError(dataset_id)
    policy = dataset.storage_policy or {}
    partition_field = policy.get("logical_partition_field")

    query = select(CatalogPartition).where(CatalogPartition.dataset_id == dataset_id)
    if start is not None:
        query = query.where(CatalogPartition.partition_key >= start.isoformat())
    if end is not None:
        query = query.where(CatalogPartition.partition_key <= end.isoformat())
    partitions = list(session.scalars(query.order_by(CatalogPartition.partition_key)))

    by_file: dict[str, set[str]] = {}
    for item in partitions:
        by_file.setdefault(item.file_path, set()).add(item.partition_key)

    rows: list[dict] = []
    columns: list[str] = []
    for path in sorted(by_file):
        file_path = data_root / path
        if not file_path.is_file():
            continue
        table = pq.read_table(file_path)
        columns = table.column_names
        if partition_field and partition_field in table.column_names:
            wanted = by_file[path]
            mask = [
                str(value) in wanted
                or (hasattr(value, "isoformat") and value.isoformat() in wanted)
                for value in table[partition_field].to_pylist()
            ]
            table = table.filter(mask)
        rows.extend(table.to_pylist())
        if len(rows) >= limit:
            break

    return {
        "dataset_id": dataset_id,
        "files_read": len(by_file),
        "row_count": min(len(rows), limit),
        "columns": columns,
        "rows": rows[:limit],
    }


def compact_year(
    session: Session,
    data_root: Path,
    dataset_id: str,
    year: int,
) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise KeyError(dataset_id)

    prefix = f"{year:04d}-"
    partitions = list(
        session.scalars(
            select(CatalogPartition)
            .where(
                CatalogPartition.dataset_id == dataset_id,
                CatalogPartition.partition_key.like(f"{prefix}%"),
            )
            .order_by(CatalogPartition.partition_key)
        )
    )
    if not partitions:
        return {"dataset_id": dataset_id, "year": year, "status": "empty", "partitions": 0}

    target_rel = f"datasets/{dataset_id}/annual/{year}.parquet"
    sources = sorted({item.file_path for item in partitions} - {target_rel})
    if not sources:
        return {
            "dataset_id": dataset_id,
            "year": year,
            "status": "already_compacted",
            "partitions": len(partitions),
            "files": 1,
        }

    tables = []
    for path in sources:
        source = data_root / path
        if source.is_file():
            tables.append(pq.read_table(source))
    if not tables:
        return {"dataset_id": dataset_id, "year": year, "status": "missing_files", "partitions": 0}

    merged = pa.concat_tables(tables)
    target = data_root / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    pq.write_table(merged, temporary, compression="zstd")
    os.replace(temporary, target)

    file_row = upsert_file(
        session,
        dataset_id=dataset_id,
        path=target_rel,
        row_count=merged.num_rows,
        size_bytes=target.stat().st_size,
        sha256=_sha256(target),
    )
    for item in partitions:
        item.file_id = file_row.id
        item.file_path = target_rel

    revisions = data_root / "revisions" / dataset_id / f"{year:04d}"
    revisions.mkdir(parents=True, exist_ok=True)
    for path in sources:
        source = data_root / path
        if source.is_file():
            os.replace(source, revisions / source.name)
        stale = session.scalar(select(CatalogFile).where(CatalogFile.path == path))
        if stale is not None:
            session.delete(stale)
    session.commit()

    return {
        "dataset_id": dataset_id,
        "year": year,
        "status": "compacted",
        "partitions": len(partitions),
        "source_files": len(sources),
        "rows": merged.num_rows,
        "path": target_rel,
    }
