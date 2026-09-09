"""The default app emits bounded summaries, not request content."""

import json
import subprocess
import sys

from nexus_backend.runtime import RunLimiter


def test_default_app_startup_emits_one_json_summary_without_sensitive_fields():
    program = '''
from fastapi.testclient import TestClient
from nexus_backend.app import create_app
from nexus_backend.runtime import log_run
for _ in range(2):
    with TestClient(create_app(":memory:")):
        log_run(trace_id="trace-123", mode="mock", status="diagnosed", steps=1, elapsed_ms=2)
'''
    completed = subprocess.run([sys.executable, "-c", program], capture_output=True,
                               text=True, timeout=15, check=True)
    records = [json.loads(line) for line in completed.stderr.splitlines()
               if line.startswith('{"event":')]
    assert len(records) == 2
    assert records[0] == {"event": "diagnosis.completed", "trace_id": "trace-123",
                          "mode": "mock", "status": "diagnosed", "steps": 1, "elapsed_ms": 2}


def test_concurrency_slot_is_released_without_consuming_admission_on_busy():
    limiter = RunLimiter(per_minute=2, concurrent=1)
    assert limiter.acquire() is None
    assert limiter.acquire() == "busy"
    limiter.release()
    assert limiter.acquire() is None
    limiter.release()
    assert limiter.acquire() == "rate_limited"
