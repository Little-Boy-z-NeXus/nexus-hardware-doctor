import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from nexus_backend.contracts import HardwareModel, LifecycleEvent, TelemetrySample, ToolCall

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "nexus-contracts" / "v1" / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "contract"),
    [
        ("hardware-model.example.json", HardwareModel),
        ("telemetry.example.json", TelemetrySample),
        ("tool.example.json", ToolCall),
        ("event.example.json", LifecycleEvent),
    ],
)
def test_v1_fixture_matches_backend_model(
    fixture_name: str,
    contract: type[BaseModel],
) -> None:
    payload = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))

    parsed = contract.model_validate(payload)

    assert parsed.schema_version == "1.0.0"


def test_v1_telemetry_accepts_three_wheel_ps2_extension() -> None:
    payload = json.loads((FIXTURE_ROOT / "telemetry.example.json").read_text(encoding="utf-8"))
    payload["measurements"].update(
        {
            "total_current_ma": 810.5,
            "rpm_left": 101.0,
            "rpm_right": 99.5,
            "rpm_rear": 100.25,
            "rpm_delta": 1.5,
            "pwm_left_percent": 35,
            "pwm_right_percent": 34,
            "pwm_rear_percent": 35,
            "pid_state": "manual_ps2",
            "ps2_connected": True,
            "ps2_failsafe_active": False,
            "ps2_last_packet_age_ms": 8,
            "control_mode": "ps2_manual",
        }
    )

    parsed = TelemetrySample.model_validate(payload)

    assert parsed.measurements.rpm_rear == 100.25
    assert parsed.measurements.ps2_connected is True
    assert parsed.measurements.control_mode == "ps2_manual"
