from __future__ import annotations

import json
import logging
from collections import deque
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LOGGER_NAME = "quantstone_data"
SENSITIVE_MARKERS = ("token", "password", "secret", "cookie", "authorization")
STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)


def _redact(key: str, value: Any) -> Any:
    if any(marker in key.lower() for marker in SENSITIVE_MARKERS):
        return "***"
    if isinstance(value, dict):
        return {item_key: _redact(str(item_key), item) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(key, item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in STANDARD_RECORD_FIELDS and key not in payload:
                payload[key] = _redact(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class JobLogHandler(logging.Handler):
    def __init__(self, directory: Path) -> None:
        super().__init__()
        self.directory = directory

    def emit(self, record: logging.LogRecord) -> None:
        job_id = getattr(record, "job_id", None)
        if not job_id:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{job_id}.log"
        with target.open("a", encoding="utf-8") as output:
            output.write(self.format(record) + "\n")


def configure_logging(data_root: Path) -> logging.Logger:
    logs_root = data_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    application = RotatingFileHandler(
        logs_root / "application.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    application.setFormatter(formatter)
    logger.addHandler(application)

    jobs = JobLogHandler(logs_root / "collection")
    jobs.setFormatter(formatter)
    logger.addHandler(jobs)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def read_job_logs(data_root: Path, job_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    """读取任务最近的结构化日志；忽略并发写入造成的不完整行。"""
    target = data_root / "logs" / "collection" / f"{job_id}.log"
    if not target.is_file():
        return []
    entries: deque[dict[str, Any]] = deque(maxlen=limit)
    with target.open(encoding="utf-8") as source:
        for line in source:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
    return list(entries)


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    get_logger().log(level, event, extra={"event": event, **fields}, exc_info=exc_info)
