import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_hardware_baseline.py"
SPEC = importlib.util.spec_from_file_location("nexus_hardware_baseline", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
BASELINE_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASELINE_MODULE
SPEC.loader.exec_module(BASELINE_MODULE)

BaselineState = BASELINE_MODULE.BaselineState
measurement_failures = BASELINE_MODULE.measurement_failures
parse_telemetry = BASELINE_MODULE.parse_telemetry
update_low_current_streak = BASELINE_MODULE.update_low_current_streak
write_report = BASELINE_MODULE.write_report


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


def test_current_rise_monitor_tolerates_one_transient_zero_sample() -> None:
    streak, failure = update_low_current_streak(
        current_ma=0.0, idle_current_ma=26.0, previous_streak=0
    )
    assert streak == 1
    assert failure is None

    streak, failure = update_low_current_streak(
        current_ma=90.0, idle_current_ma=26.0, previous_streak=streak
    )
    assert streak == 0
    assert failure is None


def test_current_rise_monitor_rejects_five_consecutive_weak_samples() -> None:
    streak = 0
    failure = None
    for _ in range(5):
        streak, failure = update_low_current_streak(
            current_ma=26.0, idle_current_ma=26.0, previous_streak=streak
        )

    assert streak == 5
    assert failure is not None
    assert "5 mẫu liên tiếp" in failure


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


def test_report_accepts_real_duration_with_ina226_sample_rate_below_one_hz(
    tmp_path,
) -> None:
    sample = {
        "bus_voltage_v": 12.1,
        "current_ma": 90.0,
        "power_mw": 1089.0,
        "pwm_percent": 30,
        "driver_enabled": True,
        "motor_rpm": None,
    }
    state = BaselineState(
        idle_current_ma=26.2,
        samples=[sample] * 1785,
        start_monotonic=10.0,
        stop_monotonic=1810.42,
    )
    report_path = tmp_path / "report.md"

    passed = write_report(
        report_path,
        state,
        duration_seconds=1800,
        pwm_percent=30,
        evidence_path=tmp_path / "evidence.ndjson",
        physical_checks={"Không quá nhiệt": True, "Video đã lưu": True},
    )

    assert passed is True
    report = report_path.read_text(encoding="utf-8")
    assert "**PASS**" in report
    assert "99.2%" in report
