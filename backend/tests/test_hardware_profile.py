import json
from pathlib import Path

import pytest

from nexus_backend.hardware_profile import (
    HardwareProfileError,
    default_profile_path,
    load_hardware_profile,
    profile_summary,
    profile_to_hardware_model,
)


def test_default_hardware_profile_is_machine_readable_and_valid() -> None:
    profile = load_hardware_profile()

    assert profile["profile_id"] == (
        "nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1"
    )
    assert profile["controller"]["family"] == "esp32"
    assert profile["firmware"]["pins"]["i2c_sda"] == 1
    assert profile["firmware"]["sensor"]["identity"]["manufacturer_id"] == "0x5449"
    assert "signal.i2c.health" in profile["capabilities"]


def test_profile_summary_contains_no_hardcoded_runtime_values() -> None:
    summary = profile_summary(load_hardware_profile())

    assert summary["controller"] == "GOOUUU Tech ESP32-S3-N16R8"
    assert summary["sensor"].startswith("INA226")
    assert summary["limits"]["max_current_ma"] == 1500


def test_unknown_connection_pin_is_rejected(tmp_path: Path) -> None:
    profile = load_hardware_profile()
    profile["connections"][0]["to"]["pin_id"] = "missing_pin"
    path = tmp_path / "nexus-invalid-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(HardwareProfileError, match="unknown pin"):
        load_hardware_profile(path)


def test_invalid_safety_range_is_rejected(tmp_path: Path) -> None:
    profile = load_hardware_profile()
    profile["safety"]["min_bus_voltage_v"] = 14
    path = tmp_path / "nexus-invalid-safety-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(HardwareProfileError, match="min_bus_voltage_v"):
        load_hardware_profile(path)


def test_unsafe_signal_voltage_is_rejected(tmp_path: Path) -> None:
    profile = load_hardware_profile()
    controller = next(
        item for item in profile["components"] if item["component_id"] == "esp32"
    )
    encoder_a = next(pin for pin in controller["pins"] if pin["pin_id"] == "gpio_16")
    encoder_a["max_voltage_v"] = 1.8
    path = tmp_path / "nexus-unsafe-signal-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(HardwareProfileError, match="electrically unsafe"):
        load_hardware_profile(path)


def test_default_path_uses_nexus_prefix() -> None:
    assert default_profile_path().name.startswith("nexus-")


def test_diagnosis_model_is_generated_from_the_active_profile() -> None:
    profile = load_hardware_profile()
    model = profile_to_hardware_model(profile, "nexus-runtime-device")

    assert model["device_id"] == "nexus-runtime-device"
    assert model["hardware_model_id"] == profile["hardware_model_id"]
    assert [item["model"] for item in model["components"]] == [
        item["model"] for item in profile["components"]
    ]
    assert len(model["connections"]) == len(profile["connections"])
    assert model["safety_limits"]["max_current_ma"] == profile["safety"][
        "max_current_ma"
    ]
