import threading

from quantstone_data.background import BackgroundJobExecutor


def test_background_executor_runs_one_job_at_a_time_and_cancels_queued_job() -> None:
    executor = BackgroundJobExecutor()
    started = threading.Event()
    release = threading.Event()
    completed: list[str] = []

    def first() -> None:
        started.set()
        assert release.wait(timeout=2)
        completed.append("first")

    executor.submit("first", first)
    assert started.wait(timeout=2)
    executor.submit("second", lambda: completed.append("second"))
    assert executor.cancel("second") is True
    release.set()
    executor.shutdown()

    assert completed == ["first"]
