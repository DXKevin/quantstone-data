from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_session
from .models import Dataset, DatasetCategory
from .schemas import DatasetCategoryCreate, DatasetCategoryRead, DatasetCategoryUpdate

router = APIRouter(prefix="/dataset-categories", tags=["dataset categories"])
SessionDep = Annotated[Session, Depends(get_session)]


def serialize_category(category: DatasetCategory, dataset_count: int) -> DatasetCategoryRead:
    return DatasetCategoryRead(
        id=category.id,
        name=category.name,
        description=category.description,
        dataset_count=dataset_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def category_count_query():
    return (
        select(DatasetCategory, func.count(Dataset.id))
        .outerjoin(Dataset, Dataset.category_id == DatasetCategory.id)
        .group_by(DatasetCategory.id)
    )


@router.get("", response_model=list[DatasetCategoryRead])
def list_dataset_categories(session: SessionDep) -> list[DatasetCategoryRead]:
    rows = session.execute(category_count_query().order_by(DatasetCategory.name)).all()
    return [serialize_category(category, count) for category, count in rows]


@router.post("", response_model=DatasetCategoryRead, status_code=status.HTTP_201_CREATED)
def create_dataset_category(
    payload: DatasetCategoryCreate, session: SessionDep
) -> DatasetCategoryRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="大类名称不能为空")
    category = DatasetCategory(
        id=str(uuid4()),
        name=name,
        description=payload.description.strip() if payload.description else None,
    )
    session.add(category)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="数据集大类名称已存在") from error
    session.refresh(category)
    return serialize_category(category, 0)


@router.patch("/{category_id}", response_model=DatasetCategoryRead)
def update_dataset_category(
    category_id: str, payload: DatasetCategoryUpdate, session: SessionDep
) -> DatasetCategoryRead:
    category = session.get(DatasetCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="数据集大类不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="大类名称不能为空")
    category.name = name
    category.description = payload.description.strip() if payload.description else None
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="数据集大类名称已存在") from error
    session.refresh(category)
    count = session.scalar(
        select(func.count(Dataset.id)).where(Dataset.category_id == category_id)
    )
    return serialize_category(category, count or 0)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_category(category_id: str, session: SessionDep) -> Response:
    category = session.get(DatasetCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="数据集大类不存在")
    dataset_count = session.scalar(
        select(func.count(Dataset.id)).where(Dataset.category_id == category_id)
    )
    if dataset_count:
        raise HTTPException(status_code=409, detail="请先移出该大类中的数据集")
    session.delete(category)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
