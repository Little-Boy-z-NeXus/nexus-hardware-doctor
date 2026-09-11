import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_backend.health_check import run_health_check

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "nexus-contracts/v1/fixtures/hardware-model.example.json"
CASES = Path(__file__).parent / "fixtures/health-check-cases.json"


def hardware_model() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def apply_mutation(model: dict, case: dict) -> None:
    if connection_id := case.get("remove_connection_id"):
        model["connections"] = [
            item for item in model["connections"] if item["connection_id"] != connection_id
        ]
    if change := case.get("set_pin_mode"):
        component = next(
            item for item in model["components"]
            if item["component_id"] == change["component_id"]
        )
        pin = next(item for item in component["pins"] if item["pin_id"] == change["pin_id"])
        pin["mode"] = change["mode"]
    if change := case.get("remove_component_field"):
        component = next(
            item for item in model["components"]
            if item["component_id"] == change["component_id"]
        )
        component.pop(change["field"])


def test_frozen_mvp_graph_passes_without_unverified_electrical_assumptions() -> None:
    model = hardware_model()
    report = run_health_check(model)
    assert report == {
        "health_check_version": "1.0.0",
        "status": "pass",
        "finding_count": 0,
        "findings": [],
    }
    assert model == hardware_model()


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["id"])
def test_rule_fixtures_return_actionable_error(case: dict) -> None:
    model = hardware_model()
    apply_mutation(model, case)

    report = run_health_check(model, case["profile"])

    finding = next(item for item in report["findings"] if item["rule_id"] == case["expected_rule"])
    assert report["status"] == "fail"
    assert finding["severity"] == "error"
    assert finding["evidence"]
    assert finding["remediation"]


def test_five_volt_gpio_evidence_contains_actual_and_allowed_voltage() -> None:
    case = cases()[0]
    report = run_health_check(hardware_model(), case["profile"])
    finding = report["findings"][0]
    assert finding["rule_id"] == "VOLTAGE_LIMIT_EXCEEDED"
    assert finding["evidence"]["observed_voltage_v"] == 5.0
    assert finding["evidence"]["target_max_voltage_v"] == 3.3


@pytest.mark.parametrize("profile", [
    {"unknown": []},
    {"pin_profiles": [{"component_id": "esp32", "pin_id": "gpio_16", "max_voltage_v": True}]},
    {"connection_readings": [{"connection_id": "wire", "voltage_v": float("nan")}]},
])
def test_invalid_rule_profile_fails_closed(profile: dict) -> None:
    with pytest.raises(ValueError):
        run_health_check(deepcopy(hardware_model()), profile)
