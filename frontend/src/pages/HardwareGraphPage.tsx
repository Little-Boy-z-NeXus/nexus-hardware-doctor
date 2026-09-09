import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleOff,
  Cpu,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  TerminalSquare,
  Trash2,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import {
  useHardwareMonitor,
  type HardwareDiagnostic,
  type LiveLog,
} from "../realtime/HardwareMonitorContext";

type NodeState = "healthy" | "warning" | "error" | "waiting";

const timeLabel = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(value))
    : "--:--:--";

const valueOrDash = (value: number | null | undefined, digits = 2) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

function componentState(
  componentId: string,
  diagnostics: HardwareDiagnostic[],
  hasTelemetry: boolean,
): NodeState {
  const findings = diagnostics.filter((item) => item.component_id === componentId);
  if (findings.some((item) => item.severity === "error")) return "error";
  if (findings.length) return "warning";
  return hasTelemetry ? "healthy" : "waiting";
}

function stateLabel(state: NodeState) {
  return {
    healthy: "Ổn định",
    warning: "Cần kiểm tra",
    error: "Có lỗi",
    waiting: "Chờ dữ liệu",
  }[state];
}

export function HardwareGraphPage() {
  const { snapshot, streamStatus } = useHardwareMonitor();
  const [pausedLogs, setPausedLogs] = useState<LiveLog[] | null>(null);
  const [hiddenBefore, setHiddenBefore] = useState<string | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const telemetry = snapshot.telemetry;
  const measurements = telemetry?.measurements;
  const activeDiagnostics = useMemo(
    () => snapshot.diagnostics.filter((item) => item.active),
    [snapshot.diagnostics],
  );
  const visibleLogs = (pausedLogs ?? snapshot.logs).filter(
    (item) => !hiddenBefore || item.occurred_at > hiddenBefore,
  );
  const deviceLive = streamStatus === "live" && snapshot.connection.status === "connected";

  useEffect(() => {
    if (!pausedLogs && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [visibleLogs.length, pausedLogs]);

  const nodes = [
    {
      id: "esp32",
      name: "GOOUUU ESP32-S3",
      type: "Controller · N16R8",
      detail: deviceLive
        ? `${snapshot.connection.port} · 115200 baud`
        : "Chưa nhận USB serial",
      icon: Cpu,
      tone: "blue",
      state: deviceLive
        ? componentState("esp32", activeDiagnostics, Boolean(telemetry))
        : ("waiting" as NodeState),
    },
    {
      id: "ina219",
      name: "INA219",
      type: "Voltage + current sensor",
      detail: `${valueOrDash(measurements?.bus_voltage_v)} V · ${valueOrDash(measurements?.current_ma, 1)} mA`,
      icon: Activity,
      tone: "teal",
      state: componentState("ina219", activeDiagnostics, Boolean(telemetry)),
    },
    {
      id: "l298n",
      name: "L298N",
      type: "Motor driver · Channel A",
      detail: measurements
        ? `${measurements.driver_enabled ? "Đang bật" : "Đang tắt"} · PWM ${measurements.pwm_percent}%`
        : "Chờ telemetry",
      icon: Zap,
      tone: "violet",
      state: componentState("l298n", activeDiagnostics, Boolean(telemetry)),
    },
    {
      id: "motor",
      name: "JGB37-520",
      type: "12V motor + Hall encoder",
      detail:
        measurements?.motor_rpm == null
          ? "RPM chờ hiệu chuẩn encoder"
          : `${valueOrDash(measurements.motor_rpm, 0)} RPM`,
      icon: RotateCcw,
      tone: "orange",
      state: componentState("motor", activeDiagnostics, Boolean(telemetry)),
    },
  ];

  const togglePause = () => setPausedLogs((current) => (current ? null : [...snapshot.logs]));
  const clearVisibleLogs = () => setHiddenBefore(new Date().toISOString());

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Realtime hardware doctor"
        title="Hardware Graph"
        description="Theo dõi đúng bộ MVP đã chốt, xem log từ ESP32 và nhận hướng dẫn xử lý lỗi mà không cần mở CMD."
        action={
          <span className={`status-pill status-pill--${deviceLive ? "healthy" : "warning"}`}>
            {deviceLive ? <CheckCircle2 size={15} /> : <CircleOff size={15} />}
            {deviceLive ? `${snapshot.connection.port} đang live` : "Đang chờ ESP32"}
          </span>
        }
      />

      <section
        className={`connection-banner connection-banner--${deviceLive ? "healthy" : snapshot.connection.status === "error" ? "error" : "warning"}`}
      >
        <span className="connection-banner__icon">
          {deviceLive ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
        </span>
        <div>
          <strong>
            {deviceLive ? "Dữ liệu đang cập nhật realtime" : "Chưa có luồng telemetry trực tiếp"}
          </strong>
          <p>
            {streamStatus !== "live"
              ? "UI đang thử nối lại backend. Hãy giữ cửa sổ Backend đang chạy."
              : snapshot.connection.message}
          </p>
        </div>
        <span className="connection-banner__meta">
          Gói cuối: {timeLabel(snapshot.connection.last_seen_at)}
        </span>
      </section>

      <section className="card graph-card">
        <div className="panel__header">
          <div>
            <p className="eyebrow">BOM signal path</p>
            <h2>GOOUUU S3 → INA219 → L298N → JGB37-520</h2>
          </div>
          <span className={`status-pill status-pill--${snapshot.health.status}`}>
            {activeDiagnostics.length} lỗi đang mở
          </span>
        </div>
        <div className="hardware-flow">
          {nodes.map(({ id, name, type, detail, icon: Icon, tone, state }, index) => (
            <div className="hardware-step" key={id}>
              <div
                className={`hardware-node hardware-node--${tone} hardware-node--state-${state}`}
              >
                <span className="hardware-node__icon">
                  <Icon size={24} />
                </span>
                <span>
                  <small>{type}</small>
                  <strong>{name}</strong>
                  <em>{detail}</em>
                </span>
                <span className={`node-state node-state--${state}`}>{stateLabel(state)}</span>
              </div>
              {index < nodes.length - 1 && (
                <span className="hardware-edge" aria-hidden="true">
                  <i />
                  <ArrowRight size={17} />
                </span>
              )}
            </div>
          ))}
        </div>
        <div className="graph-legend">
          <span>
            <i
              className={`legend-dot${deviceLive ? " legend-dot--live" : " legend-dot--offline"}`}
            />
            {deviceLive ? "Live telemetry" : "Đang chờ dữ liệu"}
          </span>
          <span><i className="legend-line" /> Luồng tín hiệu</span>
          <span>
            Schema {telemetry?.schema_version ?? "1.0.0"} · {snapshot.hardware.hardware_model_id}
          </span>
        </div>
      </section>

      <section className="monitor-grid">
        <article className="card panel diagnostic-panel">
          <div className="panel__header">
            <div><p className="eyebrow">Nhận biết lỗi</p><h2>Việc cần xử lý</h2></div>
            <AlertTriangle size={21} />
          </div>
          <div className="diagnostic-list">
            {streamStatus !== "live" && (
              <div className="diagnostic-item diagnostic-item--error">
                <div><strong>Không kết nối được backend</strong><span>UI không thể nhận log realtime.</span></div>
                <p><b>Làm ngay:</b> Double-click <code>nexus-start-app.cmd</code> và giữ cửa sổ Backend mở.</p>
              </div>
            )}
            {streamStatus === "live" && activeDiagnostics.length === 0 && (
              <div className="diagnostic-empty">
                <CheckCircle2 size={24} />
                <strong>Chưa phát hiện lỗi</strong>
                <span>NeXus vẫn đang kiểm tra từng gói mới.</span>
              </div>
            )}
            {activeDiagnostics.map((item) => (
              <div className={`diagnostic-item diagnostic-item--${item.severity}`} key={item.code}>
                <div><strong>{item.title}</strong><span>{item.code} · lặp {item.occurrences} lần</span></div>
                <p>{item.message}</p>
                <p><b>Làm ngay:</b> {item.action}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="card terminal-card">
          <div className="terminal-card__header">
            <div>
              <TerminalSquare size={19} />
              <span><strong>ESP32 Live Log</strong><small>{pausedLogs ? "Đã tạm dừng" : "Tự cuộn · realtime"}</small></span>
            </div>
            <div className="terminal-actions">
              <button type="button" onClick={togglePause}>
                {pausedLogs ? <Play size={14} /> : <Pause size={14} />}
                {pausedLogs ? "Tiếp tục" : "Tạm dừng"}
              </button>
              <button type="button" onClick={clearVisibleLogs}><Trash2 size={14} />Ẩn log cũ</button>
            </div>
          </div>
          <div className="terminal-feed" ref={terminalRef} role="log" aria-live="polite">
            {visibleLogs.length === 0 && (
              <p className="terminal-empty">Log từ firmware sẽ hiện tại đây ngay khi ESP32 gửi dữ liệu.</p>
            )}
            {visibleLogs.map((item) => (
              <div className={`terminal-line terminal-line--${item.level}`} key={item.id}>
                <time>{timeLabel(item.occurred_at)}</time>
                <span>{item.source}</span>
                <code>{item.message}</code>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Latest packet</p><h2>Telemetry thật từ board</h2></div><Gauge size={22} /></div>
          <dl className="detail-list">
            <div><dt>Bus voltage</dt><dd>{valueOrDash(measurements?.bus_voltage_v, 3)} V</dd></div>
            <div><dt>Current</dt><dd>{valueOrDash(measurements?.current_ma, 2)} mA</dd></div>
            <div><dt>Power</dt><dd>{valueOrDash(measurements?.power_mw, 2)} mW</dd></div>
            <div><dt>Driver / PWM</dt><dd>{measurements ? `${measurements.driver_enabled ? "ON" : "OFF"} / ${measurements.pwm_percent}%` : "--"}</dd></div>
            <div><dt>Sequence</dt><dd>{telemetry?.sequence ?? "--"}</dd></div>
          </dl>
        </article>
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">MVP guardrails</p><h2>Bộ phần cứng đã khóa</h2></div><Activity size={22} /></div>
          <dl className="detail-list">
            <div><dt>Mainboard</dt><dd>{snapshot.hardware.controller}</dd></div>
            <div><dt>Cảm biến</dt><dd>{snapshot.hardware.sensor} · SDA GPIO1 / SCL GPIO2</dd></div>
            <div><dt>Driver</dt><dd>{snapshot.hardware.driver} · ENA 12 / IN1 13 / IN2 14</dd></div>
            <div><dt>Motor</dt><dd>{snapshot.hardware.motor} · Encoder A16 / B17</dd></div>
            <div><dt>Nguồn</dt><dd>{snapshot.hardware.power}</dd></div>
          </dl>
        </article>
      </section>
    </div>
  );
}
