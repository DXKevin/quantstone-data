from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import get_session
from .models import Dataset, DatasetField, DatasetSchemaVersion
from .schemas import (
    DatasetCreate,
    DatasetFieldRead,
    DatasetRead,
    DatasetSchemaRead,
    DatasetStatus,
    DatasetSummary,
    DatasetUpdate,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])
SessionDep = Annotated[Session, Depends(get_session)]


def dataset_query():
    return select(Dataset).options(
        selectinload(Dataset.schemas).selectinload(DatasetSchemaVersion.fields)
    )


def serialize_dataset(dataset: Dataset) -> DatasetRead:
    schema = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    return DatasetRead(
        id=dataset.id,
        provider=dataset.provider,
        region=dataset.region,
        instrument=dataset.instrument,
        dataset_name=dataset.dataset_name,
        market=dataset.market,
        display_name=dataset.display_name,
        description=dataset.description,
        status=DatasetStatus(dataset.status),
        current_schema_version=dataset.current_schema_version,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        schema=DatasetSchemaRead(
            version=schema.version,
            primary_key=schema.primary_key_fields,
            time_field=schema.time_field,
            created_at=schema.created_at,
            fields=[DatasetFieldRead.model_validate(field) for field in schema.fields],
        ),
    )


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, session: SessionDep) -> DatasetRead:
    if session.get(Dataset, payload.id):
        raise HTTPException(status_code=409, detail="dataset already exists")

    dataset = Dataset(
        id=payload.id,
        provider=payload.provider,
        region=payload.region,
        instrument=payload.instrument,
        dataset_name=payload.dataset_name,
        market=payload.market,
        display_name=payload.display_name,
        description=payload.description,
        status=DatasetStatus.DRAFT.value,
        current_schema_version=1,
    )
    schema = DatasetSchemaVersion(
        version=1,
        primary_key=",".join(payload.primary_key),
        time_field=payload.time_field,
    )
    schema.fields = [
        DatasetField(
            name=field.name,
            data_type=field.data_type,
            nullable=field.nullable,
            description=field.description,
            unit=field.unit,
            source_name=field.source_name,
            position=position,
        )
        for position, field in enumerate(payload.fields)
    ]
    dataset.schemas = [schema]
    session.add(dataset)
    session.commit()

    stored = session.scalar(dataset_query().where(Dataset.id == payload.id))
    assert stored is not None
    return serialize_dataset(stored)


@router.get("", response_model=list[DatasetSummary])
def list_datasets(session: SessionDep) -> list[Dataset]:
    return list(session.scalars(select(Dataset).order_by(Dataset.id)))


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: str, session: SessionDep) -> DatasetRead:
    dataset = session.scalar(dataset_query().where(Dataset.id == dataset_id))
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return serialize_dataset(dataset)


@router.put("/{dataset_id}", response_model=DatasetRead)
def update_draft_dataset(
    dataset_id: str, payload: DatasetUpdate, session: SessionDep
) -> DatasetRead:
    dataset = session.scalar(dataset_query().where(Dataset.id == dataset_id))
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != DatasetStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="only draft datasets can be edited")

    schema = next(
        item for item in dataset.schemas if item.version == dataset.current_schema_version
    )
    dataset.display_name = payload.display_name
    dataset.description = payload.description
    schema.primary_key = ",".join(payload.primary_key)
    schema.time_field = payload.time_field
    for field in list(schema.fields):
        session.delete(field)
    session.flush()
    schema.fields = [
        DatasetField(
            name=field.name,
            data_type=field.data_type,
            nullable=field.nullable,
            description=field.description,
            unit=field.unit,
            source_name=field.source_name,
            position=position,
        )
        for position, field in enumerate(payload.fields)
    ]
    session.commit()

    stored = session.scalar(dataset_query().where(Dataset.id == dataset_id))
    assert stored is not None
    return serialize_dataset(stored)


@router.post("/{dataset_id}/activate", response_model=DatasetRead)
def activate_dataset(dataset_id: str, session: SessionDep) -> DatasetRead:
    dataset = session.scalar(dataset_query().where(Dataset.id == dataset_id))
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status == DatasetStatus.DEPRECATED.value:
        raise HTTPException(status_code=409, detail="deprecated dataset cannot be activated")

    dataset.status = DatasetStatus.ACTIVE.value
    session.commit()
    session.refresh(dataset)
    return serialize_dataset(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft_dataset(dataset_id: str, session: SessionDep) -> Response:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if dataset.status != DatasetStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="only draft datasets can be deleted")
    session.delete(dataset)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
