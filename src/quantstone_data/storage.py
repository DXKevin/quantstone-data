"""数据读取与文件合并：读取时按文件分组，合并时减少小文件数量。"""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from .file_cleanup import remove_empty_parent_directories
from .models import CatalogFile, CatalogPartition, Dataset
from .publishing.catalog_writer import upsert_file


class MissingCatalogFilesError(RuntimeError):
    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        super().__init__("Catalog 指向的文件缺失：" + "；".join(paths))


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
    primary_key_filters: dict[str, str] | None = None,
) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise KeyError(dataset_id)
    policy = dataset.storage_policy or {}
    partition_field = policy.get("logical_partition_field")
    schema_version = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    primary_keys = set(schema_version.primary_key_fields)
    filters = primary_key_filters or {}
    query_mode = bool(filters) or start is not None or end is not None
    unknown_filters = set(filters) - primary_keys
    if unknown_filters:
        raise ValueError(f"只能按主键字段筛选：{', '.join(sorted(primary_keys))}")

    query = select(CatalogPartition).where(CatalogPartition.dataset_id == dataset_id)
    if start is not None:
        query = query.where(CatalogPartition.partition_key >= start.isoformat())
    if end is not None:
        query = query.where(CatalogPartition.partition_key <= end.isoformat())
    partitions = list(session.scalars(query.order_by(CatalogPartition.partition_key)))

    by_file: dict[str, set[str]] = {}
    for item in partitions:
        by_file.setdefault(item.file_path, set()).add(item.partition_key)

    missing_files = sorted(path for path in by_file if not (data_root / path).is_file())
    if missing_files:
        raise MissingCatalogFilesError(missing_files)

    rows: list[dict] = []
    columns: list[str] = []
    files_read = 0
    matched_count = 0
    for path in sorted(by_file):
        file_path = data_root / path
        parquet_filters: list[tuple[str, str, object]] = []
        schema = pq.read_schema(file_path)
        if partition_field:
            if partition_field not in schema.names:
                raise ValueError(f"文件 {path} 缺少逻辑分区字段 {partition_field}")
            field_type = schema.field(partition_field).type
            wanted = sorted(by_file[path])
            filter_values = (
                [date.fromisoformat(value) for value in wanted]
                if pa.types.is_date(field_type)
                else wanted
            )
            parquet_filters.append((partition_field, "in", filter_values))
        for field_name, raw_value in filters.items():
            if field_name not in schema.names:
                raise ValueError(f"文件 {path} 缺少主键字段 {field_name}")
            parquet_filters.append(
                (field_name, "=", _coerce_filter_value(raw_value, schema.field(field_name).type))
            )
        table = pq.read_table(file_path, filters=parquet_filters or None)
        files_read += 1
        columns = table.column_names
        matched_count += table.num_rows
        remaining = limit - len(rows)
        if remaining > 0:
            rows.extend(table.slice(0, remaining).to_pylist())
        if not query_mode and len(rows) >= limit:
            break

    return {
        "dataset_id": dataset_id,
        "files_read": files_read,
        "row_count": min(len(rows), limit),
        "matched_count": matched_count if query_mode else None,
        "truncated": bool(query_mode and matched_count > limit),
        "filtered": query_mode,
        "columns": columns,
        "rows": rows[:limit],
    }


def _coerce_filter_value(value: str, field_type: pa.DataType) -> object:
    """把 URL 中的主键文本转换为 Parquet 字段类型。"""
    if pa.types.is_date(field_type):
        return date.fromisoformat(value)
    if pa.types.is_timestamp(field_type):
        return datetime.fromisoformat(value)
    if pa.types.is_integer(field_type):
        return int(value)
    if pa.types.is_floating(field_type):
        return float(value)
    if pa.types.is_boolean(field_type):
        normalized = value.strip().lower()
        if normalized not in {"true", "false", "1", "0"}:
            raise ValueError(f"布尔值必须是 true/false 或 1/0：{value}")
        return normalized in {"true", "1"}
    return value


