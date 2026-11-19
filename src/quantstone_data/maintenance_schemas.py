from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class MaintenanceJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MaintenanceJobRead(BaseModel):
    id: str
    dataset_id: str
    operation: str
    parameters: dict[str, Any]
    status: MaintenanceJobStatus
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime
