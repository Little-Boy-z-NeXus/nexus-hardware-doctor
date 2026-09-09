"""Default-deny action policy; physical writes have no enabled transport."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import pairwise

from nexus_backend.validation import ContractValidationError, validate_contract

READ_TOOLS = frozenset({"get_hardware_graph", "get_telemetry"})
WRITE_TOOLS = frozenset({"enable_driver", "set_pwm", "run_motor_test"})
TOOL_ARGUMENTS = {
    "get_hardware_graph": (frozenset(), frozenset()),
    "get_telemetry": (frozenset(), frozenset()),
    "read_gpio": (frozenset({"pin_id"}), frozenset({"pin_id"})),
    "enable_driver": (frozenset({"enabled"}), frozenset({"enabled"})),
    "set_pwm": (frozenset({"pwm_percent"}), frozenset({"pwm_percent"})),
    "run_motor_test": (frozenset({"duration_ms"}), frozenset({"duration_ms", "pwm_percent"})),
}


@dataclass(frozen=True)
class PolicyDecision:
    classification: str
    allowed: bool
    reason: str
    simulated: bool

    def to_dict(self) -> dict:
        return asdict(self)


def sample_fresh(sample: dict | None, *, now: datetime, max_age_seconds: float = 5) -> bool:
    """Require a known, recent UTC-compatible device time; future clocks fail closed."""
    if sample is None or not isinstance(sample.get("recorded_at"), str):
        return False
    try:
        recorded = datetime.fromisoformat(sample["recorded_at"].upper())
        age = (now - recorded).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return False
    return -1 <= age <= max_age_seconds


def valid_tool_arguments(tool_name: str, arguments: object) -> bool:
    """The frozen envelope permits cross-tool arguments; this policy does not."""
    if tool_name not in TOOL_ARGUMENTS or not isinstance(arguments, dict):
        return False
    required, permitted = TOOL_ARGUMENTS[tool_name]
    if not required <= arguments.keys() <= permitted:
        return False
    for field, value in arguments.items():
        if field == "enabled" and type(value) is not bool:
            return False
        if field in {"pwm_percent", "duration_ms"} and type(value) is not int:
            return False
        if field == "pwm_percent" and not 0 <= value <= 100:
            return False
        if field == "duration_ms" and not 100 <= value <= 10_000:
            return False
        if field == "pin_id" and (
            not isinstance(value, str) or not value.strip() or len(value) > 128
        ):
            return False
    return True


class SafetyPolicy:
    """Allow bounded sandbox changes only to fresh simulated telemetry.

    ``simulation_max_voltage_v`` is an explicit nonphysical sandbox rule. It is
    not a voltage rating inferred for any component. Frozen v1 lacks those
    ratings, and no option in this policy enables physical actuation.
    """

    def __init__(self, *, simulation_max_voltage_v: float = 14.0,
                 max_age_seconds: float = 5.0) -> None:
        for value in (simulation_max_voltage_v, max_age_seconds):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("Policy bounds must be finite positive numbers")
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Policy bounds must be finite positive numbers")
        self.simulation_max_voltage_v = simulation_max_voltage_v
        self.max_age_seconds = max_age_seconds

    def evaluate(self, tool_name: str, arguments: dict, *, context: dict,
                 sample: dict | None, mode: str, now: datetime | None = None) -> PolicyDecision:
        simulated = mode == "mock"

        def decision(classification: str, reason: str) -> PolicyDecision:
            return PolicyDecision(classification, classification in {"read_only", "auto_safe"},
                                  reason, simulated)

        if mode not in {"mock", "real"}:
            return decision("blocked", "Unknown execution mode")
        if not valid_tool_arguments(tool_name, arguments):
            return decision("blocked", "Unknown tool or arguments do not exactly match the tool")
        if tool_name in READ_TOOLS:
            return decision("read_only", "Read the device-bound context snapshot")
        if tool_name not in WRITE_TOOLS:
            return decision("blocked", "This tool has no implemented adapter")
        if mode == "real":
            return decision("manual_required", "Physical writes are unavailable: no device adapter "
                            "or verified electrical ratings exist")
        try:
            checked = validate_contract("telemetry", sample)
        except (ContractValidationError, TypeError):
            return decision("blocked", "A valid before-action telemetry sample is required")
        if (checked["device_id"] != context.get("device_id")
                or checked["hardware_model_id"] != context.get("hardware_model_id")):
            return decision("blocked", "Telemetry identity does not match this diagnosis")
        if checked["quality"]["source"] != "simulator":
            return decision("blocked", "Sandbox writes require explicitly simulated telemetry")
        if not sample_fresh(checked, now=now or datetime.now(UTC),
                            max_age_seconds=self.max_age_seconds):
            return decision("blocked", "Before-action telemetry is stale, future-dated or undated")
        limits = context.get("hardware_model", {}).get("safety_limits", {})
        required = {"max_pwm_percent", "min_bus_voltage_v", "max_current_ma",
                    "max_motor_test_duration_ms"}
        if not required <= limits.keys():
            return decision("blocked", "Declared safety limits are incomplete")
        measurements = checked["measurements"]
        if not limits["min_bus_voltage_v"] <= measurements["bus_voltage_v"] <= (
            self.simulation_max_voltage_v
        ):
            return decision("blocked", "Voltage is outside the explicit simulation limits")
        if abs(measurements["current_ma"]) > limits["max_current_ma"]:
            return decision("blocked", "Current exceeds the declared magnitude limit")
        if not 0 <= measurements["pwm_percent"] <= limits["max_pwm_percent"]:
            return decision("blocked", "Before-action PWM exceeds the declared limit")
        pwm = arguments.get("pwm_percent", 20 if tool_name == "run_motor_test" else 0)
        if not 0 <= pwm <= limits["max_pwm_percent"]:
            return decision("blocked", "Requested PWM exceeds the declared limit")
        if arguments.get("duration_ms", 100) > limits["max_motor_test_duration_ms"]:
            return decision("blocked", "Requested test duration exceeds the declared limit")
        return decision("auto_safe", "Approved only inside the isolated nonphysical simulator")

    def verify(self, tool_name: str, arguments: dict, *, context: dict, before: dict | None,
               after: dict | None, during: dict | None = None,
               now: datetime | None = None) -> dict:
        """A successful command acknowledgement is not verification."""
        checked_at = now or datetime.now(UTC)

        def result(passed: bool, reason: str) -> dict:
            return {"passed": passed, "reason": reason, "scope": "simulation",
                    "physical_operation_verified": False,
                    "before_sample_id": before.get("sample_id") if before else None,
                    "after_sample_id": after.get("sample_id") if after else None}

        if tool_name not in WRITE_TOOLS or before is None or after is None:
            return result(False, "Before and after telemetry are both required")
        samples = [before, after] + ([during] if during is not None else [])
        for sample in samples:
            try:
                validate_contract("telemetry", sample)
            except ContractValidationError:
                return result(False, "Verification received invalid telemetry")
            if (sample["device_id"] != context["device_id"]
                    or sample["hardware_model_id"] != context["hardware_model_id"]
                    or sample["quality"]["source"] != "simulator"):
                return result(False, "Verification source or device identity does not match")
            if not sample_fresh(sample, now=checked_at, max_age_seconds=self.max_age_seconds):
                return result(False, "Verification telemetry is stale, future-dated or undated")
            measured = sample["measurements"]
            limits = context["hardware_model"]["safety_limits"]
            if (not limits["min_bus_voltage_v"] <= measured["bus_voltage_v"] <= (
                    self.simulation_max_voltage_v)
                    or abs(measured["current_ma"]) > limits["max_current_ma"]
                    or not 0 <= measured["pwm_percent"] <= limits["max_pwm_percent"]):
                return result(False, "Verification measurements exceeded simulation limits")
        if len({sample["sample_id"] for sample in samples}) != len(samples):
            return result(False, "Verification requires distinct before and after samples")
        ordered = [before, during, after] if during is not None else [before, after]
        for first_sample, next_sample in pairwise(ordered):
            first_time = datetime.fromisoformat(
                first_sample["recorded_at"].upper()
            )
            next_time = datetime.fromisoformat(
                next_sample["recorded_at"].upper()
            )
            if (next_time < first_time
                    or next_sample["sequence"] <= first_sample["sequence"]):
                return result(False, "Simulation verification samples are out of order")
        first, last = before["measurements"], after["measurements"]
        if tool_name == "set_pwm":
            passed = (last["pwm_percent"] == arguments["pwm_percent"]
                      and first["pwm_percent"] != last["pwm_percent"])
        elif tool_name == "enable_driver":
            passed = (last["driver_enabled"] == arguments["enabled"]
                      and first["driver_enabled"] != last["driver_enabled"])
        else:
            passed = (during is not None and during["measurements"]["driver_enabled"] is True
                      and during["measurements"]["pwm_percent"] == arguments.get("pwm_percent", 20)
                      and during["measurements"]["pwm_percent"] > 0
                      and last["driver_enabled"] is False and last["pwm_percent"] == 0)
        return result(passed, "Observed the requested simulated state change" if passed else
                      "Telemetry does not demonstrate the requested state change")
