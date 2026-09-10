"""Device-bound context reads and an isolated, nonphysical simulator adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from nexus_backend.policy import READ_TOOLS, SafetyPolicy
from nexus_backend.validation import validate_contract


class ToolExecutionError(RuntimeError):
    """A tool failed without establishing a successful physical action."""


class LocalToolAdapter:
    """Never imports a device transport and never writes to the persistent store."""

    def __init__(self, context: dict, *, mode: str = "mock",
                 policy: SafetyPolicy | None = None) -> None:
        if mode not in {"mock", "real"}:
            raise ValueError("mode must be mock or real")
        self.context = deepcopy(context)
        self.mode = mode
        self.policy = policy or SafetyPolicy()
        self._sample = deepcopy(context["telemetry"][-1]) if context.get("telemetry") else None

    def latest_sample(self) -> dict | None:
        return deepcopy(self._sample)

    def _snapshot(self, *, pwm: int, enabled: bool) -> dict:
        if self._sample is None:
            raise ToolExecutionError("No simulator telemetry is available")
        sample = deepcopy(self._sample)
        sample.update(sample_id=f"sim-{uuid4()}", sequence=sample["sequence"] + 1,
                      recorded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        measurements = sample["measurements"]
        measurements.update(pwm_percent=pwm, driver_enabled=enabled, motor_rpm=None)
        # Deliberately synthetic response for software verification, never a motor observation.
        current = self.context["hardware_model"]["safety_limits"]["max_current_ma"] * 0.25
        measurements["current_ma"] = round(current * pwm / 100, 2) if enabled else 0.0
        measurements["power_mw"] = round(
            measurements["bus_voltage_v"] * measurements["current_ma"], 2
        )
        validate_contract("telemetry", sample)
        self._sample = sample
        return deepcopy(sample)

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        decision = self.policy.evaluate(tool_name, arguments, context=self.context,
                                        sample=self._sample, mode=self.mode)
        if not decision.allowed:
            raise ToolExecutionError(decision.reason)
        if tool_name == "get_hardware_graph":
            return {"hardware_model": deepcopy(self.context["hardware_model"]),
                    "scope": "declared_configuration"}
        if tool_name == "get_telemetry":
            if self._sample is None:
                raise ToolExecutionError("No telemetry has been received")
            return {"sample": self.latest_sample(), "scope": "context_snapshot"}
        if tool_name in READ_TOOLS or self.mode != "mock":
            raise ToolExecutionError("No physical action adapter exists")
        before = self.latest_sample()
        measurements = before["measurements"]
        during = None
        if tool_name == "set_pwm":
            after = self._snapshot(pwm=arguments["pwm_percent"],
                                   enabled=measurements["driver_enabled"])
        elif tool_name == "enable_driver":
            after = self._snapshot(pwm=measurements["pwm_percent"], enabled=arguments["enabled"])
        elif tool_name == "run_motor_test":
            during = self._snapshot(pwm=arguments.get("pwm_percent", 20), enabled=True)
            after = self._snapshot(pwm=0, enabled=False)
        else:
            raise ToolExecutionError("Unknown tool")
        return {"sample": after, "before": before, "after": after, "during": during,
                "scope": "simulation", "physical_operation_verified": False,
                "simulated_duration_ms": arguments.get("duration_ms", 0)}
