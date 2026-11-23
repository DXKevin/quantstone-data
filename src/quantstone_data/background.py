from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future


class BackgroundJobExecutor:
    """单进程多线程执行器；任务数不限，同一资源串行执行。"""

    def __init__(self) -> None:
        self._futures: dict[str, Future[None]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._resource_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self._accepting = True

    def submit(
        self,
        job_id: str,
        function: Callable[[], None],
        *,
        resource_key: str | None = None,
    ) -> None:
        with self._lock:
            if not self._accepting:
                raise RuntimeError("background executor is shutting down")
            if job_id in self._futures:
                raise RuntimeError("job has already been submitted")
            future: Future[None] = Future()
            resource_lock = (
                self._resource_locks.setdefault(resource_key, threading.Lock())
                if resource_key
                else None
            )
            thread = threading.Thread(
                target=self._run,
                args=(job_id, future, function, resource_lock),
                name=f"background-job-{job_id[:8]}",
                daemon=False,
            )
            self._futures[job_id] = future
            self._threads[job_id] = thread
            future.add_done_callback(lambda completed: self._forget(job_id, completed))
            thread.start()

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            future = self._futures.get(job_id)
        return bool(future and future.cancel())

    def _run(
        self,
        job_id: str,
        future: Future[None],
        function: Callable[[], None],
        resource_lock: threading.Lock | None,
    ) -> None:
        if resource_lock is not None:
            resource_lock.acquire()
        try:
            if not future.set_running_or_notify_cancel():
                return
            try:
                function()
            except BaseException as error:
                future.set_exception(error)
            else:
                future.set_result(None)
        finally:
            if resource_lock is not None:
                resource_lock.release()
            with self._lock:
                self._threads.pop(job_id, None)

    def _forget(self, job_id: str, completed: Future[None]) -> None:
        with self._lock:
            if self._futures.get(job_id) is completed:
                self._futures.pop(job_id, None)

    def shutdown(self) -> None:
        with self._lock:
            self._accepting = False
            threads = list(self._threads.values())
        for thread in threads:
            thread.join()
