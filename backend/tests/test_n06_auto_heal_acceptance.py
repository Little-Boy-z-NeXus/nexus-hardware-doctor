import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "nexus_n06_auto_heal_acceptance.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("nexus_n06_auto_heal_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
n06 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = n06
SPEC.loader.exec_module(n06)


def snapshot(**changed):
    value = {
        "bus_voltage_v": 12.1,
        "current_ma": 26.0,
        "power_mw": 314.6,
        "pwm_percent": 0,
        "driver_enabled": False,
    }
    value.update(changed)
    return value


def test_physical_policy_is_conservative_and_default_deny() -> None:
    assert n06.safety_decision(snapshot(), pwm_percent=30, duration_ms=500)[0]
    for unsafe in (
        snapshot(bus_voltage_v=None),
        snapshot(bus_voltage_v=9.4),
        snapshot(bus_voltage_v=13.1),
        snapshot(current_ma=1501.0),
        snapshot(pwm_percent=1),
        snapshot(driver_enabled=True),
    ):
        assert n06.safety_decision(unsafe, pwm_percent=30, duration_ms=500)[0] is False
    assert n06.safety_decision(snapshot(), pwm_percent=31, duration_ms=500)[0] is False
    assert n06.safety_decision(snapshot(), pwm_percent=30, duration_ms=1001)[0] is False


def test_fault_and_recovery_require_measured_state_change() -> None:
    assert n06.fault_state_passed(snapshot(), idle_current_ma=26.0)
    assert not n06.fault_state_passed(
        snapshot(pwm_percent=30, driver_enabled=True, current_ma=95.0), idle_current_ma=26.0
    )
    assert n06.healed_state_passed(
        snapshot(pwm_percent=30, driver_enabled=True, current_ma=95.0),
        pwm_percent=30,
        idle_current_ma=26.0,
    )
    assert not n06.healed_state_passed(
        snapshot(pwm_percent=30, driver_enabled=True, current_ma=29.0),
        pwm_percent=30,
        idle_current_ma=26.0,
    )


def test_bounded_motor_test_must_end_safe() -> None:
    terminal = {
        "response_type": "result",
        "hardware_effect": True,
        "elapsed_ms": 505,
        "result": {"duration_ms": 500, "test_pwm_percent": 30, "stopped_after_test": True},
        "after": snapshot(),
    }
    assert n06.motor_test_passed(terminal, pwm_percent=30, duration_ms=500)
    terminal["after"] = snapshot(pwm_percent=30, driver_enabled=True)
    assert not n06.motor_test_passed(terminal, pwm_percent=30, duration_ms=500)
