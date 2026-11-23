from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .collection_schemas import CollectionOperation


class ImportJobStatus(StrEnum):
    CREATED = "created"
    SCANNING = "scanning"
    REVIEW_READY = "review_ready"
    IMPORTING = "importing"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ImportJobCreate(BaseModel):
    dataset_id: str
    scanner_key: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=128)
    purpose: CollectionOperation = CollectionOperation.INITIAL
    source_root: str = Field(min_length=1, max_length=1024)
    transfer_mode: Literal["move", "copy"] = "move"
    start_date: date | None = None
    end_date: date | None = None


class ImportJobRead(BaseModel):
    id: str
    dataset_id: str
    scanner_key: str
    operation: str
    parameters: dict
    status: ImportJobStatus
    manifest_path: str | None
    summary: dict | None
    collection_job_id: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
