import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_backend.hardware import load_hardware_model
from nexus_backend.validation import ContractValidationError, json_pointer, validate_contract

FIXTURES = Path(__file__).resolve().parents[2] / "nexus-contracts/v1/fixtures"


def fixture(name="hardware-model"):
    return json.loads((FIXTURES / f"{name}.example.json").read_text())


def test_hardware_fixture_is_loaded_without_mutating_input():
    raw = fixture()
    model = load_hardware_model(raw)
    assert model == raw
    model["components"][0]["pins"].clear()
    assert raw["components"][0]["pins"]


@pytest.mark.parametrize("name", ["hardware-model", "telemetry", "tool", "event"])
def test_runtime_canonical_validator_accepts_all_fixtures(name):
    assert validate_contract(name, fixture(name)) == fixture(name)


@pytest.mark.parametrize("mutate,path", [
    (lambda m: m.update(schema_version="2.0.0"), "/schema_version"),
    (lambda m: m.pop("safety_limits"), ""),
    (lambda m: m.update(updated_at="not-a-date"), "/updated_at"),
    (lambda m: m["safety_limits"].update(max_pwm_percent="80"), "/safety_limits/max_pwm_percent"),
    (lambda m: m["safety_limits"].update(max_pwm_percent=True), "/safety_limits/max_pwm_percent"),
    (lambda m: m.update(secret="private-credential"), ""),
    (lambda m: m["components"][0].update(secret="private-credential"), "/components/0"),
    (lambda m: m.update(components=[]), "/components"),
    (lambda m: m.update(connections=[]), "/connections"),
])
def test_raw_contract_drift_is_rejected(mutate, path):
    model = fixture()
    mutate(model)
    with pytest.raises(ContractValidationError) as caught:
        load_hardware_model(model)
    assert any(error["path"] == path for error in caught.value.errors)
    assert "private-credential" not in str(caught.value.errors)


@pytest.mark.parametrize("mutate,path", [
    (
        lambda m: m["components"].append(deepcopy(m["components"][0])),
        "/components/{component_index}/component_id",
    ),
    (
        lambda m: m["components"][0]["pins"].append(deepcopy(m["components"][0]["pins"][0])),
        "/components/0/pins/{pin_index}/pin_id",
    ),
    (
        lambda m: m["connections"].append(deepcopy(m["connections"][0])),
        "/connections/{connection_index}/connection_id",
    ),
    (lambda m: m["connections"][0].update(from_component_id="missing"),
     "/connections/0/from_component_id"),
    (lambda m: m["connections"][0].update(to_component_id="missing"),
     "/connections/0/to_component_id"),
    (lambda m: m["connections"][0].update(from_pin="missing"), "/connections/0/from_pin"),
    (lambda m: m["connections"][0].update(to_pin="missing"), "/connections/0/to_pin"),
    (lambda m: m["components"][0].update(pins=[]), "/components/0/pins"),
    (lambda m: m["components"][0].update(capabilities=[]), "/components/0/capabilities"),
    (lambda m: m["components"][0].update(model="   "), "/components/0/model"),
    (lambda m: m["components"][0]["pins"][0].update(label=" "), "/components/0/pins/0/label"),
    (lambda m: m["components"][0].update(capabilities=[" "]), "/components/0/capabilities/0"),
])
def test_semantic_graph_errors_are_actionable(mutate, path):
    model = fixture()
    path = path.format(
        component_index=len(model["components"]),
        pin_index=len(model["components"][0]["pins"]),
        connection_index=len(model["connections"]),
    )
    mutate(model)
    with pytest.raises(ContractValidationError) as caught:
        load_hardware_model(model)
    assert any(error["path"] == path for error in caught.value.errors)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_are_rejected_even_inside_open_event_payload(value):
    event = fixture("event")
    event["payload"] = {"nested": [{"measurement": value}]}
    with pytest.raises(ContractValidationError) as caught:
        validate_contract("event", event)
    assert caught.value.errors[0] == {
        "path": "/payload/nested/0/measurement", "message": "Numbers must be finite",
    }


def test_overly_nested_json_is_rejected():
    event = fixture("event")
    nested = event["payload"]
    for _ in range(25):
        nested["child"] = {}
        nested = nested["child"]
    with pytest.raises(ContractValidationError):
        validate_contract("event", event)


def test_unknown_schema_name_cannot_select_an_arbitrary_file():
    with pytest.raises(ValueError, match="Unknown contract"):
        validate_contract("../../secret", {})


def test_hardware_context_limits_prevent_unbounded_topology():
    model = fixture()
    for i in range(65):
        component = deepcopy(model["components"][0])
        component["component_id"] = f"extra_{i}"
        model["components"].append(component)
    with pytest.raises(ContractValidationError) as caught:
        load_hardware_model(model)
    assert any(error["path"] == "/components" for error in caught.value.errors)


@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
def test_unpaired_surrogate_in_hardware_metadata_is_rejected_before_persistence(codepoint):
    model = fixture()
    model["name"] = "private-value" + chr(codepoint)
    with pytest.raises(ContractValidationError) as caught:
        load_hardware_model(model)
    assert caught.value.errors == [{
        "path": "/name", "message": "Strings must contain valid UTF-8 text",
    }]
    encoded_errors = json.dumps(caught.value.errors, ensure_ascii=False).encode("utf-8")
    assert b"private-value" not in encoded_errors


@pytest.mark.parametrize("codepoint", [0xD800, 0xDFFF])
def test_unpaired_surrogate_key_and_ancestor_are_rejected_with_serializable_errors(codepoint):
    event = fixture("event")
    event["payload"] = {"nested": {"private-key" + chr(codepoint): {"measurement": float("nan")}}}
    with pytest.raises(ContractValidationError) as caught:
        validate_contract("event", event)
    assert caught.value.errors == [{
        "path": "/payload/nested", "message": "JSON field names must contain valid UTF-8 text",
    }]
    encoded_errors = json.dumps(caught.value.errors, ensure_ascii=False).encode("utf-8")
    assert b"private-key" not in encoded_errors


def test_json_pointer_is_safe_even_if_passed_an_invalid_unicode_ancestor():
    pointer = json_pointer(["payload", "private-key\ud800", "child", 0])
    assert pointer == "/payload/[invalid-unicode-key]/child/0"
    assert "private-key" not in pointer
    pointer.encode("utf-8")


def test_valid_unicode_hardware_metadata_is_preserved():
    model = fixture()
    model["name"] = "Động cơ 🔧"
    assert load_hardware_model(model)["name"] == "Động cơ 🔧"
