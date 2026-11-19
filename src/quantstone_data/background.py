from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor


class BackgroundJobExecutor:
    """单进程后台任务队列；同一时刻只执行一个任务。"""

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="background-job")
        self._futures: dict[str, Future[None]] = {}
        self._lock = threading.Lock()

    def submit(self, job_id: str, function: Callable[[], None]) -> None:
        with self._lock:
            if job_id in self._futures:
                raise RuntimeError("job has already been submitted")
            future = self._pool.submit(function)
            self._futures[job_id] = future
        future.add_done_callback(lambda completed: self._forget(job_id, completed))

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            future = self._futures.get(job_id)
        return bool(future and future.cancel())

    def _forget(self, job_id: str, completed: Future[None]) -> None:
        with self._lock:
            if self._futures.get(job_id) is completed:
                self._futures.pop(job_id, None)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=False)
