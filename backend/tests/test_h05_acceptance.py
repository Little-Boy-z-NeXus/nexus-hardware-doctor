from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_h05_acceptance.py"
SPEC = importlib.util.spec_from_file_location("nexus_h05_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def software_evidence() -> dict:
    return {"integration_evidence": {"covered": sorted(MODULE.REQUIRED_SOFTWARE_COVERAGE)}}


def physical_rows() -> list[dict]:
    safe = {"pwm_percent": 0, "driver_enabled": False}
    return [
        {"kind": "request", "value": {"request_id": "read-1", "command": "read_current"}},
        {"kind": "terminal", "value": {
            "request_id": "read-1", "response_type": "result", "command": "read_current"
        }},
        {"kind": "terminal", "value": {
            "request_id": "read-1", "response_type": "error",
            "error": {"code": "UNKNOWN_COMMAND"},
        }},
        {"kind": "final_stop", "value": {"after": safe}},
        {"kind": "result", "value": {"outcome": "PASS"}},
    ]


def test_accepts_software_and_physical_adapter_evidence() -> None:
    result = MODULE.assess_acceptance(software_evidence(), physical_rows(), evidence_sha256="a" * 64)
    assert result["outcome"] == "PASS"
    assert result["physical_adapter"]["fresh_current_reads"] == 1
    assert result["physical_adapter"]["final_driver_enabled"] is False


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda software, rows: software["integration_evidence"].update(covered=[]),
            "H05_SOFTWARE_COVERAGE_INCOMPLETE",
        ),
        (
            lambda software, rows: rows[-1]["value"].update(outcome="FAIL"),
            "H05_N03_PHYSICAL_RUN_NOT_PASSING",
        ),
        (
            lambda software, rows: rows.__setitem__(
                1, {"kind": "terminal", "value": {"request_id": "wrong", "command": "read_current"}}
            ),
            "H05_CORRELATION_FAILED",
        ),
        (
            lambda software, rows: rows.__setitem__(3, {
                "kind": "final_stop", "value": {"after": {"pwm_percent": 30, "driver_enabled": True}}
            }),
            "H05_FINAL_SAFE_STATE_MISSING",
        ),
    ],
)
def test_rejects_incomplete_acceptance(mutation, code: str) -> None:
    software = software_evidence()
    rows = physical_rows()
    mutation(software, rows)
    with pytest.raises(MODULE.AcceptanceError, match=code):
        MODULE.assess_acceptance(software, rows, evidence_sha256="a" * 64)
