import { env } from "../config/env";
import type { LifecycleEventV1, TelemetrySampleV1, ToolName } from "../contracts/v1";

export type DiagnosisMode = "mock" | "live";

export interface DiagnosisCapabilities {
  mock_available: boolean;
  live_enabled: boolean;
  live_configured: boolean;
  physical_commands_enabled: boolean;
  serial_reads_enabled: boolean;
  serial_device_id: string | null;
  serial_history_status?: string;
}

export interface DeviceSummary {
  device_id: string;
  hardware_model_id: string;
  display_name: string;
  source: "device" | "simulator" | "replay";
  registered_at: string;
}

export interface DiagnosisHypothesis {
  id: string;
  label: string;
  confidence: number;
  evidence_ids: string[];
}

export interface DiagnosisPlan {
  confidence: number;
  user_message: string;
  stop_condition: "continue" | "diagnosed" | "needs_manual";
  hypotheses: DiagnosisHypothesis[];
  next_tool?: { tool_name: ToolName; arguments: Record<string, unknown> } | null;
}

export interface DiagnosisObservation {
  evidence_id: string;
  tool_name: ToolName;
  status: "succeeded" | "failed" | "blocked";
  recorded_at?: string;
  error?: string;
  data?: {
    scope?: string;
    sample?: TelemetrySampleV1;
    before?: TelemetrySampleV1;
    after?: TelemetrySampleV1;
    during?: TelemetrySampleV1;
    physical_operation_verified?: boolean;
  };
  verification?: {
    passed: boolean;
    reason: string;
    scope: string;
    physical_operation_verified: boolean;
    before_sample_id?: string | null;
    after_sample_id?: string | null;
  };
}

export interface DiagnosisResult {
  status: string;
  summary: string;
  mode: DiagnosisMode;
  source?: string;
  plan: DiagnosisPlan | null;
  observations: DiagnosisObservation[];
  events: LifecycleEventV1[];
  steps?: number;
  trace_id?: string;
  model_runtime?: {
    provider: string;
    calls: Array<{
      response_model?: string;
      requested_model?: string;
      elapsed_ms?: number;
      usage?: Record<string, number>;
    }>;
  };
  physical_commands_enabled: boolean;
  verified_simulated_changes?: number;
  physical_operation_verified?: boolean;
  limitations?: string[];
}

export interface DiagnosisSession {
  session_id: string;
  device_id?: string;
  status?: string;
  created_at?: string;
  completed_at?: string | null;
  result: DiagnosisResult;
}

export class NexusApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = "NEXUS_API_ERROR",
  ) {
    super(message);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCapabilities(value: unknown): value is DiagnosisCapabilities {
  return isRecord(value)
    && typeof value.mock_available === "boolean"
    && typeof value.live_enabled === "boolean"
    && typeof value.live_configured === "boolean"
    && typeof value.physical_commands_enabled === "boolean"
    && typeof value.serial_reads_enabled === "boolean"
    && (typeof value.serial_device_id === "string" || value.serial_device_id === null);
}

function isDevice(value: unknown): value is DeviceSummary {
  return isRecord(value)
    && typeof value.device_id === "string"
    && typeof value.hardware_model_id === "string"
    && typeof value.display_name === "string"
    && ["device", "simulator", "replay"].includes(String(value.source));
}

function isSession(value: unknown): value is DiagnosisSession {
  return isRecord(value)
    && typeof value.session_id === "string"
    && isRecord(value.result)
    && typeof value.result.status === "string"
    && Array.isArray(value.result.observations)
    && Array.isArray(value.result.events);
}

async function requestJson<T>(
  path: string,
  guard: (value: unknown) => value is T,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const payload = await response.json().catch(() => null) as unknown;
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string"
      ? payload.detail
      : `Backend trả về HTTP ${response.status}`;
    throw new NexusApiError(detail, response.status);
  }
  if (!guard(payload)) {
    throw new NexusApiError("Backend trả về dữ liệu không đúng contract giao diện.", 502, "NEXUS_INVALID_RESPONSE");
  }
  return payload;
}

export const nexusApi = {
  capabilities(signal?: AbortSignal) {
    return requestJson("/api/diagnosis/capabilities", isCapabilities, { signal });
  },
  devices(signal?: AbortSignal) {
    return requestJson("/api/devices", (value): value is DeviceSummary[] => (
      Array.isArray(value) && value.every(isDevice)
    ), { signal });
  },
  bootstrapSimulator(signal?: AbortSignal) {
    return requestJson("/api/demo/simulator", (value): value is { device: DeviceSummary; sample: TelemetrySampleV1 } => (
      isRecord(value) && isDevice(value.device) && isRecord(value.sample)
    ), { method: "POST", signal });
  },
  diagnose(deviceId: string, symptom: string, mode: DiagnosisMode, signal?: AbortSignal) {
    return requestJson(
      `/api/devices/${encodeURIComponent(deviceId)}/diagnoses`,
      isSession,
      {
        method: "POST",
        signal,
        body: JSON.stringify({
          symptom,
          mode,
          max_steps: 6,
          require_fresh_read: mode === "live",
        }),
      },
    );
  },
};
