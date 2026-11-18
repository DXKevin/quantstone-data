from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CollectorParameter:
    name: str
    data_type: str
    required: bool
    description: str


@dataclass(frozen=True)
class CollectorOperation:
    key: str
    name: str
    description: str
    purpose: str
    parameters: tuple[CollectorParameter, ...]
    datasets: tuple[str, ...]
    function: Callable


@dataclass(frozen=True)
class CollectorDefinition:
    key: str
    name: str
    description: str
    operations: dict[str, CollectorOperation]
