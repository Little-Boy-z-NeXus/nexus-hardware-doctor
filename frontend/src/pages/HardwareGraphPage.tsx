import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Cable,
  CheckCircle2,
  CircleOff,
  Cpu,
  Download,
  Gauge,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  TerminalSquare,
  Trash2,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { env } from "../config/env";
import {
  useHardwareMonitor,
  type HardwareDiagnostic,
  type LiveLog,
} from "../realtime/HardwareMonitorContext";

type NodeState = "healthy" | "warning" | "error" | "waiting";

interface SignalCheck {
  id: string;
  label: string;
  pin: string;
  state: NodeState;
  detail: string;
}

interface HardwareProfileComponent {
  component_id: string;
  component_type: string;
  model: string;
  address?: string;
}

interface HardwareAsCodeProfile {
  profile_id: string;
  roles: {
    controller: string;
    power_monitor: string;
    motor_driver: string;
    actuator: string;
    power: string;
  };
  components: HardwareProfileComponent[];
  firmware: {
    pins: Record<string, number>;
    sensor: { i2c_address: string };
  };
}

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

function activeSignalIssue(
  diagnostics: HardwareDiagnostic[],
  codes: string[],
): HardwareDiagnostic | undefined {
  return diagnostics.find((item) => codes.includes(item.code));
}

