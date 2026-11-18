from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CollectorParameter:
    name: str
    data_type: str
    required: bool
    description: str


@dataclass(frozen=True)
class RateLimit:
    """供应商接口的调用频率上限，按滑动窗口计算。"""

    calls: int
    period_seconds: float
    scope: str = ""


@dataclass(frozen=True)
class RetryPolicy:
    """限流或网络错误后的重试策略。"""

    attempts: int = 3
    delay_seconds: float = 5.0
    max_delay_seconds: float = 65.0


@dataclass(frozen=True)
class CollectorOperation:
    key: str
    name: str
    description: str
    purpose: str
    parameters: tuple[CollectorParameter, ...]
    datasets: tuple[str, ...]
    function: Callable
    rate_limit: RateLimit | None = None
    retry: RetryPolicy = RetryPolicy()


@dataclass(frozen=True)
class CollectorDefinition:
    key: str
    name: str
    description: str
    operations: dict[str, CollectorOperation]
