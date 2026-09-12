from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_h07_acceptance.py"
SPEC = importlib.util.spec_from_file_location("nexus_h07_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def model_report() -> dict:
    return {
        "evaluation": {
            "dataset": "challenge",
            "planner_mode": "live_model_synthetic_inputs",
            "cases": {
                "total": 12,
                "top2_correct": 12,
                "top2_accuracy": 1.0,
                "valid_evidence_and_safe_plan": 12,
            },
        },
        "simulated_paths": {
            name: {"passed": 5, "total": 5}
            for name in ("prevent", "manual", "auto_heal")
        },
    }


def software_fault_rows() -> list[dict]:
    rows = [
        {"kind": "fault_apply", "value": {"profile": profile}}
        for profile in ("pwm_zero", "pwm_frequency_low", "current_offset")
        for _ in range(5)
    ]
    return rows + [{"kind": "result", "value": {"outcome": "PASS", "checks": 15}}]


def manual_rows() -> list[dict]:
    rows = [{
        "kind": "fault_apply",
        "value": {"profile": "out2_open_manual", "manual_action_required": "true"},
    } for _ in range(5)]
    return rows + [{"kind": "result", "value": {"outcome": "PASS", "checks": 5}}]


def restored_rows() -> list[dict]:
    return [{"kind": "result", "value": {"outcome": "PASS", "checks": 1}}]


def auto_heal_rows() -> list[dict]:
    rows = [
        {"event_type": "verification.passed", "payload": {"cycle": cycle}}
        for cycle in range(1, 6)
    ]
    return rows + [{"event_type": "acceptance.completed", "payload": {
        "outcome": "PASS", "passed_cycles": 5, "required_cycles": 5
    }}]


def assess(report=None, software=None, manual=None, restored=None, auto=None):
    return MODULE.assess_acceptance(
        report or model_report(),
        software or software_fault_rows(),
        manual or manual_rows(),
        restored or restored_rows(),
        auto or auto_heal_rows(),
        digests={"source": "c" * 64},
    )


def test_accepts_model_score_golden_paths_and_physical_reproducibility() -> None:
    result = assess()
    assert result["h07_complete"] is True
    assert result["model_evaluation"]["top2_correct"] == 12
    assert result["physical_reproducibility"]["out2_open_manual"] == 5
    assert result["physical_reproducibility"]["auto_heal_verified"] == 5


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("accuracy", "H07_TOP2_GATE_FAILED"),
        ("golden", "H07_GOLDEN_PATH_GATE_FAILED"),
        ("fault", "H07_FAULT_REPRODUCTION_INCOMPLETE"),
        ("manual", "H07_MANUAL_GROUND_TRUTH_INVALID"),
        ("auto", "H07_AUTO_HEAL_REPRODUCTION_INCOMPLETE"),
    ],
)
def test_rejects_incomplete_evaluation(case: str, code: str) -> None:
    report = model_report()
    software = software_fault_rows()
    manual = manual_rows()
    auto = auto_heal_rows()
    if case == "accuracy":
        report["evaluation"]["cases"].update(top2_correct=7, top2_accuracy=7 / 12)
    elif case == "golden":
        report["simulated_paths"]["prevent"].update(passed=4)
    elif case == "fault":
        software.pop(0)
    elif case == "manual":
        manual[0]["value"]["manual_action_required"] = "false"
    else:
        auto.pop(0)
    with pytest.raises(MODULE.AcceptanceError, match=code):
        MODULE.assess_acceptance(
            report,
            software,
            manual,
            restored_rows(),
            auto,
            digests={"source": "c" * 64},
        )