export function HardwareGraphPage() {
  const { snapshot, streamStatus, reconnect } = useHardwareMonitor();
  const [pausedLogs, setPausedLogs] = useState<LiveLog[] | null>(null);
  const [hiddenBefore, setHiddenBefore] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const [logLevel, setLogLevel] = useState<"all" | LiveLog["level"]>("all");
  const [hardwareProfile, setHardwareProfile] = useState<HardwareAsCodeProfile | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const telemetry = snapshot.telemetry;
  const measurements = telemetry?.measurements;
  const activeDiagnostics = useMemo(
    () => snapshot.diagnostics.filter((item) => item.active),
    [snapshot.diagnostics],
  );
  const signalHealth = snapshot.signal_health ?? {
    monitor_ready: false,
    i2c_verified: false,
    encoder_a_verified: false,
    encoder_b_verified: false,
    last_i2c_verified_at: null,
    last_encoder_verified_at: null,
  };
  const compatibility = snapshot.compatibility ?? {
    expected_profile_id: snapshot.hardware.profile_id,
    reported_profile_id: null,
    expected_profile_sha256: snapshot.hardware.profile_sha256,
    reported_profile_sha256: null,
    expected_hardware_model_id: snapshot.hardware.hardware_model_id,
    reported_hardware_model_id: null,
    firmware_profile_version: null,
    firmware_profile_verified: false,
    sensor_identity_verified: false,
    last_verified_at: null,
  };
  const firmwareMismatch = activeSignalIssue(activeDiagnostics, [
    "FIRMWARE_PROFILE_MISMATCH",
    "HARDWARE_MODEL_MISMATCH",
  ]);
  const sensorMismatch = activeSignalIssue(activeDiagnostics, ["INA226_ID_MISMATCH"]);
  const compatibilityChecks: SignalCheck[] = [
    {
      id: "firmware-profile",
      label: "Firmware",
      pin: compatibility.reported_profile_id ?? "Chưa nhận profile từ board",
      state: firmwareMismatch
        ? "error"
        : compatibility.firmware_profile_verified
          ? "healthy"
          : "waiting",
      detail:
        firmwareMismatch?.action ??
        (compatibility.firmware_profile_verified
          ? `Khớp hardware-as-code schema ${snapshot.hardware.profile_schema_version}, `
            + `firmware ${compatibility.firmware_profile_version}, fingerprint `
            + `${compatibility.reported_profile_sha256?.slice(0, 12)}.`
          : "Chờ heartbeat HARDWARE_PROFILE; nếu chờ lâu, hãy nạp firmware mới nhất."),
    },
    {
      id: "sensor-identity",
      label: "Chip cảm biến",
      pin: hardwareProfile
        ? `${hardwareProfile.components.find((item) => item.component_id === hardwareProfile.roles.power_monitor)?.model ?? "Power monitor"} · ${hardwareProfile.firmware.sensor.i2c_address}`
        : "Yêu cầu INA226 R100 · 0x40",
      state: sensorMismatch
        ? "error"
        : compatibility.sensor_identity_verified
          ? "healthy"
          : "waiting",
      detail:
        sensorMismatch?.action ??
        (compatibility.sensor_identity_verified
          ? "Manufacturer ID 0x5449 và die ID 0x226x đã khớp."
          : "Chờ đọc identity; INA219 hoặc module gắn nhầm sẽ bị chặn tại đây."),
    },
    {
      id: "reported-model",
      label: "BOM đang báo",
      pin: compatibility.reported_hardware_model_id ?? "Chưa nhận model từ board",
      state: firmwareMismatch
        ? "error"
        : compatibility.reported_hardware_model_id === compatibility.expected_hardware_model_id
          ? "healthy"
          : "waiting",
      detail:
        compatibility.reported_hardware_model_id === compatibility.expected_hardware_model_id
          ? "Khớp GOOUUU S3 + INA226 R100 + L298N + JGB37-520."
          : `Cần ${compatibility.expected_hardware_model_id}.`,
    },
  ];
  const i2cSharedCodes = [
    "INA226_I2C_NO_ACK",
    "INA226_I2C_FAILURE",
    "INA226_ID_MISMATCH",
    "INA226_SIGNAL_INCONSISTENT",
  ];
  const signalChecks: SignalCheck[] = [
    {
      id: "sda",
      label: "SDA",
      pin: `I²C SDA → GPIO${hardwareProfile?.firmware.pins.i2c_sda ?? 1}`,
      state: activeSignalIssue(activeDiagnostics, ["I2C_SDA_STUCK_LOW", ...i2cSharedCodes])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["I2C_SDA_STUCK_LOW", ...i2cSharedCodes])?.action ??
        (signalHealth.i2c_verified
          ? "ACK, chip ID và dữ liệu R100 hợp lệ ở gói mới nhất."
          : "Chờ INA226 vượt qua kiểm tra ACK và chip ID."),
    },
    {
      id: "scl",
      label: "SCL",
      pin: `I²C SCL → GPIO${hardwareProfile?.firmware.pins.i2c_scl ?? 2}`,
      state: activeSignalIssue(activeDiagnostics, ["I2C_SCL_STUCK_LOW", ...i2cSharedCodes])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["I2C_SCL_STUCK_LOW", ...i2cSharedCodes])?.action ??
        (signalHealth.i2c_verified
          ? "Bus idle HIGH và giao dịch I²C hợp lệ ở gói mới nhất."
          : "Chờ INA226 vượt qua kiểm tra bus I²C."),
    },
    {
      id: "encoder-a",
      label: "Encoder A",
      pin: `Dây vàng → GPIO${hardwareProfile?.firmware.pins.encoder_a ?? 16}`,
      state: activeSignalIssue(activeDiagnostics, [
        "ENCODER_CHANNEL_A_MISSING",
        "ENCODER_SIGNAL_MISSING",
        "ENCODER_SIGNAL_INVALID",
      ])
        ? "error"
        : signalHealth.encoder_a_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, [
          "ENCODER_CHANNEL_A_MISSING",
          "ENCODER_SIGNAL_MISSING",
          "ENCODER_SIGNAL_INVALID",
        ])?.action ??
        (signalHealth.encoder_a_verified
          ? "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất."
          : "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát."),
    },
    {
      id: "encoder-b",
      label: "Encoder B",
      pin: `Dây xanh lá → GPIO${hardwareProfile?.firmware.pins.encoder_b ?? 17}`,
      state: activeSignalIssue(activeDiagnostics, [
        "ENCODER_CHANNEL_B_MISSING",
        "ENCODER_SIGNAL_MISSING",
        "ENCODER_SIGNAL_INVALID",
      ])
        ? "error"
        : signalHealth.encoder_b_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, [
          "ENCODER_CHANNEL_B_MISSING",
          "ENCODER_SIGNAL_MISSING",
          "ENCODER_SIGNAL_INVALID",
        ])?.action ??
        (signalHealth.encoder_b_verified
          ? "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất."
          : "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát."),
    },
  ];
  const visibleLogs = (pausedLogs ?? snapshot.logs).filter((item) => {
    const afterClear = !hiddenBefore || item.occurred_at > hiddenBefore;
    const levelMatches = logLevel === "all" || item.level === logLevel;
    const queryMatches = item.message.toLocaleLowerCase("vi").includes(logQuery.trim().toLocaleLowerCase("vi"));
    return afterClear && levelMatches && queryMatches;
  });
  const deviceLive = streamStatus === "live" && snapshot.connection.status === "connected";
  const savedLogName = snapshot.connection.log_file?.split(/[\\/]/).pop() ?? "đang chờ log";

  useEffect(() => {
    if (!pausedLogs && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [visibleLogs.length, pausedLogs]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${env.apiBaseUrl}/api/v1/hardware-profile`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Hardware profile HTTP ${response.status}`);
        return response.json() as Promise<HardwareAsCodeProfile>;
      })
      .then(setHardwareProfile)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setHardwareProfile(null);
        }
      });
    return () => controller.abort();
  }, []);

  const flowRoles = ["controller", "power_monitor", "motor_driver", "actuator"] as const;
  const flowPresentation = [
    { icon: Cpu, tone: "blue" },
    { icon: Activity, tone: "teal" },
    { icon: Zap, tone: "violet" },
    { icon: RotateCcw, tone: "orange" },
  ];
  const fallbackIds = ["esp32", "ina226", "l298n", "motor"];
  const fallbackNames = [
    snapshot.hardware.controller,
    snapshot.hardware.sensor,
    snapshot.hardware.driver,
    snapshot.hardware.motor,
  ];
  const nodeDetails = [
    deviceLive
      ? `${snapshot.connection.port} · ${snapshot.connection.baud_rate} baud`
      : "Chưa nhận device transport",
    `${valueOrDash(measurements?.bus_voltage_v)} V · ${valueOrDash(measurements?.current_ma, 1)} mA`,
    measurements
      ? `${measurements.driver_enabled ? "Đang bật" : "Đang tắt"} · PWM ${measurements.pwm_percent}%`
      : "Chờ telemetry",
    measurements?.motor_rpm == null
      ? "RPM chờ hiệu chuẩn encoder"
      : `${valueOrDash(measurements.motor_rpm, 0)} RPM`,
  ];
  const nodes = flowRoles.map((role, index) => {
    const componentId = hardwareProfile?.roles[role] ?? fallbackIds[index];
    const component = hardwareProfile?.components.find(
      (item) => item.component_id === componentId,
    );
    return {
      id: componentId,
      name: component?.model ?? fallbackNames[index],
      type: component?.component_type ?? role.replaceAll("_", " "),
      detail: nodeDetails[index],
      ...flowPresentation[index],
      state:
        role === "controller" && !deviceLive
          ? ("waiting" as NodeState)
          : componentState(componentId, activeDiagnostics, Boolean(telemetry)),
    };
  });
  const hardwareFlowTitle = nodes.map((node) => node.name).join(" → ");

  const togglePause = () => setPausedLogs((current) => (current ? null : [...snapshot.logs]));
  const clearVisibleLogs = () => setHiddenBefore(new Date().toISOString());
  const downloadLogs = () => {
    const body = visibleLogs
      .map((item) => `[${item.occurred_at}] [${item.level.toUpperCase()}] [${item.source}] ${item.message}`)
      .join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `nexus-live-log-${new Date().toISOString().replaceAll(":", "-")}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Bác sĩ phần cứng realtime"
        title="Sơ đồ phần cứng"
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
        role="status"
        aria-live="polite"
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
        {!deviceLive && <button className="button button--secondary connection-banner__action" type="button" onClick={reconnect}><RefreshCw size={15} /> Thử nối lại</button>}
      </section>

      <section className="card graph-card">
        <div className="panel__header">
          <div>
            <p className="eyebrow">BOM signal path</p>
            <h2>{hardwareFlowTitle}</h2>
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
            Profile {snapshot.hardware.profile_schema_version} · {snapshot.hardware.profile_id}
          </span>
        </div>
      </section>

      <section className="card signal-card" aria-labelledby="compatibility-title">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Hardware fingerprint</p>
            <h2 id="compatibility-title">Đối chiếu firmware với BOM</h2>
          </div>
          <ShieldCheck size={21} />
        </div>
        <p className="signal-card__intro">
          NeXus kiểm tra firmware khai báo đúng bộ phần cứng và xác minh identity của chip trước khi
          tin số đo. Sai firmware và sai cảm biến được báo thành hai lỗi riêng.
        </p>
        <div className="signal-grid compatibility-grid" aria-live="polite">
          {compatibilityChecks.map((check) => (
            <article className={`signal-item signal-item--${check.state}`} key={check.id}>
              <span className={`node-state node-state--${check.state}`}>
                {stateLabel(check.state)}
              </span>
              <strong>{check.label}</strong>
              <small>{check.pin}</small>
              <p>{check.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card signal-card" aria-labelledby="signal-health-title">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Signal wire watchdog</p>
            <h2 id="signal-health-title">Tình trạng dây tín hiệu</h2>
          </div>
          <Cable size={21} />
        </div>
        <p className="signal-card__intro">
          SDA/SCL được kiểm tra ở từng gói. Encoder chỉ được xác nhận khi motor thực sự được lệnh
          chạy; trạng thái chờ không có nghĩa là dây đã hỏng.
        </p>
        <div className="signal-grid" aria-live="polite">
          {signalChecks.map((signal) => (
            <article className={`signal-item signal-item--${signal.state}`} key={signal.id}>
              <span className={`node-state node-state--${signal.state}`}>
                {stateLabel(signal.state)}
              </span>
              <strong>{signal.label}</strong>
              <small>{signal.pin}</small>
              <p>{signal.detail}</p>
            </article>
          ))}
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
              <div className="diagnostic-item diagnostic-item--error" role="alert">
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
                <div><strong>{item.title}</strong><span>{item.code} · {item.occurrences} mẫu liên tiếp</span></div>
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
              <span><strong>ESP32 Live Log</strong><small>{pausedLogs ? "Đã tạm dừng" : `Tự cuộn · đang lưu ${savedLogName}`}</small></span>
            </div>
            <div className="terminal-actions">
              <button type="button" onClick={togglePause}>
                {pausedLogs ? <Play size={14} /> : <Pause size={14} />}
                {pausedLogs ? "Tiếp tục" : "Tạm dừng"}
              </button>
              <button type="button" onClick={clearVisibleLogs}><Trash2 size={14} />Ẩn log cũ</button>
              <button type="button" onClick={downloadLogs} disabled={!visibleLogs.length}><Download size={14} />Tải log</button>
            </div>
          </div>
          <div className="terminal-toolbar">
            <label>
              <Search size={15} aria-hidden="true" />
              <span className="sr-only">Tìm trong log</span>
              <input value={logQuery} onChange={(event) => setLogQuery(event.target.value)} placeholder="Tìm mã lỗi hoặc giá trị…" />
            </label>
            <select value={logLevel} onChange={(event) => setLogLevel(event.target.value as typeof logLevel)} aria-label="Lọc log theo mức">
              <option value="all">Tất cả mức</option>
              <option value="error">Lỗi</option>
              <option value="warning">Cảnh báo</option>
              <option value="telemetry">Telemetry</option>
              <option value="info">Thông tin</option>
            </select>
            <span>{visibleLogs.length} dòng</span>
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
