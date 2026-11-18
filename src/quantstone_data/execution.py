"""采集执行框架：限流等待、限流重试与统一的调用入口。"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any
from urllib.error import URLError

from .collection_protocol import RateLimitExceeded
from .collector_types import CollectorOperation, RateLimit, RetryPolicy
from .logging_config import log_event

# 以模块变量间接调用，测试可替换时钟与睡眠函数而不真正等待。
_clock: Callable[[], float] = time.monotonic
_sleep: Callable[[float], None] = time.sleep


class RateLimiter:
    """滑动窗口限流器。

    在任意 ``period_seconds`` 窗口内最多放行 ``calls`` 次调用；超出时等待
    最早一次调用离开窗口。多个线程共享同一实例时由锁串行化。
    """

    def __init__(self, limit: RateLimit, *, clock: Callable[[], float] | None = None) -> None:
        if limit.calls <= 0:
            raise ValueError("rate limit calls must be positive")
        if limit.period_seconds <= 0:
            raise ValueError("rate limit period must be positive")
        self._calls = limit.calls
        self._period = float(limit.period_seconds)
        self._clock = clock or _clock
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """占用一次调用额度，返回本次实际等待的秒数。"""
        waited = 0.0
        with self._lock:
            while True:
                now = self._clock()
                while self._timestamps and now - self._timestamps[0] >= self._period:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._calls:
                    self._timestamps.append(now)
                    return waited
                pause = self._period - (now - self._timestamps[0])
                if pause > 0:
                    _sleep(pause)
                    waited += pause


_limiters: dict[tuple[str, str], RateLimiter] = {}
_limiters_lock = threading.Lock()


def _limiter_for(collector_key: str, operation: CollectorOperation) -> RateLimiter | None:
    limit = operation.rate_limit
    if limit is None:
        return None
    scope = limit.scope or operation.key
    cache_key = (collector_key, scope)
    with _limiters_lock:
        limiter = _limiters.get(cache_key)
        if limiter is None:
            limiter = RateLimiter(limit)
            _limiters[cache_key] = limiter
        return limiter


def reset_rate_limiters() -> None:
    """清空进程内限流器，主要供测试和显式重置使用。"""
    with _limiters_lock:
        _limiters.clear()


def run_operation(
    collector_key: str,
    operation: CollectorOperation,
    call: Callable[[], Any],
    *,
    policy: RetryPolicy | None = None,
    job_id: str | None = None,
) -> Any:
    """按采集器的限流与重试策略执行一次操作调用。"""
    limiter = _limiter_for(collector_key, operation)
    settings = policy or operation.retry
    attempts = max(1, settings.attempts)
    delay = settings.delay_seconds

    for attempt in range(1, attempts + 1):
        if limiter is not None:
            waited = limiter.acquire()
            if waited > 0:
                log_event(
                    "rate_limit_wait",
                    collector=collector_key,
                    operation=operation.key,
                    scope=operation.rate_limit.scope or operation.key,
                    waited_seconds=round(waited, 2),
                    job_id=job_id,
                )
        try:
            return call()
        except (RateLimitExceeded, URLError) as error:
            if attempt >= attempts:
                raise
            pause = delay
            if isinstance(error, RateLimitExceeded):
                pause = max(pause, error.retry_after)
            pause = min(pause, settings.max_delay_seconds)
            log_event(
                "operation_retry_scheduled",
                level=30,
                collector=collector_key,
                operation=operation.key,
                attempt=attempt,
                max_attempts=attempts,
                pause_seconds=round(pause, 2),
                error=str(error),
                job_id=job_id,
            )
            _sleep(pause)
            delay = min(delay * 2, settings.max_delay_seconds)
    raise AssertionError("retry loop must return or raise")
