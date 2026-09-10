"""Default-deny safety and verification boundaries for the nonphysical sandbox."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from nexus_backend.context import build_context
from nexus_backend.mock_device import load_fixtures
from nexus_backend.policy import SafetyPolicy


@pytest.fixture
def context():
    model, sample = load_fixtures()
    sample["quality"]["source"] = "simulator"
    sample["recorded_at"] = datetime.now(UTC).isoformat()
    sample["measurements"].update(pwm_percent=0, driver_enabled=True, current_ma=0, motor_rpm=None)
    return build_context(model, [sample], "Motor does not move")


def evaluate(context, tool="set_pwm", arguments=None, mode="mock"):
    return SafetyPolicy().evaluate(tool, {"pwm_percent": 40} if arguments is None else arguments,
                                   context=context, sample=context["telemetry"][-1], mode=mode)


def test_read_tools_are_read_only_and_safe_changes_only_approve_simulation(context):
    assert evaluate(context, "get_telemetry", {}).classification == "read_only"
    decision = evaluate(context)
    assert decision.allowed and decision.classification == "auto_safe" and decision.simulated
    physical = evaluate(context, mode="real")
    assert not physical.allowed and physical.classification == "manual_required"


@pytest.mark.parametrize("tool,args", [
    ("reset_device", {}), ("read_gpio", {"pin_id": "gpio_25"}),
    ("get_telemetry", {"enabled": True}), ("enable_driver", {"enabled": 1}),
    ("set_pwm", {"pwm_percent": True}), ("set_pwm", {"pwm_percent": "40"}),
    ("set_pwm", {"pwm_percent": -1}), ("set_pwm", {"pwm_percent": 81}),
    ("set_pwm", {"pwm_percent": 40, "duration_ms": 100}),
    ("set_pwm", {}), ("run_motor_test", {"duration_ms": 99}),
    ("run_motor_test", {"duration_ms": 3001}),
    ("run_motor_test", {"duration_ms": 200, "pwm_percent": 81}),
    ("enable_driver", {"enabled": True, "pin_id": "gpio_25"}),
])
def test_unsafe_unknown_missing_or_cross_tool_arguments_are_denied(context, tool, args):
    assert not evaluate(context, tool, args).allowed


@pytest.mark.parametrize("field,value", [
    ("bus_voltage_v", 9.49), ("bus_voltage_v", 14.01),
    ("current_ma", 1501), ("current_ma", -1501), ("pwm_percent", 81),
])
def test_unsafe_before_measurements_block_actions(context, field, value):
    context["telemetry"][-1]["measurements"][field] = value
    assert not evaluate(context).allowed


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(recorded_at=None),
    lambda s: s.update(recorded_at=(datetime.now(UTC) - timedelta(seconds=6)).isoformat()),
    lambda s: s.update(recorded_at=(datetime.now(UTC) + timedelta(seconds=10)).isoformat()),
    lambda s: s.update(device_id="nexus-another"),
    lambda s: s.update(hardware_model_id="nexus-another"),
    lambda s: s["quality"].update(source="device"),
    lambda s: s["quality"].update(source="replay"),
])
def test_writes_require_fresh_matching_simulator_data(context, mutation):
    mutation(context["telemetry"][-1])
    assert not evaluate(context).allowed


def changed_samples(context):
    before = deepcopy(context["telemetry"][-1])
    after = deepcopy(before)
    after.update(sample_id="sim-after", sequence=before["sequence"] + 1,
                 recorded_at=datetime.now(UTC).isoformat())
    after["measurements"]["pwm_percent"] = 40
    return before, after


def test_verified_change_requires_fresh_distinct_ordered_before_and_after(context):
    before, after = changed_samples(context)
    verification = SafetyPolicy().verify("set_pwm", {"pwm_percent": 40}, context=context,
                                        before=before, after=after)
    assert verification["passed"] and verification["scope"] == "simulation"
    assert verification["physical_operation_verified"] is False


@pytest.mark.parametrize("case", ["missing_before", "missing_after", "same_sample", "no_change",
                                  "stale", "wrong_device", "reverse_order", "overcurrent"])
def test_acknowledgement_without_valid_observed_change_fails(context, case):
    before, after = changed_samples(context)
    if case == "missing_before":
        before = None
    elif case == "missing_after":
        after = None
    elif case == "same_sample":
        after["sample_id"] = before["sample_id"]
    elif case == "no_change":
        after["measurements"]["pwm_percent"] = 0
    elif case == "stale":
        after["recorded_at"] = (datetime.now(UTC) - timedelta(seconds=20)).isoformat()
    elif case == "wrong_device":
        after["device_id"] = "nexus-other"
    elif case == "reverse_order":
        after["sequence"] = before["sequence"]
    elif case == "overcurrent":
        after["measurements"]["current_ma"] = 1501
    verification = SafetyPolicy().verify("set_pwm", {"pwm_percent": 40}, context=context,
                                        before=before, after=after)
    assert verification["passed"] is False


def test_missing_before_sample_and_safety_metadata_fail_closed(context):
    decision = SafetyPolicy().evaluate("set_pwm", {"pwm_percent": 40}, context=context,
                                       sample=None, mode="mock")
    assert not decision.allowed
    context["hardware_model"]["safety_limits"] = {}
    assert not evaluate(context).allowed
