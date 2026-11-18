from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CollectionContext:
    run_id: str
    staging_dir: Path
    token: str


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
