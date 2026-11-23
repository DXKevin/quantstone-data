import threading

from quantstone_data.background import BackgroundJobExecutor


def test_background_executor_runs_different_resources_concurrently_and_serializes_same_resource(
) -> None:
    executor = BackgroundJobExecutor()
    first_started = threading.Event()
    other_started = threading.Event()
    release = threading.Event()
    completed: list[str] = []

    def first() -> None:
        first_started.set()
        assert release.wait(timeout=2)
        completed.append("first")

    def other() -> None:
        other_started.set()
        completed.append("other")

    executor.submit("first", first, resource_key="dataset:a")
    assert first_started.wait(timeout=2)
    executor.submit("second", lambda: completed.append("second"), resource_key="dataset:a")
    executor.submit("other", other, resource_key="dataset:b")
    assert other_started.wait(timeout=2)
    assert executor.cancel("second") is True
    release.set()
    executor.shutdown()

    assert set(completed) == {"first", "other"}
