import json
from pathlib import Path

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
    bridge = SerialBridge(enabled=False)
    bridge.ingest_line(json.dumps(fixture_payload()), port="COM8")

    snapshot = bridge.snapshot()

    assert snapshot["connection"]["status"] == "connected"
    assert snapshot["connection"]["port"] == "COM8"
    assert snapshot["telemetry"]["hardware_model_id"] == EXPECTED_HARDWARE_MODEL_ID
    assert snapshot["telemetry"]["measurements"]["current_ma"] == 840.0
    assert snapshot["health"] == {"status": "healthy", "active_issue_count": 0}


def test_i2c_error_explains_ina219_wiring_repair() -> None:
    bridge = SerialBridge(enabled=False)
    bridge.ingest_line("[133521][E][Wire.cpp:499] requestFrom(): i2cWriteReadNonStop returned Error -1")

    snapshot = bridge.snapshot()
    finding = next(item for item in snapshot["diagnostics"] if item["code"] == "INA219_I2C_NO_ACK")

    assert finding["active"] is True
    assert finding["severity"] == "error"
    assert "GND" in finding["action"]
    assert snapshot["logs"][-1]["level"] == "error"


def test_non_finite_serial_packet_is_rejected_instead_of_reaching_ui() -> None:
    bridge = SerialBridge(enabled=False)
    payload = json.dumps(fixture_payload()).replace("840.0", "NaN")

    bridge.ingest_line(payload)

    assert bridge.snapshot()["telemetry"] is None
    assert "TELEMETRY_INVALID" in active_codes(bridge)


def test_zero_voltage_with_current_reports_reference_and_supply_problems() -> None:
    bridge = SerialBridge(enabled=False)
    payload = fixture_payload()
    payload["measurements"].update(bus_voltage_v=0.0, current_ma=34.0, power_mw=0.0)

    bridge.ingest_line(json.dumps(payload))

    assert {
        "INA219_REFERENCE_INVALID",
        "MOTOR_SUPPLY_NOT_DETECTED",
    }.issubset(active_codes(bridge))


def test_wrong_hardware_model_is_never_accepted_as_mvp_data() -> None:
    bridge = SerialBridge(enabled=False)
    payload = fixture_payload()
    payload["hardware_model_id"] = "nexus-other-board-v1"

    bridge.ingest_line(json.dumps(payload))

    assert bridge.snapshot()["telemetry"] is None
    assert "HARDWARE_MODEL_MISMATCH" in active_codes(bridge)
