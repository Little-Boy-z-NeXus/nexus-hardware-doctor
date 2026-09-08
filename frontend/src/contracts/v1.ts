export const NEXUS_SCHEMA_VERSION = "1.0.0" as const;

export type SchemaVersion = typeof NEXUS_SCHEMA_VERSION;
export type ComponentType = "controller" | "sensor" | "driver" | "actuator" | "power";
export type PinMode = "input" | "output" | "i2c" | "pwm" | "power" | "ground";
export type SignalType = "i2c" | "digital" | "pwm" | "power" | "ground";

export interface HardwarePin {
  pin_id: string;
  label: string;
  mode: PinMode;
}

export interface HardwareComponent {
  component_id: string;
  component_type: ComponentType;
  model: string;
  pins: HardwarePin[];
  capabilities: string[];
}

export interface HardwareConnection {
  connection_id: string;
  from_component_id: string;
  from_pin: string;
  to_component_id: string;
  to_pin: string;
  signal_type: SignalType;
}

export interface SafetyLimits {
  max_pwm_percent: number;
  min_bus_voltage_v: number;
  max_current_ma: number;
  max_motor_test_duration_ms: number;
}

export interface HardwareModelV1 {
  schema_version: SchemaVersion;
  hardware_model_id: string;
  device_id: string;
  name: string;
  components: HardwareComponent[];
  connections: HardwareConnection[];
  safety_limits: SafetyLimits;
  updated_at: string;
}

export interface TelemetryMeasurements {
  bus_voltage_v: number;
  current_ma: number;
  power_mw: number;
  pwm_percent: number;
  driver_enabled: boolean;
  motor_rpm: number | null;
}

export interface TelemetryQuality {
  signal_quality_percent: number;
  source: "device" | "simulator" | "replay";
}

export interface TelemetrySampleV1 {
  schema_version: SchemaVersion;
  device_id: string;
  hardware_model_id: string;
  sample_id: string;
  recorded_at: string | null;
  sequence: number;
  measurements: TelemetryMeasurements;
  quality: TelemetryQuality;
}

export type ToolName =
  | "get_hardware_graph"
  | "get_telemetry"
  | "read_gpio"
  | "enable_driver"
  | "set_pwm"
  | "run_motor_test";

export interface ToolArguments {
  pin_id?: string;
  enabled?: boolean;
  pwm_percent?: number;
  duration_ms?: number;
}

export interface ToolCallV1 {
  schema_version: SchemaVersion;
  tool_call_id: string;
  trace_id: string;
  device_id: string;
  tool_name: ToolName;
  arguments: ToolArguments;
  requested_by: "user" | "nemotron" | "orchestrator";
  requested_at: string;
  requires_verification: boolean;
}

export type EventType =
  | "telemetry.received"
  | "diagnosis.proposed"
  | "action.approved"
  | "action.rejected"
  | "action.executed"
  | "verification.passed"
  | "verification.failed";

export interface LifecycleEventV1 {
  schema_version: SchemaVersion;
  event_id: string;
  trace_id: string;
  device_id: string;
  event_type: EventType;
  occurred_at: string;
  source: "firmware" | "backend" | "nemotron" | "orchestrator" | "safety_policy" | "tool" | "verify";
  severity: "info" | "warning" | "error";
  summary: string;
  payload: Record<string, unknown>;
  related_tool_call_id: string | null;
}
