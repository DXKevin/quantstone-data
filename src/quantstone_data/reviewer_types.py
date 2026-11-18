from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import DatasetSchemaVersion


@dataclass(frozen=True)
class ReviewContext:
    artifact_path: Path
    schema: DatasetSchemaVersion
    expected_partition: date | None = None


@dataclass(frozen=True)
class ReviewReport:
    reviewer: str
    passed: bool
    row_count: int
    errors: tuple[dict, ...]

    def as_dict(self) -> dict:
        return {
            "reviewer": self.reviewer,
            "passed": self.passed,
            "row_count": self.row_count,
            "errors": list(self.errors),
            "error_count": len(self.errors),
        }


@dataclass(frozen=True)
class ReviewerDefinition:
    dataset_id: str
    function: Callable[[ReviewContext], ReviewReport]
