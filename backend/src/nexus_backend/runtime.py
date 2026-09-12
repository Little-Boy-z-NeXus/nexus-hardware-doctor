"""Bounded local model workload and payload-free structured run logging."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger("nexus.diagnosis")


def configure_logging() -> None:
    """Install one payload-free JSON sink independent of Uvicorn's logger hierarchy."""
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, "_nexus_json_sink", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._nexus_json_sink = True
        logger.addHandler(handler)


class RunLimiter:
    """One-process admission limits; public distributed deployment is a later concern."""

    def __init__(self, per_minute: int = 10, concurrent: int = 2):
        if type(per_minute) is not int or not 1 <= per_minute <= 120:
            raise ValueError("per_minute must be between 1 and 120")
        self.per_minute = per_minute
        self.concurrent = concurrent
        self._starts: deque[float] = deque()
        self._active = 0
        self._lock = Lock()

    def acquire(self) -> str | None:
        with self._lock:
            now = time.monotonic()
            while self._starts and self._starts[0] <= now - 60:
                self._starts.popleft()
            if len(self._starts) >= self.per_minute:
                return "rate_limited"
            if self._active >= self.concurrent:
                return "busy"
            self._starts.append(now)
            self._active += 1
            return None

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)


def log_run(*, trace_id: str, mode: str, status: str, steps: int, elapsed_ms: int,
            model_calls: int = 0, model: str | None = None) -> None:
    """Never log prompts, symptoms, API keys, telemetry, provider bodies or exceptions."""
    record = {
        "event": "diagnosis.completed", "trace_id": trace_id, "mode": mode,
        "status": status, "steps": steps, "elapsed_ms": elapsed_ms,
        "model_calls": model_calls,
    }
    if isinstance(model, str) and 1 <= len(model) <= 256:
        record["model"] = model
    logger.info(json.dumps(record, separators=(",", ":")))
