import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { env, toWebSocketUrl } from "../config/env";
import type { TelemetrySampleV1 } from "../contracts/v1";

export type ConnectionStatus = "disabled" | "searching" | "connected" | "disconnected" | "error";
export type MonitorSeverity = "healthy" | "warning" | "error";

export interface SerialConnection {
  status: ConnectionStatus;
  port: string | null;
  baud_rate: number;
  last_seen_at: string | null;
  log_file: string | null;
  message: string;
}

export interface LiveLog {
  id: string;
  occurred_at: string;
  level: "info" | "telemetry" | "warning" | "error";
  source: "backend" | "firmware";
  message: string;
}

export interface HardwareDiagnostic {
  code: string;
  severity: "warning" | "error";
  component_id: string;
  title: string;
  message: string;
  action: string;
  first_seen_at: string;
  last_seen_at: string;
  occurrences: number;
  active: boolean;
}

export interface HardwareSnapshot {
  connection: SerialConnection;
  telemetry: TelemetrySampleV1 | null;
  logs: LiveLog[];
  diagnostics: HardwareDiagnostic[];
  health: { status: MonitorSeverity; active_issue_count: number };
  hardware: {
    hardware_model_id: string;
    controller: string;
    sensor: string;
    driver: string;
    motor: string;
    power: string;
    limits: { min_bus_voltage_v: number; max_current_ma: number; max_pwm_percent: number };
  };
}

const initialSnapshot: HardwareSnapshot = {
  connection: {
    status: "searching",
    port: null,
    baud_rate: 115200,
    last_seen_at: null,
    log_file: null,
    message: "Đang kết nối tới backend và tìm ESP32...",
  },
  telemetry: null,
  logs: [],
  diagnostics: [],
  health: { status: "warning", active_issue_count: 0 },
  hardware: {
    hardware_model_id: "nexus-s3-ina226-l298n-motor-rig-v1",
    controller: "GOOUUU Tech ESP32-S3-N16R8",
    sensor: "INA226 (R100 shunt)",
    driver: "L298N",
    motor: "JGB37-520 12V + Hall encoder",
    power: "12V DC (không dùng pin vuông 9V)",
    limits: { min_bus_voltage_v: 9.5, max_current_ma: 1500, max_pwm_percent: 80 },
  },
};

interface HardwareMonitorValue {
  snapshot: HardwareSnapshot;
  streamStatus: "connecting" | "live" | "reconnecting" | "unavailable";
  history: TelemetrySampleV1[];
  lastUpdatedAt: number | null;
  retryAttempt: number;
  reconnect: () => void;
}

const HardwareMonitorContext = createContext<HardwareMonitorValue | null>(null);

export function HardwareMonitorProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [streamStatus, setStreamStatus] = useState<HardwareMonitorValue["streamStatus"]>(
    "connecting",
  );
  const [history, setHistory] = useState<TelemetrySampleV1[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [connectionEpoch, setConnectionEpoch] = useState(0);
  const reconnect = useCallback(() => setConnectionEpoch((value) => value + 1), []);

  useEffect(() => {
    // Protocol behavior is exercised by k6; jsdom's Event type conflicts with Node's WebSocket.
    if (import.meta.env.MODE === "test") return;

    let stopped = false;
    let retryDelay = 1000;
    let retryTimer: number | undefined;
    let socket: WebSocket | undefined;
    const abortController = new AbortController();

    fetch(`${env.apiBaseUrl}/api/v1/live`, { signal: abortController.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<HardwareSnapshot>;
      })
      .then((data) => {
        if (!stopped) {
          setSnapshot(data);
          setLastUpdatedAt(Date.now());
          if (data.telemetry) setHistory([data.telemetry]);
        }
      })
      .catch(() => {
        if (!stopped) setStreamStatus("unavailable");
      });

    const connect = () => {
      if (stopped || typeof WebSocket === "undefined") return;
      setStreamStatus(retryDelay === 1000 ? "connecting" : "reconnecting");
      socket = new WebSocket(`${toWebSocketUrl(env.apiBaseUrl)}/api/v1/live/ws`);
      socket.onopen = () => {
        retryDelay = 1000;
        setRetryAttempt(0);
        setStreamStatus("live");
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as {
            type?: string;
            data?: HardwareSnapshot;
          };
          if (message.type === "snapshot" && message.data) {
            setSnapshot(message.data);
            setLastUpdatedAt(Date.now());
            if (message.data.telemetry) {
              setHistory((current) => {
                const latest = message.data?.telemetry;
                if (!latest || current.at(-1)?.sample_id === latest.sample_id) return current;
                return [...current, latest].slice(-24);
              });
            }
          }
        } catch {
          setStreamStatus("unavailable");
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (stopped) return;
        setStreamStatus("reconnecting");
        retryDelay = Math.min(retryDelay * 2, 8000);
        setRetryAttempt((value) => value + 1);
        retryTimer = window.setTimeout(connect, retryDelay);
      };
    };

    const handleOnline = () => {
      if (!stopped && socket?.readyState !== WebSocket.OPEN) reconnect();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && socket?.readyState !== WebSocket.OPEN) {
        reconnect();
      }
    };

    window.addEventListener("online", handleOnline);
    document.addEventListener("visibilitychange", handleVisibility);
    connect();
    return () => {
      stopped = true;
      abortController.abort();
      if (retryTimer) window.clearTimeout(retryTimer);
      socket?.close();
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [connectionEpoch, reconnect]);

  const value = useMemo(
    () => ({ snapshot, streamStatus, history, lastUpdatedAt, retryAttempt, reconnect }),
    [snapshot, streamStatus, history, lastUpdatedAt, retryAttempt, reconnect],
  );
  return <HardwareMonitorContext.Provider value={value}>{children}</HardwareMonitorContext.Provider>;
}

// The provider and its hook intentionally share this small state module.
// eslint-disable-next-line react-refresh/only-export-components
export function useHardwareMonitor() {
  const value = useContext(HardwareMonitorContext);
  if (!value) throw new Error("useHardwareMonitor must be used inside HardwareMonitorProvider");
  return value;
}
