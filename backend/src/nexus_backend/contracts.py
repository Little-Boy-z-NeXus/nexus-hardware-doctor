"""Typed mirrors of the frozen NeXus v1 JSON contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SchemaVersion = Literal["1.0.0"]


class StrictContract(BaseModel):
    """Reject drift at the stable contract envelope."""

    model_config = ConfigDict(extra="forbid")


class HardwarePin(StrictContract):
    pin_id: str
    label: str
    mode: Literal["input", "output", "i2c", "pwm", "power", "ground"]


class HardwareComponent(StrictContract):
    component_id: str
    component_type: Literal["controller", "sensor", "driver", "actuator", "power"]
    model: str
    pins: list[HardwarePin]
    capabilities: list[str]


class HardwareConnection(StrictContract):
    connection_id: str
    from_component_id: str
    from_pin: str
    to_component_id: str
    to_pin: str
    signal_type: Literal["i2c", "digital", "pwm", "power", "ground"]


class SafetyLimits(StrictContract):
    max_pwm_percent: int = Field(ge=0, le=100)
    min_bus_voltage_v: float = Field(ge=0)
    max_current_ma: float = Field(gt=0)
    max_motor_test_duration_ms: int = Field(ge=100, le=10_000)


class HardwareModel(StrictContract):
    schema_version: SchemaVersion
    hardware_model_id: str
    device_id: str
    name: str
    components: list[HardwareComponent]
    connections: list[HardwareConnection]
    safety_limits: SafetyLimits
    updated_at: datetime


class TelemetryMeasurements(StrictContract):
    bus_voltage_v: float = Field(ge=0)
    current_ma: float
    power_mw: float
    pwm_percent: int = Field(ge=0, le=100)
    driver_enabled: bool
    motor_rpm: float | None = Field(default=None, ge=0)


class TelemetryQuality(StrictContract):
    signal_quality_percent: float = Field(ge=0, le=100)
    source: Literal["device", "simulator", "replay"]


class TelemetrySample(StrictContract):
    schema_version: SchemaVersion
    device_id: str
    hardware_model_id: str
    sample_id: str
    recorded_at: datetime | None
    sequence: int = Field(ge=0)
    measurements: TelemetryMeasurements
    quality: TelemetryQuality


class ToolArguments(StrictContract):
    pin_id: str | None = None
    enabled: bool | None = None
    pwm_percent: int | None = Field(default=None, ge=0, le=100)
    duration_ms: int | None = Field(default=None, ge=100, le=10_000)


class ToolCall(StrictContract):
    schema_version: SchemaVersion
    tool_call_id: str
    trace_id: str
    device_id: str
    tool_name: Literal[
        "get_hardware_graph",
        "get_telemetry",
        "read_gpio",
        "enable_driver",
        "set_pwm",
        "run_motor_test",
    ]
    arguments: ToolArguments
    requested_by: Literal["user", "nemotron", "orchestrator"]
    requested_at: datetime
    requires_verification: bool


class LifecycleEvent(StrictContract):
    schema_version: SchemaVersion
    event_id: str
    trace_id: str
    device_id: str
    event_type: Literal[
        "telemetry.received",
        "diagnosis.proposed",
        "action.approved",
        "action.rejected",
        "action.executed",
        "verification.passed",
        "verification.failed",
    ]
    occurred_at: datetime
    source: Literal[
        "firmware",
        "backend",
        "nemotron",
        "orchestrator",
        "safety_policy",
        "tool",
        "verify",
    ]
    severity: Literal["info", "warning", "error"]
    summary: str = Field(min_length=1, max_length=280)
    payload: dict[str, object]
    related_tool_call_id: str | None
