from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class RateLimitExceeded(RuntimeError):
    """供应商返回限流错误；由执行框架等待后重试。"""

    def __init__(self, message: str, retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class CollectionContext:
    run_id: str
    staging_dir: Path
    token: str
    current_artifact_path: Path | None = None
    data_root: Path | None = None


@dataclass(frozen=True)
class DatasetArtifact:
    dataset_id: str
    path: Path
    partition: dict[str, str]
    row_count: int


@dataclass(frozen=True)
class CollectionResult:
    outputs: dict[str, list[DatasetArtifact]]
    provenance: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str | None = None
