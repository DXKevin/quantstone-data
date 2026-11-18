from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_session
from .logging_config import log_event
from .storage import compact_year, read_dataset_rows

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
    limit = max(1, min(limit, 1000))
    try:
        return read_dataset_rows(
            session,
            request.app.state.data_root,
            dataset_id,
            start=start,
            end=end,
            limit=limit,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="dataset not found") from error


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
