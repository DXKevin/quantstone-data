from __future__ import annotations

import json
import threading
import time
from typing import Any
from urllib.request import Request, urlopen

from .logging_config import log_event

_provider_gates: dict[str, threading.BoundedSemaphore] = {}
_provider_gates_lock = threading.Lock()


def _gate_for(provider: str) -> threading.BoundedSemaphore:
    with _provider_gates_lock:
        gate = _provider_gates.get(provider)
        if gate is None:
            gate = threading.BoundedSemaphore(value=1)
            _provider_gates[provider] = gate
        return gate


def post_json(
    provider: str,
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 60,
) -> dict:
    """同一供应商同时只允许一个 HTTP 请求。"""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    gate = _gate_for(provider)
    started = time.monotonic()
    with gate:
        waited = time.monotonic() - started
        if waited >= 0.01:
            log_event(
                "provider_api_concurrency_wait",
                provider=provider,
                waited_seconds=round(waited, 3),
            )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.load(response)
    if not isinstance(body, dict):
        raise ValueError(f"{provider} API 返回的 JSON 不是对象")
    return body
