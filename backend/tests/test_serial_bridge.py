import json
from pathlib import Path

import pytest

from nexus_backend.hardware_profile import load_hardware_profile, profile_fingerprint
from nexus_backend.serial_bridge import EXPECTED_HARDWARE_MODEL_ID, SerialBridge

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "nexus-contracts"
    / "v1"
    / "fixtures"
    / "telemetry.example.json"
)


def fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def active_codes(bridge: SerialBridge) -> set[str]:
    return {
        item["code"]
        for item in bridge.snapshot()["diagnostics"]
        if item["active"]
    }


def test_valid_mvp_telemetry_becomes_latest_snapshot() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line(json.dumps(fixture_payload()), port="COM8")

    snapshot = bridge.snapshot()

    assert snapshot["connection"]["status"] == "connected"
    assert snapshot["connection"]["port"] == "COM8"
    assert snapshot["telemetry"]["hardware_model_id"] == EXPECTED_HARDWARE_MODEL_ID
    assert snapshot["telemetry"]["measurements"]["current_ma"] == 840.0
    assert snapshot["health"] == {"status": "healthy", "active_issue_count": 0}
    assert snapshot["signal_health"]["monitor_ready"] is False
    assert snapshot["signal_health"]["i2c_verified"] is False


def test_signal_monitor_handshake_allows_latest_i2c_sample_to_be_verified() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line("[NEXUS][INFO][SIGNAL_MONITOR_READY] I2C and encoder watchdog active")

    bridge.ingest_line(json.dumps(fixture_payload()))

    status = bridge.snapshot()["signal_health"]
    assert status["monitor_ready"] is True
    assert status["i2c_verified"] is True
    assert status["last_i2c_verified_at"] is not None
    compatibility = bridge.snapshot()["compatibility"]
    assert compatibility["sensor_identity_verified"] is True
    assert compatibility["last_verified_at"] is not None


def test_locked_hardware_profile_is_verified_before_measurements() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    fingerprint = profile_fingerprint(load_hardware_profile())
    bridge.ingest_line(
        "[NEXUS][INFO][HARDWARE_PROFILE] profile_version=1.0.0 "
        "profile_id=nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1 "
        f"profile_sha256={fingerprint} "
        "hardware_model_id=nexus-s3-ina226-l298n-motor-rig-v1 "
        "controller=goouuu-esp32-s3-n16r8 sensor=ina226-r100 driver=l298n"
    )
    bridge.ingest_line("[NEXUS][INFO][INA226_READY] identity verified")

    compatibility = bridge.snapshot()["compatibility"]
    assert compatibility["firmware_profile_verified"] is True
    assert compatibility["sensor_identity_verified"] is True
    assert compatibility["firmware_profile_version"] == "1.0.0"
    assert compatibility["reported_profile_id"] == compatibility["expected_profile_id"]
    assert compatibility["reported_profile_sha256"] == compatibility["expected_profile_sha256"]
    assert active_codes(bridge) == set()


def test_backend_runtime_values_are_loaded_from_selected_profile(tmp_path: Path) -> None:
    profile = load_hardware_profile()
    profile["profile_id"] = "nexus-profile-custom-motor-rig-v1"
    profile["hardware_model_id"] = "nexus-custom-motor-rig-v1"
    profile["controller"]["model"] = "Custom test controller"
    profile["safety"]["max_current_ma"] = 500
    path = tmp_path / "nexus-profile-custom-motor-rig-v1.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    bridge = SerialBridge(
        enabled=False,
        persist_logs=False,
        hardware_profile_path=path,
    )
    payload = fixture_payload()
    payload["hardware_model_id"] = "nexus-custom-motor-rig-v1"

    bridge.ingest_line(json.dumps(payload))

    snapshot = bridge.snapshot()
    assert snapshot["hardware"]["profile_id"] == "nexus-profile-custom-motor-rig-v1"
    assert snapshot["hardware"]["controller"] == "Custom test controller"
    assert snapshot["hardware"]["limits"]["max_current_ma"] == 500
    assert "MOTOR_OVERCURRENT" in active_codes(bridge)


