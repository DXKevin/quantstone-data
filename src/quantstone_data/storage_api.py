from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_session
from .logging_config import log_event
from .models import Dataset
from .storage import MissingCatalogFilesError, compact_year, read_dataset_rows

router = APIRouter(prefix="/datasets", tags=["storage"])
SessionDep = Annotated[Session, Depends(get_session)]


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
        reserved = {"start", "end", "limit"}
        supplied = {
            key: value
            for key, value in request.query_params.items()
            if key not in reserved and value != ""
        }
        unknown = set(supplied) - set(schema.primary_key_fields)
        if unknown:
            raise ValueError(
                f"只能按主键字段筛选：{', '.join(schema.primary_key_fields)}"
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


@router.post("/{dataset_id}/compact")
def compact_dataset(
    dataset_id: str,
    request: Request,
    session: SessionDep,
    year: int,
) -> dict:
    try:
        result = compact_year(
            session,
            request.app.state.data_root,
            dataset_id,
            year,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="dataset not found") from error
    log_event(
        "dataset_compacted",
        dataset_id=dataset_id,
        year=year,
        status=result["status"],
        partitions=result.get("partitions", 0),
        rows=result.get("rows"),
        path=result.get("path"),
    )
    return result
