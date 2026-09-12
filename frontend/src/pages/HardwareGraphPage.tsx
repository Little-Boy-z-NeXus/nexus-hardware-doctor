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
  signalIds: string[],
): HardwareDiagnostic | undefined {
  return diagnostics.find((item) => item.signal_id && signalIds.includes(item.signal_id));
}

export function HardwareGraphPage() {
  const { snapshot, hardwareProfile, streamStatus, reconnect } = useHardwareMonitor();
  const [pausedLogs, setPausedLogs] = useState<LiveLog[] | null>(null);
  const [hiddenBefore, setHiddenBefore] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const [logLevel, setLogLevel] = useState<"all" | LiveLog["level"]>("all");
  const terminalRef = useRef<HTMLDivElement>(null);
  const telemetry = snapshot?.telemetry;
  const measurements = telemetry?.measurements;
  const activeDiagnostics = useMemo(
    () => snapshot?.diagnostics.filter((item) => item.active) ?? [],
    [snapshot],
  );
  const signalHealth = snapshot?.signal_health ?? {
    monitor_ready: false,
    i2c_verified: false,
    encoder_a_verified: false,
    encoder_b_verified: false,
    last_i2c_verified_at: null,
    last_encoder_verified_at: null,
  };
  const compatibility = snapshot?.compatibility ?? {
    expected_profile_id: hardwareProfile?.profile_id ?? "",
    reported_profile_id: null,
    expected_profile_sha256: "",
    reported_profile_sha256: null,
    expected_hardware_model_id: hardwareProfile?.hardware_model_id ?? "",
    reported_hardware_model_id: null,
    firmware_profile_version: null,
    firmware_profile_verified: false,
    sensor_identity_verified: false,
    last_verified_at: null,
  };
  const firmwareMismatch = activeSignalIssue(activeDiagnostics, ["firmware_profile"]);
  const sensorMismatch = activeSignalIssue(activeDiagnostics, ["sensor_identity"]);
  const componentForRole = (role: "controller" | "power_monitor" | "motor_driver" | "actuator" | "power") => hardwareProfile
    ? hardwareProfile.components.find((item) => item.component_id === hardwareProfile.roles[role])
    : undefined;
  const controller = componentForRole("controller");
  const sensor = componentForRole("power_monitor");
  const driver = componentForRole("motor_driver");
  const actuator = componentForRole("actuator");
  const power = componentForRole("power");
  const hardwareIdentity = [controller, sensor, driver, actuator]
    .filter(Boolean)
    .map((item) => item?.model)
    .join(" + ");
  const gpio = (role: string) => hardwareProfile?.firmware.pins[role];
  const wireColorLabel = (value: string | undefined) => ({
    yellow: "vàng",
    green: "xanh lá",
    blue: "xanh dương",
    black: "đen",
    red: "đỏ",
    white: "trắng",
  })[value ?? ""] ?? value;
  const wireForControllerPin = (role: string) => {
    if (!hardwareProfile || !controller) return undefined;
    const pinId = `gpio_${gpio(role)}`;
    const connection = hardwareProfile.connections.find((item) =>
      (item.from.component_id === controller.component_id && item.from.pin_id === pinId)
      || (item.to.component_id === controller.component_id && item.to.pin_id === pinId));
    return wireColorLabel(connection?.wire_color);
  };
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
          ? `Khớp hardware-as-code schema ${snapshot?.hardware.profile_schema_version ?? hardwareProfile?.schema_version}, `
            + `firmware ${compatibility.firmware_profile_version}, fingerprint `
            + `${compatibility.reported_profile_sha256?.slice(0, 12)}.`
          : "Chờ heartbeat HARDWARE_PROFILE; nếu chờ lâu, hãy nạp firmware mới nhất."),
    },
    {
      id: "sensor-identity",
      label: "Chip cảm biến",
      pin: hardwareProfile
        ? `${sensor?.model ?? "Power monitor"} · ${hardwareProfile.firmware.sensor.i2c_address}`
        : "Đang tải định danh cảm biến từ profile",
      state: sensorMismatch
        ? "error"
        : compatibility.sensor_identity_verified
          ? "healthy"
          : "waiting",
      detail:
        sensorMismatch?.action ??
        (compatibility.sensor_identity_verified
          ? `${sensor?.model ?? "Cảm biến"} đã khớp identity khai báo trong profile.`
          : "Chờ firmware đọc identity; module gắn nhầm sẽ bị chặn tại đây."),
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
          ? `Khớp ${hardwareIdentity || "hardware profile đang chọn"}.`
          : `Cần ${compatibility.expected_hardware_model_id}.`,
    },
  ];
  const i2cSharedSignals = ["i2c_bus", "sensor_identity"];
  const signalChecks: SignalCheck[] = [
    {
      id: "sda",
      label: "SDA",
      pin: hardwareProfile ? `I²C SDA → GPIO${gpio("i2c_sda")}` : "Đang tải từ profile",
      state: activeSignalIssue(activeDiagnostics, ["i2c_sda", ...i2cSharedSignals])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["i2c_sda", ...i2cSharedSignals])?.action ??
        (signalHealth.i2c_verified
          ? `ACK, chip ID và dữ liệu từ ${sensor?.model ?? "cảm biến"} hợp lệ ở gói mới nhất.`
          : "Chờ power monitor vượt qua kiểm tra ACK và chip ID."),
    },
    {
      id: "scl",
      label: "SCL",
      pin: hardwareProfile ? `I²C SCL → GPIO${gpio("i2c_scl")}` : "Đang tải từ profile",
      state: activeSignalIssue(activeDiagnostics, ["i2c_scl", ...i2cSharedSignals])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["i2c_scl", ...i2cSharedSignals])?.action ??
        (signalHealth.i2c_verified
          ? "Bus idle HIGH và giao dịch I²C hợp lệ ở gói mới nhất."
          : "Chờ power monitor vượt qua kiểm tra bus I²C."),
    },
    {
      id: "encoder-a",
      label: "Encoder A",
      pin: hardwareProfile ? `${wireForControllerPin("encoder_a") ? `Dây ${wireForControllerPin("encoder_a")}` : "Encoder A"} → GPIO${gpio("encoder_a")}` : "Đang tải từ profile",
      state: activeSignalIssue(activeDiagnostics, ["encoder_a", "encoder_bus"])
        ? "error"
        : signalHealth.encoder_a_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["encoder_a", "encoder_bus"])?.action ??
        (signalHealth.encoder_a_verified
          ? "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất."
          : "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát."),
    },
    {
      id: "encoder-b",
      label: "Encoder B",
      pin: hardwareProfile ? `${wireForControllerPin("encoder_b") ? `Dây ${wireForControllerPin("encoder_b")}` : "Encoder B"} → GPIO${gpio("encoder_b")}` : "Đang tải từ profile",
      state: activeSignalIssue(activeDiagnostics, ["encoder_b", "encoder_bus"])
        ? "error"
        : signalHealth.encoder_b_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["encoder_b", "encoder_bus"])?.action ??
        (signalHealth.encoder_b_verified
          ? "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất."
          : "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát."),
    },
  ];
  const visibleLogs = (pausedLogs ?? snapshot?.logs ?? []).filter((item) => {
    const afterClear = !hiddenBefore || item.occurred_at > hiddenBefore;
    const levelMatches = logLevel === "all" || item.level === logLevel;
    const queryMatches = item.message.toLocaleLowerCase("vi").includes(logQuery.trim().toLocaleLowerCase("vi"));
    return afterClear && levelMatches && queryMatches;
  });
  const deviceLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const savedLogName = snapshot?.connection.log_file?.split(/[\\/]/).pop() ?? "đang chờ log";

  useEffect(() => {
    if (!pausedLogs && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [visibleLogs.length, pausedLogs]);

  const componentPresentation = {
    controller: { icon: Cpu, tone: "blue" },
    sensor: { icon: Activity, tone: "teal" },
    driver: { icon: Zap, tone: "violet" },
    actuator: { icon: RotateCcw, tone: "orange" },
    power: { icon: Gauge, tone: "orange" },
    compute: { icon: Cpu, tone: "blue" },
    communication: { icon: Cable, tone: "teal" },
    other: { icon: Activity, tone: "teal" },
  } as const;
  const nodes = hardwareProfile ? hardwareProfile.components.map((component) => {
    const detail = component.component_id === hardwareProfile.roles.controller
      ? deviceLive
        ? `${snapshot?.connection.port} · ${snapshot?.connection.baud_rate} baud`
        : "Chưa nhận device transport"
      : component.component_id === hardwareProfile.roles.power_monitor
        ? `${valueOrDash(measurements?.bus_voltage_v)} V · ${valueOrDash(measurements?.current_ma, 1)} mA`
        : component.component_id === hardwareProfile.roles.motor_driver
          ? measurements
            ? `${measurements.driver_enabled ? "Đang bật" : "Đang tắt"} · PWM ${measurements.pwm_percent}%`
            : "Chờ telemetry"
          : component.component_id === hardwareProfile.roles.actuator
            ? measurements?.motor_rpm == null
              ? "RPM chờ hiệu chuẩn encoder"
              : `${valueOrDash(measurements.motor_rpm, 0)} RPM`
            : component.component_id === hardwareProfile.roles.power
              ? "Nguồn cấp cho hệ thống"
              : `${component.capabilities.length} khả năng đã khai báo`;
    const presentation = componentPresentation[
      component.component_type as keyof typeof componentPresentation
    ] ?? componentPresentation.other;
    return {
      id: component.component_id,
      name: component.model,
      type: component.component_type.replaceAll("_", " "),
      detail,
      ...presentation,
      state:
        component.component_id === hardwareProfile.roles.controller && !deviceLive
          ? ("waiting" as NodeState)
          : componentState(component.component_id, activeDiagnostics, Boolean(telemetry)),
    };
  }) : [];
  const hardwareFlowTitle = nodes.length
    ? nodes.map((node) => node.name).join(" → ")
    : "Đang tải hardware profile từ backend";
  const profileLabel = `Profile ${snapshot?.hardware.profile_schema_version ?? hardwareProfile?.schema_version ?? "--"} · ${snapshot?.hardware.profile_id ?? hardwareProfile?.profile_id ?? "đang tải"}`;

  const togglePause = () => setPausedLogs((current) => (current ? null : [...(snapshot?.logs ?? [])]));
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
            {deviceLive ? `${snapshot?.connection.port} đang live` : `Đang chờ ${controller?.model ?? "hardware profile"}`}
          </span>
        }
      />

      <section
        className={`connection-banner connection-banner--${deviceLive ? "healthy" : snapshot?.connection.status === "error" ? "error" : "warning"}`}
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
              : snapshot?.connection.message ?? "Đang tải trạng thái runtime từ backend."}
          </p>
        </div>
        <span className="connection-banner__meta">
          Gói cuối: {timeLabel(snapshot?.connection.last_seen_at ?? null)}
        </span>
        {!deviceLive && <button className="button button--secondary connection-banner__action" type="button" onClick={reconnect}><RefreshCw size={15} /> Thử nối lại</button>}
      </section>

      <section className="card graph-card">
        <div className="panel__header graph-card__header">
          <div className="graph-card__heading">
            <p className="eyebrow">BOM signal path</p>
            <h2 className="graph-card__title" title={hardwareFlowTitle}>{hardwareFlowTitle}</h2>
          </div>
          <span className={`status-pill status-pill--${snapshot?.health.status ?? "warning"}`}>
            {activeDiagnostics.length} lỗi đang mở
          </span>
        </div>
        <div
          className="hardware-flow"
          data-testid="hardware-flow-scroll"
          role="region"
          aria-label={`Chuỗi ${nodes.length} thành phần phần cứng. Có thể cuộn ngang để xem đầy đủ.`}
          tabIndex={0}
        >
          <div className="hardware-flow__track">
            {nodes.map(({ id, name, type, detail, icon: Icon, tone, state }, index) => (
              <div className="hardware-step" key={id}>
                <article
                  className={`hardware-node hardware-node--${tone} hardware-node--state-${state}`}
                  aria-label={`${type}: ${name}, ${stateLabel(state)}`}
                >
                  <span className="hardware-node__icon">
                    <Icon size={24} />
                  </span>
                  <span className="hardware-node__content">
                    <small title={type}>{type}</small>
                    <strong title={name}>{name}</strong>
                    <em title={detail}>{detail}</em>
                  </span>
                  <span className={`node-state node-state--${state}`}>{stateLabel(state)}</span>
                </article>
                {index < nodes.length - 1 && (
                  <span className="hardware-edge" aria-hidden="true">
                    <i />
                    <ArrowRight size={17} />
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="graph-legend">
          <span>
            <i
              className={`legend-dot${deviceLive ? " legend-dot--live" : " legend-dot--offline"}`}
            />
            {deviceLive ? "Live telemetry" : "Đang chờ dữ liệu"}
          </span>
          <span><i className="legend-line" /> Luồng tín hiệu</span>
          <span className="graph-legend__profile" title={profileLabel}>{profileLabel}</span>
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
            <div><dt>Mainboard</dt><dd>{controller?.model ?? "--"}</dd></div>
            <div><dt>Cảm biến</dt><dd>{sensor ? `${sensor.model} · SDA GPIO${gpio("i2c_sda")} / SCL GPIO${gpio("i2c_scl")}` : "--"}</dd></div>
            <div><dt>Driver</dt><dd>{driver ? `${driver.model} · ENA ${gpio("motor_enable")} / IN1 ${gpio("motor_in1")} / IN2 ${gpio("motor_in2")}` : "--"}</dd></div>
            <div><dt>Motor</dt><dd>{actuator ? `${actuator.model} · Encoder A${gpio("encoder_a")} / B${gpio("encoder_b")}` : "--"}</dd></div>
            <div><dt>Nguồn</dt><dd>{power?.model ?? "--"}</dd></div>
          </dl>
        </article>
      </section>
    </div>
  );
}