def test_wrong_firmware_profile_is_named_without_trusting_telemetry() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line(
        "[NEXUS][INFO][HARDWARE_PROFILE] profile_version=0.8.0 "
        "hardware_model_id=nexus-s3-ina219-l298n-motor-rig-v1 "
        "controller=esp32 sensor=ina219 driver=l298n"
    )

    compatibility = bridge.snapshot()["compatibility"]
    finding = next(
        item for item in bridge.snapshot()["diagnostics"]
        if item["code"] == "FIRMWARE_PROFILE_MISMATCH"
    )
    assert compatibility["firmware_profile_verified"] is False
    assert compatibility["reported_hardware_model_id"] == "nexus-s3-ina219-l298n-motor-rig-v1"
    assert "nạp firmware" in finding["action"].lower()


def test_ina219_like_identity_is_reported_as_wrong_physical_sensor() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line(
        "[NEXUS][ERROR][INA226_ID_MISMATCH] Expected manufacturer=0x5449 "
        "die=0x226x; received manufacturer=0x0000 die=0x0000"
    )

    snapshot = bridge.snapshot()
    finding = next(
        item for item in snapshot["diagnostics"] if item["code"] == "INA226_ID_MISMATCH"
    )
    assert snapshot["compatibility"]["sensor_identity_verified"] is False
    assert "không khớp" in finding["message"]
    assert "INA226 with R100 0.1 ohm shunt" in finding["message"]
    assert "INA226 with R100 0.1 ohm shunt" in finding["action"]
    assert "0x40" in finding["action"]


def test_i2c_error_explains_ina226_wiring_repair() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line("[133521][E][Wire.cpp:499] requestFrom(): i2cWriteReadNonStop returned Error -1")

    snapshot = bridge.snapshot()
    finding = next(item for item in snapshot["diagnostics"] if item["code"] == "INA226_I2C_FAILURE")

    assert finding["active"] is True
    assert finding["severity"] == "error"
    assert "GND" in finding["action"]
    assert snapshot["logs"][-1]["level"] == "error"


def test_non_finite_serial_packet_is_rejected_instead_of_reaching_ui() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    payload = json.dumps(fixture_payload()).replace("840.0", "NaN")

    bridge.ingest_line(payload)

    assert bridge.snapshot()["telemetry"] is None
    assert "TELEMETRY_INVALID" in active_codes(bridge)


def test_zero_voltage_with_current_reports_reference_and_supply_problems() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    payload = fixture_payload()
    payload["measurements"].update(bus_voltage_v=0.0, current_ma=34.0, power_mw=0.0)

    bridge.ingest_line(json.dumps(payload))

    assert {
        "INA226_REFERENCE_INVALID",
        "MOTOR_SUPPLY_NOT_DETECTED",
    }.issubset(active_codes(bridge))
    reference_finding = next(
        item
        for item in bridge.snapshot()["diagnostics"]
        if item["code"] == "INA226_REFERENCE_INVALID"
    )
    assert "VBUS" in reference_finding["action"]


def test_ina226_read_failure_never_becomes_telemetry() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)

    bridge.ingest_line(
        "[NEXUS][ERROR][INA226_I2C_READ_FAILED] "
        "bus_ok=false shunt_ok=true current_ok=true; sample discarded"
    )

    assert bridge.snapshot()["telemetry"] is None
    assert "INA226_I2C_FAILURE" in active_codes(bridge)


@pytest.mark.parametrize(
    ("line", "code", "expected_action"),
    [
        (
            "[NEXUS][ERROR][I2C_SDA_STUCK_LOW] SDA=GPIO1 is LOW",
            "I2C_SDA_STUCK_LOW",
            "GPIO1",
        ),
        (
            "[NEXUS][ERROR][I2C_SCL_STUCK_LOW] SCL=GPIO2 is LOW",
            "I2C_SCL_STUCK_LOW",
            "GPIO2",
        ),
        (
            "[NEXUS][ERROR][INA226_I2C_NO_ACK] address=0x40 ack_error=2",
            "INA226_I2C_NO_ACK",
            "SDA→GPIO1",
        ),
        (
            "[NEXUS][ERROR][INA226_SIGNAL_INCONSISTENT] current_register=35.4mA",
            "INA226_SIGNAL_INCONSISTENT",
            "0.1 Ω",
        ),
    ],
)
def test_i2c_signal_faults_name_the_wire_and_repair(
    line: str, code: str, expected_action: str,
) -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)

    bridge.ingest_line(line)

    finding = next(item for item in bridge.snapshot()["diagnostics"] if item["code"] == code)
    assert finding["active"] is True
    assert finding["severity"] == "error"
    assert finding["component_id"] == "ina226"
    assert finding["signal_id"] in {"i2c_sda", "i2c_scl", "i2c_bus"}
    assert expected_action in finding["action"]
    assert bridge.snapshot()["telemetry"] is None
    assert bridge.snapshot()["signal_health"]["i2c_verified"] is False


