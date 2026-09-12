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

    async def execute_call(self, call: dict) -> dict:
        """Preserve the canonical call ID when an adapter uses a device transport."""
        return await self.execute(call["tool_name"], call["arguments"])

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


class SerialToolAdapter(LocalToolAdapter):
    """Policy-checked reads over the existing serial owner, with durable evidence."""

    def __init__(self, context: dict, *, reads, history, policy: SafetyPolicy | None = None):
        super().__init__(context, mode="real", policy=policy)
        if history.device_id != context["device_id"]:
            raise ValueError("Serial history must match the diagnosis device")
        self.reads = reads
        self.history = history

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        # Standalone callers still use the full checked envelope path.
        return await self.execute_call({
            "schema_version": "1.0.0", "tool_call_id": str(uuid4()),
            "trace_id": str(uuid4()), "device_id": self.context["device_id"],
            "tool_name": tool_name, "arguments": arguments, "requested_by": "orchestrator",
            "requested_at": datetime.now(UTC).isoformat(), "requires_verification": False,
        })

    async def execute_call(self, call: dict) -> dict:
        checked = validate_contract("tool", call)
        name, arguments = checked["tool_name"], checked["arguments"]
        if checked["device_id"] != self.context["device_id"]:
            raise ToolExecutionError("Tool request belongs to another device")
        decision = self.policy.evaluate(name, arguments, context=self.context,
                                        sample=self.latest_sample(), mode="real")
        # Keep the transport boundary read-only even if a caller injects a permissive policy.
        if not decision.allowed or name not in READ_TOOLS:
            raise ToolExecutionError("Physical actions are unavailable through this adapter")
        if name == "get_hardware_graph":
            return {"hardware_model": deepcopy(self.context["hardware_model"]),
                    "scope": "declared_configuration"}
        record = await self.reads.read(
            device_id=self.context["device_id"],
            hardware_model_id=self.context["hardware_model_id"],
            tool_call_id=checked["tool_call_id"],
        )
        sample = self.history.persist(record)
        self._sample = deepcopy(sample)
        return {"sample": sample, "scope": "serial_read", "provenance": record["provenance"],
                "device_command": record["device_command"], "physical_operation_verified": False}
