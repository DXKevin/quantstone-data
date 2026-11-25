from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_session
from .models import CatalogPartition, Dataset
from .storage import (
    MissingCatalogFilesError,
    export_dataset_rows,
    read_dataset_rows,
)

router = APIRouter(prefix="/datasets", tags=["storage"])
SessionDep = Annotated[Session, Depends(get_session)]


def _query_filters(request: Request, primary_keys: list[str], reserved: set[str]) -> dict[str, str]:
    supplied = {
        key: value
        for key, value in request.query_params.items()
        if key not in reserved and value != ""
    }
    if set(supplied) - set(primary_keys):
        raise ValueError(f"只能按主键字段筛选：{', '.join(primary_keys)}")
    return supplied


@router.get("/{dataset_id}/rows")
def read_rows(
    dataset_id: str,
    request: Request,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    limit: int = 50,
) -> dict:
    try:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        schema = next(
            item for item in dataset.schemas if item.version == dataset.current_schema_version
        )
        supplied = _query_filters(
            request,
            schema.primary_key_fields,
            {"start", "end", "limit"},
        )
        # 无筛选只是预览；提供任意主键条件才进入查询模式。
        query_mode = bool(supplied) or start is not None or end is not None
        effective_limit = max(1, min(limit, 100_000)) if query_mode else 20
        return read_dataset_rows(
            session,
            request.app.state.data_root,
            dataset_id,
            start=start,
            end=end,
            limit=effective_limit,
            primary_key_filters=supplied,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="dataset not found") from error
    except MissingCatalogFilesError as error:
        raise HTTPException(
            status_code=409,
            detail=f"Catalog 文件缺失，读取已中止：{'；'.join(error.paths)}",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{dataset_id}/download")
def download_rows(
    dataset_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    format: str = "parquet",
    start: date | None = None,
    end: date | None = None,
) -> FileResponse:
    target: Path | None = None
    try:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        schema = next(
            item for item in dataset.schemas if item.version == dataset.current_schema_version
        )
        supplied = _query_filters(
            request, schema.primary_key_fields, {"format", "start", "end"}
        )
        suffix = "csv" if format == "csv" else "parquet"
        target = (
            request.app.state.data_root
            / "tmp"
            / "exports"
            / f"{dataset_id}-{uuid4().hex}.{suffix}"
        )
        result = export_dataset_rows(
            session,
            request.app.state.data_root,
            dataset_id,
            supplied,
            target,
            format,
            start=start,
            end=end,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="dataset not found") from error
    except MissingCatalogFilesError as error:
        raise HTTPException(
            status_code=409,
            detail=f"Catalog 文件缺失，下载已中止：{'；'.join(error.paths)}",
        ) from error
    except ValueError as error:
        if target is not None:
            target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{dataset_id}-{timestamp}.{suffix}"
    media_type = "text/csv; charset=utf-8" if format == "csv" else "application/vnd.apache.parquet"
    background_tasks.add_task(target.unlink, missing_ok=True)
    return FileResponse(
        target,
        media_type=media_type,
        filename=filename,
        headers={"X-Row-Count": str(result["row_count"])},
        background=background_tasks,
    )


@router.get("/{dataset_id}/coverage")
def dataset_coverage(dataset_id: str, request: Request, session: SessionDep) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    count, rows, size_bytes, first, last = session.execute(
        select(
            func.count(CatalogPartition.id),
            func.coalesce(func.sum(CatalogPartition.row_count), 0),
            func.coalesce(func.sum(CatalogPartition.size_bytes), 0),
            func.min(CatalogPartition.partition_key),
            func.max(CatalogPartition.partition_key),
        ).where(CatalogPartition.dataset_id == dataset_id)
    ).one()
    missing_files = sum(
        1
        for path in session.scalars(
            select(CatalogPartition.file_path)
            .where(CatalogPartition.dataset_id == dataset_id)
            .distinct()
        )
        if not (request.app.state.data_root / path).is_file()
    )
    return {
        "dataset_id": dataset_id,
        "partition_count": count,
        "row_count": rows,
        "size_bytes": size_bytes,
        "first_partition": first,
        "last_partition": last,
        "missing_files": missing_files,
    }