@pytest.mark.parametrize(
    ("code", "expected_action"),
    [
        ("ENCODER_CHANNEL_A_MISSING", "GPIO16"),
        ("ENCODER_CHANNEL_B_MISSING", "GPIO17"),
        ("ENCODER_SIGNAL_MISSING", "VCC, GND, A và B"),
        ("ENCODER_SIGNAL_INVALID", "L298N dual H-bridge module"),
    ],
)
def test_encoder_signal_faults_are_immediate_and_actionable(
    code: str, expected_action: str,
) -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)

    bridge.ingest_line(f"[NEXUS][ERROR][{code}] test evidence")

    finding = next(item for item in bridge.snapshot()["diagnostics"] if item["code"] == code)
    assert finding["active"] is True
    assert finding["component_id"] == "motor"
    assert finding["signal_id"] in {"encoder_a", "encoder_b", "encoder_bus"}
    assert expected_action in finding["action"]

    bridge.ingest_line("[NEXUS][INFO][ENCODER_SIGNAL_OK] A_edges=8 B_edges=8")
    assert code not in active_codes(bridge)
    status = bridge.snapshot()["signal_health"]
    assert status["encoder_a_verified"] is True
    assert status["encoder_b_verified"] is True
    assert status["last_encoder_verified_at"] is not None


def test_valid_telemetry_clears_i2c_signal_fault_but_not_encoder_history() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    bridge.ingest_line("[NEXUS][ERROR][I2C_SDA_STUCK_LOW] SDA=GPIO1 is LOW")
    bridge.ingest_line("[NEXUS][ERROR][ENCODER_CHANNEL_A_MISSING] B edges=4")

    bridge.ingest_line(json.dumps(fixture_payload()))

    assert "I2C_SDA_STUCK_LOW" not in active_codes(bridge)
    assert "ENCODER_CHANNEL_A_MISSING" in active_codes(bridge)


def test_measurement_findings_are_not_current_after_disconnect() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    payload = fixture_payload()
    payload["measurements"].update(bus_voltage_v=0.0, current_ma=26.0, power_mw=0.0)
    bridge.ingest_line(json.dumps(payload))

    bridge._set_connection("disconnected", None, "USB disconnected")

    assert "INA226_REFERENCE_INVALID" not in active_codes(bridge)
    assert "MOTOR_SUPPLY_NOT_DETECTED" not in active_codes(bridge)


def test_wrong_hardware_model_is_never_accepted_as_mvp_data() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    payload = fixture_payload()
    payload["hardware_model_id"] = "nexus-other-board-v1"

    bridge.ingest_line(json.dumps(payload))

    assert bridge.snapshot()["telemetry"] is None
    assert "HARDWARE_MODEL_MISMATCH" in active_codes(bridge)
    assert bridge.snapshot()["compatibility"]["reported_hardware_model_id"] == "nexus-other-board-v1"


def test_live_log_is_persisted_as_timestamped_ndjson(tmp_path: Path) -> None:
    bridge = SerialBridge(enabled=False, persist_logs=True, log_directory=tmp_path)

    bridge.ingest_line(json.dumps(fixture_payload()), port="COM8")
    log_file = Path(bridge.snapshot()["connection"]["log_file"])
    bridge.stop()

    assert log_file.parent == tmp_path
    assert log_file.name.startswith("hardware-live-")
    entry = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["source"] == "firmware"
    assert entry["level"] == "telemetry"
    assert json.loads(entry["message"])["device_id"] == "nexus-demo-esp32"


def test_device_command_response_is_logged_without_fake_telemetry_error() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    response = {
        "protocol_version": "1.0.0",
        "response_type": "ack",
        "request_id": "tool-01k4nexus001",
        "command": "read_voltage",
        "accepted": True,
        "duplicate": False,
        "writes_enabled": False,
    }

    bridge.ingest_line(json.dumps(response), port="COM8")

    snapshot = bridge.snapshot()
    assert snapshot["telemetry"] is None
    assert "TELEMETRY_INVALID" not in active_codes(bridge)
    assert snapshot["logs"][-1]["level"] == "info"
