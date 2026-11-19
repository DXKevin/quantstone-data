from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerOperation:
    key: str
    name: str
    description: str
    dataset_id: str
    filename: str


@dataclass(frozen=True)
class ScannerDefinition:
    key: str
    name: str
    description: str
    operations: tuple[ScannerOperation, ...]
