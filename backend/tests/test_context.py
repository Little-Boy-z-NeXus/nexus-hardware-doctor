import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_backend.context import build_context
from nexus_backend.validation import ContractValidationError

FIXTURES = Path(__file__).resolve().parents[2] / "nexus-contracts/v1/fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.example.json").read_text())


def sample(sequence, *, source="device", recorded_at=None):
    value = fixture("telemetry")
    value.update(sequence=sequence, sample_id=f"sample-{sequence}", recorded_at=recorded_at)
    value["quality"]["source"] = source
    return value


def test_context_isolates_device_and_model_and_bounds_history():
    model = fixture("hardware-model")
    history = [sample(i) for i in reversed(range(15))]
    foreign_device = sample(100)
    foreign_device.update(device_id="nexus-other-device")
    foreign_model = sample(101)
    foreign_model.update(hardware_model_id="nexus-other-model")
    history.extend([foreign_device, foreign_model])

    result = build_context(model, history, "Motor does not move", max_samples=3)

    assert [item["sequence"] for item in result["telemetry"]] == [2, 1, 0]
    assert all(item["device_id"] == model["device_id"] for item in result["telemetry"])
    assert all(item["hardware_model_id"] == model["hardware_model_id"]
               for item in result["telemetry"])
    assert result["sources"]["telemetry_order"] == "received"


def test_history_keeps_receipt_order_when_device_clock_moves_backwards():
    history = [
        sample(5, recorded_at="2026-09-08T12:00:00+02:00"),
        sample(3, recorded_at="2026-09-08t11:00:00z"),
        sample(8, recorded_at="2026-09-08T09:00:00Z"),
    ]
    result = build_context(fixture("hardware-model"), history, "Check current", 2)
    assert [item["sequence"] for item in result["telemetry"]] == [3, 8]
    assert result["sources"]["telemetry_order"] == "received"


def test_latest_received_sample_survives_sequence_reset_after_reboot():
    history = [sample(99), sample(0)]
    result = build_context(fixture("hardware-model"), history, "Check after reboot", 1)
    assert [item["sequence"] for item in result["telemetry"]] == [0]
    assert result["sources"]["telemetry_order"] == "received"
    assert any(entry["path"] == "/telemetry/recorded_at"
               for entry in result["missing_metadata"])


def test_context_labels_sources_and_only_advertises_implemented_read_operations():
    result = build_context(fixture("hardware-model"), [sample(1, source="simulator")], "Check")
    assert result["available_tools"] == ["get_hardware_graph", "get_telemetry"]
    assert result["sources"]["telemetry"] == ["simulator"]
    assert result["telemetry"][0]["quality"]["source"] == "simulator"
    assert result["sources"]["hardware_model"] == "declared_configuration"
    assert result["sources"]["symptom"] == "user"
    assert result["available_sensors"] == [{
        "component_id": "ina226", "model": "INA226 with R100 0.1 ohm shunt",
        "capabilities": ["measure_voltage", "measure_current"],
    }]
    missing = {entry["path"] for entry in result["missing_metadata"]}
    assert "/hardware_model/components/*/pins/*/electrical_ratings" in missing
    assert "/hardware_model/safety_limits/max_bus_voltage_v" in missing
    assert result["hardware_model"]["safety_limits"] == fixture("hardware-model")["safety_limits"]


def test_context_with_no_telemetry_makes_no_observation_claim():
    result = build_context(fixture("hardware-model"), [], "Observe")
    assert result["telemetry"] == []
    assert result["sources"]["telemetry"] == []


def test_context_is_an_isolated_copy_without_mutating_inputs():
    model = fixture("hardware-model")
    history = [sample(1)]
    original = deepcopy((model, history))
    result = build_context(model, history, "Check")
    result["hardware_model"]["safety_limits"]["max_pwm_percent"] = 0
    result["telemetry"][0]["measurements"]["current_ma"] = 0
    assert (model, history) == original


@pytest.mark.parametrize("field,value", [
    ("max_samples", 0), ("max_samples", 101), ("max_samples", True), ("max_samples", "10"),
    ("symptom", ""), ("symptom", "  "), ("symptom", "a" * 2001), ("symptom", None),
    ("telemetry", {}), ("telemetry", [None] * 1001),
])
def test_context_rejects_invalid_or_unbounded_inputs(field, value):
    arguments = {"hardware_model": fixture("hardware-model"), "telemetry": [], "symptom": "Check"}
    arguments[field] = value
    with pytest.raises(ContractValidationError):
        build_context(**arguments)


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(secret="must-not-appear"),
    lambda s: s["measurements"].update(current_ma="12"),
    lambda s: s["measurements"].update(current_ma=float("nan")),
    lambda s: s.update(schema_version="2.0.0"),
    lambda s: s.pop("quality"),
])
def test_context_validates_raw_samples_without_secret_or_unknown_passthrough(mutate):
    value = sample(1)
    mutate(value)
    with pytest.raises(ContractValidationError) as caught:
        build_context(fixture("hardware-model"), [value], "Check")
    assert "must-not-appear" not in str(caught.value.errors)


def test_context_default_returns_ten_recent_samples():
    result = build_context(fixture("hardware-model"), [sample(i) for i in range(20)], "Check")
    assert [s["sequence"] for s in result["telemetry"]] == list(range(10, 20))
