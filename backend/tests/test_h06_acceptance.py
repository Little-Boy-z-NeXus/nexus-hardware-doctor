from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_h06_acceptance.py"
SPEC = importlib.util.spec_from_file_location("nexus_h06_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def software_evidence() -> dict:
    return {"integration_evidence": {"covered": [
        "policy and adapter rejection of physical writes"
    ]}}


def physical_rows() -> list[dict]:
    rows = []
    for cycle in range(1, 6):
        rows.extend([
            {"event_type": "action.approved", "payload": {
                "cycle": cycle,
                "requested_action": {"set_pwm": 30, "motor_test_ms": 500},
            }},
            {"event_type": "action.executed", "payload": {"cycle": cycle}},
            {"event_type": "verification.measurement", "payload": {
                "cycle": cycle,
                "before": {"driver_enabled": False},
                "after": {"driver_enabled": True},
                "current_rise_ma": 60.0,
            }},
            {"event_type": "verification.passed", "payload": {
                "cycle": cycle,
                "healed_measurement": True,
                "bounded_motor_test": True,
                "final_safe_state": True,
                "after": {"pwm_percent": 0, "driver_enabled": False},
            }},
        ])
    rows.extend([
        {"event_type": "safety.final_reset", "payload": {}},
        {"event_type": "acceptance.completed", "payload": {
            "outcome": "PASS", "passed_cycles": 5, "required_cycles": 5, "failures": []
        }},
    ])
    return rows


def test_accepts_default_deny_and_five_verified_physical_cycles() -> None:
    result = MODULE.assess_acceptance(software_evidence(), physical_rows(), evidence_sha256="b" * 64)
    assert result["outcome"] == "PASS"
    assert result["physical_auto_heal"]["cycles_passed"] == 5
    assert result["physical_auto_heal"]["final_driver_enabled"] is False


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda software, rows: software["integration_evidence"].update(covered=[]),
            "H06_DEFAULT_DENY_EVIDENCE_MISSING",
        ),
        (
            lambda software, rows: rows.pop(0),
            "H06_CYCLE_TIMELINE_INCOMPLETE",
        ),
        (
            lambda software, rows: rows[2]["payload"].update(current_rise_ma=1),
            "H06_RECOVERY_MEASUREMENT_INVALID",
        ),
        (
            lambda software, rows: rows[3]["payload"]["after"].update(driver_enabled=True),
            "H06_POST_ACTION_VERIFICATION_FAILED",
        ),
    ],
)
def test_rejects_incomplete_safety_acceptance(mutation, code: str) -> None:
    software = software_evidence()
    rows = physical_rows()
    mutation(software, rows)
    with pytest.raises(MODULE.AcceptanceError, match=code):
        MODULE.assess_acceptance(software, rows, evidence_sha256="b" * 64)
