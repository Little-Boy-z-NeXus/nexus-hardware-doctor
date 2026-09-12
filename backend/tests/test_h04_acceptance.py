from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_h04_acceptance.py"
SPEC = importlib.util.spec_from_file_location("nexus_h04_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_report() -> dict:
    ids = ["power", "pwm", "driver", "wiring", "normal"] * 2
    rows = [{"top2": [identifier], "scenario_passed": True} for identifier in ids]
    return {
        "planner_mode": "live_model_synthetic_inputs",
        "prompt_version": "diagnosis-v2",
        "model_configuration": {"model": "nvidia/Nemotron-3-Ultra-550b-a55b"},
        "cases": {
            "total": 10,
            "top2_correct": 10,
            "valid_evidence_and_safe_plan": 10,
            "cases": rows,
        },
    }


def test_accepts_complete_live_evidence() -> None:
    result = MODULE.assess_live_evidence(valid_report())
    assert result["outcome"] == "PASS"
    assert result["required_hypotheses"] == ["driver", "power", "pwm", "wiring"]
    assert result["new_model_call_made"] is False


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda report: report.update(planner_mode="deterministic_mock"), "H04_NOT_LIVE_MODEL"),
        (
            lambda report: report["cases"].update(top2_correct=7),
            "H04_ACCURACY_GATE_FAILED",
        ),
        (
            lambda report: report["cases"]["cases"].__setitem__(
                0, {"top2": ["normal"], "scenario_passed": False}
            ),
            "H04_SCENARIO_FAILED",
        ),
        (
            lambda report: report.update(raw_response="must never be stored"),
            "H04_PRIVATE_FIELD_PRESENT",
        ),
    ],
)
def test_rejects_unqualified_evidence(mutation, code: str) -> None:
    report = valid_report()
    mutation(report)
    with pytest.raises(MODULE.AcceptanceError, match=code):
        MODULE.assess_live_evidence(report)
