import pytest

from quantstone_data import execution
from quantstone_data.collection_protocol import RateLimitExceeded
from quantstone_data.collector_types import CollectorOperation, RateLimit, RetryPolicy
from quantstone_data.execution import RateLimiter, reset_rate_limiters, run_operation


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make_operation(**overrides: object) -> CollectorOperation:
    values: dict[str, object] = {
        "key": "demo_initial",
        "name": "demo",
        "description": "demo",
        "purpose": "initial",
        "parameters": (),
        "datasets": ("demo.cn.stock.daily",),
        "function": lambda: None,
    }
    values.update(overrides)
    return CollectorOperation(**values)  # type: ignore[arg-type]


def test_rate_limiter_waits_within_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    monkeypatch.setattr(execution, "_sleep", fake.sleep)
    limiter = RateLimiter(RateLimit(calls=2, period_seconds=10), clock=fake.clock)

    assert limiter.acquire() == 0
    assert limiter.acquire() == 0
    assert limiter.acquire() == pytest.approx(10)
    assert limiter.acquire() == 0


def test_operation_with_scope_shares_rate_limit_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeTime()
    monkeypatch.setattr(execution, "_clock", fake.clock)
    monkeypatch.setattr(execution, "_sleep", fake.sleep)
    reset_rate_limiters()

    limit = RateLimit(calls=1, period_seconds=30, scope="daily")
    first = make_operation(key="daily_initial", rate_limit=limit)
    second = make_operation(key="daily_incremental", rate_limit=limit)

    assert run_operation("demo", first, lambda: "first") == "first"
    assert run_operation("demo", second, lambda: "second") == "second"
    assert fake.now == pytest.approx(30)


def test_run_operation_retries_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    events: list[dict] = []
    monkeypatch.setattr(execution, "_sleep", pauses.append)
    monkeypatch.setattr(
        execution,
        "log_event",
        lambda event, **fields: events.append({"event": event, **fields}),
    )
    calls = {"count": 0}

    def call() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise RateLimitExceeded("每分钟最多 50 次", retry_after=3)
        return "ok"

    operation = make_operation(
        retry=RetryPolicy(attempts=3, delay_seconds=1, max_delay_seconds=10)
    )

    assert run_operation("demo", operation, call, job_id="job-123") == "ok"
    assert calls["count"] == 3
    assert pauses == [3, 3]
    assert [event["job_id"] for event in events] == ["job-123", "job-123"]


def test_run_operation_gives_up_after_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(execution, "_sleep", lambda seconds: None)
    operation = make_operation(
        retry=RetryPolicy(attempts=2, delay_seconds=1, max_delay_seconds=10)
    )

    def call() -> str:
        raise RateLimitExceeded("超出访问次数", retry_after=60)

    with pytest.raises(RateLimitExceeded):
        run_operation("demo", operation, call)


def test_run_operation_retries_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    calls = {"count": 0}
    monkeypatch.setattr(execution, "_sleep", pauses.append)

    def call() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("timed out")
        return "ok"

    operation = make_operation(
        retry=RetryPolicy(attempts=2, delay_seconds=2, max_delay_seconds=10)
    )

    assert run_operation("demo", operation, call) == "ok"
    assert calls["count"] == 2
    assert pauses == [2]


def test_run_operation_passes_through_other_errors() -> None:
    operation = make_operation()

    def call() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        run_operation("demo", operation, call)
