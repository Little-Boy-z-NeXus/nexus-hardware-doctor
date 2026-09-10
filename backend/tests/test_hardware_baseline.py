import json

from scripts.nexus_hardware_baseline import (
    BaselineState,
    measurement_failures,
    parse_telemetry,
    write_report,
)


def telemetry_line(**measurement_overrides: object) -> str:
    measurements = {
        "bus_voltage_v": 12.1,
        "current_ma": 220.0,
        "power_mw": 2662.0,
        "pwm_percent": 30,
        "driver_enabled": True,
        "motor_rpm": None,
    }
    measurements.update(measurement_overrides)
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "device_id": "nexus-demo-esp32",
            "hardware_model_id": "nexus-s3-ina226-l298n-motor-rig-v1",
            "sample_id": "sample-1",
            "recorded_at": None,
            "sequence": 1,
            "measurements": measurements,
            "quality": {"signal_quality_percent": 100, "source": "device"},
        }
    )


def test_parse_telemetry_accepts_expected_hardware_model() -> None:
    payload = parse_telemetry(telemetry_line())

    assert payload is not None
    assert payload["measurements"]["current_ma"] == 220.0


def test_measurement_failures_accepts_healthy_running_motor() -> None:
    payload = parse_telemetry(telemetry_line())
    assert payload is not None

    assert measurement_failures(
        payload["measurements"], requested_pwm=30, idle_current_ma=26.0
    ) == []


def test_measurement_failures_rejects_missing_motor_current_rise() -> None:
    payload = parse_telemetry(telemetry_line(current_ma=40.0))
    assert payload is not None

    failures = measurement_failures(
        payload["measurements"], requested_pwm=30, idle_current_ma=26.0
    )

    assert any("chưa chứng minh motor nhận tải" in item for item in failures)


def test_report_pass_requires_electrical_samples_and_all_physical_checks(tmp_path) -> None:
    sample = {
        "bus_voltage_v": 12.1,
        "current_ma": 220.0,
        "power_mw": 2662.0,
        "pwm_percent": 30,
        "driver_enabled": True,
        "motor_rpm": None,
    }
    state = BaselineState(
        idle_current_ma=26.0,
        samples=[sample] * 10,
        start_monotonic=10.0,
        stop_monotonic=20.0,
    )
    report_path = tmp_path / "report.md"

    passed = write_report(
        report_path,
        state,
        duration_seconds=10,
        pwm_percent=30,
        evidence_path=tmp_path / "evidence.ndjson",
        physical_checks={"Không quá nhiệt": True, "Video đã lưu": True},
    )

    assert passed is True
    assert "**PASS**" in report_path.read_text(encoding="utf-8")
