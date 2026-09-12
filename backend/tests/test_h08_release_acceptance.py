from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_h08_release_acceptance.py"
SPEC = importlib.util.spec_from_file_location("nexus_h08_release_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def inputs() -> dict:
    return {
        "health_status": 200,
        "health": {"status": "ok"},
        "capabilities_status": 200,
        "capabilities": {
            "mock_available": True,
            "live_enabled": False,
            "live_configured": False,
            "physical_commands_enabled": False,
            "serial_reads_enabled": False,
        },
        "live_status": 503,
        "live_body": {"detail": "Live model access is not enabled and configured"},
        "lab_status": 200,
        "lab_html": "<p>Retry when ready.</p><script>node.textContent = message</script>",
        "register_status": 201,
        "telemetry_status": 201,
        "telemetry_body": {"inserted": True},
        "mock_status": 200,
        "mock_session": {
            "session_id": "session-1",
            "trace_id": "trace-1",
            "result": {
                "mode": "mock",
                "status": "needs_manual",
                "physical_commands_enabled": False,
                "events": [{"event_type": "diagnosis.proposed"}],
            },
        },
    }


def test_accepts_locked_down_package_outage_and_offline_fallback() -> None:
    result = MODULE.assess_runtime_inputs(**inputs())
    assert result["outcome"] == "PASS"
    assert result["model_outage"]["http_status"] == 503
    assert result["offline_fallback"]["audit_events"] == 1


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("enabled", "H08_CLEAN_RUNTIME_NOT_LOCKED_DOWN"),
        ("leak", "H08_CAPABILITY_SECRET_FIELD_EXPOSED"),
        ("outage", "H08_MODEL_OUTAGE_NOT_CONTROLLED"),
        ("retry", "H08_RETRY_UI_MISSING"),
        ("render", "H08_UNSAFE_MODEL_RENDERING"),
        ("database", "H08_DATABASE_NOT_CLEAN"),
        ("fallback", "H08_OFFLINE_FALLBACK_UNSAFE"),
    ],
)
def test_rejects_incomplete_release_acceptance(case: str, code: str) -> None:
    values = inputs()
    if case == "enabled":
        values["capabilities"]["live_enabled"] = True
    elif case == "leak":
        values["capabilities"]["api_key"] = "must-never-appear"
    elif case == "outage":
        values["live_status"] = 500
    elif case == "retry":
        values["lab_html"] = "<script>node.textContent = message</script>"
    elif case == "render":
        values["lab_html"] += "<script>node.innerHTML = message</script>"
    elif case == "database":
        values["register_status"] = 409
    else:
        values["mock_session"]["result"]["physical_commands_enabled"] = True
    with pytest.raises(MODULE.AcceptanceError, match=code):
        MODULE.assess_runtime_inputs(**values)