def export_dataset_rows(
    session: Session,
    data_root: Path,
    dataset_id: str,
    primary_key_filters: dict[str, str],
    target: Path,
    file_format: str,
) -> dict:
    """把主键筛选出的完整结果写为临时 CSV 或 Parquet 文件。"""
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise KeyError(dataset_id)
    schema_version = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    primary_keys = set(schema_version.primary_key_fields)
    if not primary_key_filters:
        raise ValueError("下载前必须至少填写一个主键筛选条件")
    unknown_filters = set(primary_key_filters) - primary_keys
    if unknown_filters:
        raise ValueError(f"只能按主键字段筛选：{', '.join(sorted(primary_keys))}")
    if file_format not in {"csv", "parquet"}:
        raise ValueError("下载格式只支持 csv 或 parquet")

    partitions = list(
        session.scalars(
            select(CatalogPartition)
            .where(CatalogPartition.dataset_id == dataset_id)
            .order_by(CatalogPartition.partition_key)
        )
    )
    by_file: dict[str, set[str]] = {}
    for item in partitions:
        by_file.setdefault(item.file_path, set()).add(item.partition_key)
    if not by_file:
        raise ValueError("数据集尚无已发布数据")
    missing_files = sorted(path for path in by_file if not (data_root / path).is_file())
    if missing_files:
        raise MissingCatalogFilesError(missing_files)

    target.parent.mkdir(parents=True, exist_ok=True)
    partition_field = (dataset.storage_policy or {}).get("logical_partition_field")
    parquet_writer: pq.ParquetWriter | None = None
    csv_writer: pacsv.CSVWriter | None = None
    csv_sink: pa.OSFile | None = None
    row_count = 0
    files_read = 0
    failed = False
    try:
        for path in sorted(by_file):
            file_path = data_root / path
            arrow_schema = pq.read_schema(file_path)
            parquet_filters: list[tuple[str, str, object]] = []
            if partition_field:
                if partition_field not in arrow_schema.names:
                    raise ValueError(f"文件 {path} 缺少逻辑分区字段 {partition_field}")
                field_type = arrow_schema.field(partition_field).type
                wanted = sorted(by_file[path])
                filter_values = (
                    [date.fromisoformat(value) for value in wanted]
                    if pa.types.is_date(field_type)
                    else wanted
                )
                parquet_filters.append((partition_field, "in", filter_values))
            for field_name, raw_value in primary_key_filters.items():
                if field_name not in arrow_schema.names:
                    raise ValueError(f"文件 {path} 缺少主键字段 {field_name}")
                parquet_filters.append(
                    (
                        field_name,
                        "=",
                        _coerce_filter_value(raw_value, arrow_schema.field(field_name).type),
                    )
                )
            table = pq.read_table(file_path, filters=parquet_filters)
            files_read += 1
            row_count += table.num_rows
            if file_format == "parquet":
                if parquet_writer is None:
                    parquet_writer = pq.ParquetWriter(target, table.schema, compression="zstd")
                parquet_writer.write_table(table)
            else:
                if csv_writer is None:
                    csv_sink = pa.OSFile(str(target), "wb")
                    csv_writer = pacsv.CSVWriter(csv_sink, table.schema)
                csv_writer.write_table(table)
    except Exception:
        failed = True
        raise
    finally:
        if parquet_writer is not None:
            parquet_writer.close()
        if csv_writer is not None:
            csv_writer.close()
        if csv_sink is not None:
            csv_sink.close()
        if failed:
            target.unlink(missing_ok=True)

    return {
        "dataset_id": dataset_id,
        "row_count": row_count,
        "files_read": files_read,
        "path": target,
        "format": file_format,
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
    sources = sorted({item.file_path for item in partitions})
    if sources == [target_rel]:
        return {
            "dataset_id": dataset_id,
            "year": year,
            "status": "already_compacted",
            "partitions": len(partitions),
            "files": 1,
        }

    missing_sources = [path for path in sources if not (data_root / path).is_file()]
    if missing_sources:
        return {
            "dataset_id": dataset_id,
            "year": year,
            "status": "missing_files",
            "partitions": len(partitions),
            "missing_files": missing_sources,
        }

    partition_field = (dataset.storage_policy or {}).get("logical_partition_field")
    if not partition_field:
        raise ValueError("年度合并要求数据集配置 logical_partition_field")

    expected_keys = {item.partition_key for item in partitions}
    keys_by_source: dict[str, set[str]] = {}
    for item in partitions:
        keys_by_source.setdefault(item.file_path, set()).add(item.partition_key)

    tables: list[pa.Table] = []
    for path in sources:
        source = data_root / path
        table = pq.read_table(source)
        if partition_field not in table.column_names:
            raise ValueError(f"文件 {path} 缺少逻辑分区字段 {partition_field}")
        wanted = keys_by_source[path]
        values = table[partition_field].to_pylist()
        normalized = [
            value.isoformat() if hasattr(value, "isoformat") else str(value)
            for value in values
        ]
        filtered = table.filter([value in wanted for value in normalized])
        present = {value for value in normalized if value in wanted}
        if present != wanted:
            missing = sorted(wanted - present)
            raise ValueError(f"文件 {path} 缺少 Catalog 分区：{', '.join(missing)}")
        tables.append(filtered)

    merged = pa.concat_tables(tables)
    merged_values = merged[partition_field].to_pylist()
    merged_keys = {
        value.isoformat() if hasattr(value, "isoformat") else str(value)
        for value in merged_values
    }
    if merged_keys != expected_keys:
        missing = sorted(expected_keys - merged_keys)
        unexpected = sorted(merged_keys - expected_keys)
        raise ValueError(
            f"年度合并分区校验失败，缺少 {missing or '无'}，额外 {unexpected or '无'}"
        )

    target = data_root / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    pq.write_table(merged, temporary, compression="zstd")

    revisions = data_root / "revisions" / dataset_id / f"{year:04d}"
    revisions.mkdir(parents=True, exist_ok=True)
    previous_annual: Path | None = None
    if target.is_file():
        previous_annual = revisions / f"{year}.before-{uuid4().hex}.parquet"
        os.replace(target, previous_annual)
    try:
        os.replace(temporary, target)
    except Exception:
        if previous_annual is not None and previous_annual.is_file():
            os.replace(previous_annual, target)
        raise

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

    for path in sources:
        if path == target_rel:
            continue
        source = data_root / path
        if source.is_file():
            revision = revisions / source.name
            if revision.exists():
                revision = revisions / f"{source.stem}-{uuid4().hex}{source.suffix}"
            os.replace(source, revision)
            remove_empty_parent_directories(
                source,
                stop=data_root / "datasets" / dataset_id,
            )
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
