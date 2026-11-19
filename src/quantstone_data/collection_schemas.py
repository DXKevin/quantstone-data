from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CollectionOperation(StrEnum):
    INITIAL = "initial"
    INCREMENTAL = "incremental"
    REPAIR = "repair"
    REPLACE = "replace"


class InputMethod(StrEnum):
    COLLECTOR = "collector"
    FILE_IMPORT = "file_import"


class CollectionJobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    AWAITING_FILE = "awaiting_file"
    STAGED = "staged"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CollectionJobCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=255)
    operation: CollectionOperation
    input_method: InputMethod
    start_date: date | None = None
    end_date: date | None = None
    collector_key: str | None = Field(default=None, min_length=1, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_plan(self) -> "CollectionJobCreate":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.input_method is InputMethod.FILE_IMPORT and self.collector_key:
            raise ValueError("file import must not specify collector_key")
        return self


class CollectionJobRead(BaseModel):
    id: str
    dataset_id: str
    operation: CollectionOperation
    input_method: InputMethod
    status: CollectionJobStatus
    start_date: date | None
    end_date: date | None
    collector_key: str | None
    collector_operation: str | None
    parameters: dict[str, Any]
    retry_of_job_id: str | None
    source_file_name: str | None
    staged_path: str | None
    source_size_bytes: int | None
    source_sha256: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class CollectionReadiness(BaseModel):
    dataset_id: str
    initial_required: bool
