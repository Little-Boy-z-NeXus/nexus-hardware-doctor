import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Cable,
  CheckCircle2,
  CircleOff,
  Cpu,
  Gauge,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { DualMotorArchitecture } from "../components/DualMotorArchitecture";
import { HardwareDiagnosticsPanel } from "../components/HardwareDiagnosticsPanel";
import { HardwareLiveLog } from "../components/HardwareLiveLog";
import { KeyboardMotorControl } from "../components/KeyboardMotorControl";
import { WiringGuide } from "../components/WiringGuide";
import {
  useHardwareMonitor,
  type HardwareDiagnostic,
} from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";
import { localizeConnectionMessage } from "../i18n/runtimeCopy";

type NodeState = "healthy" | "warning" | "error" | "waiting";

interface SignalCheck {
  id: string;
  label: string;
  pin: string;
  state: NodeState;
  detail: string;
}

const timeLabel = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale, {
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

function stateLabel(state: NodeState, text: (english: string, vietnamese: string) => string) {
  return {
    healthy: text("Stable", "Ổn định"),
    warning: text("Check required", "Cần kiểm tra"),
    error: text("Fault", "Có lỗi"),
    waiting: text("Waiting for data", "Chờ dữ liệu"),
  }[state];
}

function activeSignalIssue(
  diagnostics: HardwareDiagnostic[],
  signalIds: string[],
): HardwareDiagnostic | undefined {
  return diagnostics.find((item) => item.signal_id && signalIds.includes(item.signal_id));
}

export function HardwareGraphPage() {
  const { language, locale, text } = useI18n();
  const { snapshot, hardwareProfile, streamStatus, reconnect } = useHardwareMonitor();
  const [viewMode, setViewMode] = useState<"design" | "live">(
    import.meta.env.MODE === "test" ? "design" : "live",
  );
  const [componentQuery, setComponentQuery] = useState("");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
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
    yellow: text("yellow", "vàng"),
    green: text("green", "xanh lá"),
    blue: text("blue", "xanh dương"),
    black: text("black", "đen"),
    red: text("red", "đỏ"),
    white: text("white", "trắng"),
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
      pin: compatibility.reported_profile_id ?? text("No profile reported by the board", "Chưa nhận profile từ board"),
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
          : text("Waiting for the HARDWARE_PROFILE heartbeat; flash the latest firmware if this persists.", "Chờ heartbeat HARDWARE_PROFILE; nếu chờ lâu, hãy nạp firmware mới nhất.")),
    },
    {
      id: "sensor-identity",
      label: text("Sensor chip", "Chip cảm biến"),
      pin: hardwareProfile
        ? `${sensor?.model ?? "Power monitor"} · ${hardwareProfile.firmware.sensor.i2c_address}`
        : text("Loading sensor identity from profile", "Đang tải định danh cảm biến từ profile"),
      state: sensorMismatch
        ? "error"
        : compatibility.sensor_identity_verified
          ? "healthy"
          : "waiting",
      detail:
        sensorMismatch?.action ??
        (compatibility.sensor_identity_verified
          ? text(`${sensor?.model ?? "Sensor"} matches the identity declared in the profile.`, `${sensor?.model ?? "Cảm biến"} đã khớp identity khai báo trong profile.`)
          : text("Waiting for firmware identity read; an incorrect module will be blocked here.", "Chờ firmware đọc identity; module gắn nhầm sẽ bị chặn tại đây.")),
    },
    {
      id: "reported-model",
      label: text("Reported BOM", "BOM đang báo"),
      pin: compatibility.reported_hardware_model_id ?? text("No model reported by the board", "Chưa nhận model từ board"),
      state: firmwareMismatch
        ? "error"
        : compatibility.reported_hardware_model_id === compatibility.expected_hardware_model_id
          ? "healthy"
          : "waiting",
      detail:
        compatibility.reported_hardware_model_id === compatibility.expected_hardware_model_id
          ? text(`Matches ${hardwareIdentity || "the selected hardware profile"}.`, `Khớp ${hardwareIdentity || "hardware profile đang chọn"}.`)
          : text(`Expected ${compatibility.expected_hardware_model_id}.`, `Cần ${compatibility.expected_hardware_model_id}.`),
    },
  ];
  const i2cSharedSignals = ["i2c_bus", "sensor_identity"];
  const signalChecks: SignalCheck[] = [
    {
      id: "sda",
      label: "SDA",
      pin: hardwareProfile ? `I²C SDA → GPIO${gpio("i2c_sda")}` : text("Loading from profile", "Đang tải từ profile"),
      state: activeSignalIssue(activeDiagnostics, ["i2c_sda", ...i2cSharedSignals])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["i2c_sda", ...i2cSharedSignals])?.action ??
        (signalHealth.i2c_verified
          ? text(`ACK, chip ID, and data from ${sensor?.model ?? "the sensor"} are valid in the latest packet.`, `ACK, chip ID và dữ liệu từ ${sensor?.model ?? "cảm biến"} hợp lệ ở gói mới nhất.`)
          : text("Waiting for the power monitor to pass ACK and chip ID checks.", "Chờ power monitor vượt qua kiểm tra ACK và chip ID.")),
    },
    {
      id: "scl",
      label: "SCL",
      pin: hardwareProfile ? `I²C SCL → GPIO${gpio("i2c_scl")}` : text("Loading from profile", "Đang tải từ profile"),
      state: activeSignalIssue(activeDiagnostics, ["i2c_scl", ...i2cSharedSignals])
        ? "error"
        : signalHealth.i2c_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["i2c_scl", ...i2cSharedSignals])?.action ??
        (signalHealth.i2c_verified
          ? text("Bus idle is HIGH and the latest I²C transaction is valid.", "Bus idle HIGH và giao dịch I²C hợp lệ ở gói mới nhất.")
          : text("Waiting for the power monitor to pass the I²C bus check.", "Chờ power monitor vượt qua kiểm tra bus I²C.")),
    },
    {
      id: "encoder-a",
      label: "Encoder A",
      pin: hardwareProfile ? `${wireForControllerPin("encoder_a") ? text(`Wire ${wireForControllerPin("encoder_a")}`, `Dây ${wireForControllerPin("encoder_a")}`) : "Encoder A"} → GPIO${gpio("encoder_a")}` : text("Loading from profile", "Đang tải từ profile"),
      state: activeSignalIssue(activeDiagnostics, ["encoder_a", "encoder_bus"])
        ? "error"
        : signalHealth.encoder_a_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["encoder_a", "encoder_bus"])?.action ??
        (signalHealth.encoder_a_verified
          ? text("Signal edges were detected during the latest motor run.", "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất.")
          : text("Can only be verified while the motor runs in a supervised test.", "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát.")),
    },
    {
      id: "encoder-b",
      label: "Encoder B",
      pin: hardwareProfile ? `${wireForControllerPin("encoder_b") ? text(`Wire ${wireForControllerPin("encoder_b")}`, `Dây ${wireForControllerPin("encoder_b")}`) : "Encoder B"} → GPIO${gpio("encoder_b")}` : text("Loading from profile", "Đang tải từ profile"),
      state: activeSignalIssue(activeDiagnostics, ["encoder_b", "encoder_bus"])
        ? "error"
        : signalHealth.encoder_b_verified
          ? "healthy"
          : "waiting",
      detail:
        activeSignalIssue(activeDiagnostics, ["encoder_b", "encoder_bus"])?.action ??
        (signalHealth.encoder_b_verified
          ? text("Signal edges were detected during the latest motor run.", "Đã thấy cạnh tín hiệu trong lần motor chạy gần nhất.")
          : text("Can only be verified while the motor runs in a supervised test.", "Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát.")),
    },
  ];
  const deviceLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const limits = snapshot?.hardware.limits ?? hardwareProfile?.safety;
  const busVoltage = measurements?.bus_voltage_v;
  const voltageSafe = typeof busVoltage === "number" && limits
    ? busVoltage >= limits.min_bus_voltage_v && busVoltage <= limits.max_bus_voltage_v
    : false;
  const motorControlReady = Boolean(
    deviceLive
    && telemetry
    && voltageSafe
    && compatibility.firmware_profile_verified
    && compatibility.sensor_identity_verified
    && !activeDiagnostics.some((item) => item.severity === "error"),
  );
  const motorControlReason = !deviceLive
    ? text("The backend has not received live telemetry from ESP32.", "Backend chưa nhận telemetry realtime từ ESP32.")
    : !compatibility.firmware_profile_verified
      ? text("Firmware does not match the selected hardware profile.", "Firmware chưa khớp hardware profile đang chọn.")
      : !compatibility.sensor_identity_verified
        ? text("INA226 has not passed the identity check.", "INA226 chưa vượt qua kiểm tra identity.")
        : !voltageSafe
          ? text(`Motor supply must be within ${limits?.min_bus_voltage_v ?? "--"}–${limits?.max_bus_voltage_v ?? "--"} V.`, `Nguồn motor phải nằm trong ${limits?.min_bus_voltage_v ?? "--"}–${limits?.max_bus_voltage_v ?? "--"} V.`)
          : text("A critical hardware fault is active; resolve it before running the motor.", "Đang có lỗi phần cứng mức nghiêm trọng; xử lý lỗi trước khi chạy motor.");

  const componentPresentation = {
    controller: { icon: Cpu, tone: "blue" },
    sensor: { icon: Activity, tone: "teal" },
    power_monitor: { icon: Activity, tone: "teal" },
    driver: { icon: Zap, tone: "violet" },
    motor_driver: { icon: Zap, tone: "violet" },
    actuator: { icon: RotateCcw, tone: "orange" },
    power: { icon: Gauge, tone: "orange" },
    power_supply: { icon: Gauge, tone: "orange" },
    compute: { icon: Cpu, tone: "blue" },
    communication: { icon: Cable, tone: "teal" },
    other: { icon: Activity, tone: "teal" },
  } as const;
  const nodes = hardwareProfile ? hardwareProfile.components.map((component) => {
    const detail = component.component_id === hardwareProfile.roles.controller
      ? deviceLive
        ? `${snapshot?.connection.port} · ${snapshot?.connection.baud_rate} baud`
        : text("No device transport", "Chưa nhận device transport")
      : component.component_id === hardwareProfile.roles.power_monitor
        ? `${valueOrDash(measurements?.bus_voltage_v)} V · ${valueOrDash(measurements?.current_ma, 1)} mA`
        : component.component_id === hardwareProfile.roles.motor_driver
          ? measurements
            ? `${measurements.driver_enabled ? text("On", "Đang bật") : text("Off", "Đang tắt")} · PWM ${measurements.pwm_percent}%`
            : text("Waiting for telemetry", "Chờ telemetry")
          : component.component_id === hardwareProfile.roles.actuator
            ? measurements?.motor_rpm == null
              ? text("RPM waiting for encoder calibration", "RPM chờ hiệu chuẩn encoder")
              : `${valueOrDash(measurements.motor_rpm, 0)} RPM`
            : component.component_id === hardwareProfile.roles.power
              ? text("System power supply", "Nguồn cấp cho hệ thống")
              : text(`${component.capabilities.length} declared capabilities`, `${component.capabilities.length} khả năng đã khai báo`);
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
  const normalizedComponentQuery = componentQuery.trim().toLocaleLowerCase("vi");
  const filteredNodes = nodes.filter((node) =>
    !normalizedComponentQuery
    || node.name.toLocaleLowerCase("vi").includes(normalizedComponentQuery)
    || node.type.toLocaleLowerCase("vi").includes(normalizedComponentQuery),
  );
  const selectedNode = nodes.find((node) => node.id === selectedComponentId) ?? nodes[0];
  const selectedPosition = selectedNode ? nodes.findIndex((node) => node.id === selectedNode.id) : -1;
  const selectedComponent = hardwareProfile?.components.find(
    (component) => component.component_id === selectedNode?.id,
  );
  const selectedConnections = hardwareProfile?.connections.filter(
    (connection) => connection.from.component_id === selectedNode?.id
      || connection.to.component_id === selectedNode?.id,
  ) ?? [];
  const previousNode = selectedPosition > 0 ? nodes[selectedPosition - 1] : undefined;
  const nextNode = selectedPosition >= 0 ? nodes[selectedPosition + 1] : undefined;
  const SelectedComponentIcon = selectedNode?.icon;
  const profileLabel = `Profile ${snapshot?.hardware.profile_schema_version ?? hardwareProfile?.schema_version ?? "--"} · ${snapshot?.hardware.profile_id ?? hardwareProfile?.profile_id ?? text("loading", "đang tải")}`;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={viewMode === "design" ? text("Three-wheel vehicle · real-time monitor", "Xe 2 motor · realtime monitor") : text("Real-time hardware doctor", "Bác sĩ phần cứng realtime")}
        title={text("Hardware Graph", "Sơ đồ phần cứng")}
        description={viewMode === "design"
          ? text("Monitor wheel RPM, PID, signals, alerts, and logs in one screen; measurements only appear when firmware sends the correct contract.", "Theo dõi hai RPM, PID, tín hiệu, cảnh báo và log trong cùng một màn hình; số đo chỉ hiện khi firmware gửi đúng contract.")
          : text("Monitor the live single-motor rig, inspect ESP32 logs, and get troubleshooting guidance without opening CMD.", "Theo dõi rig một motor đang chạy, xem log từ ESP32 và nhận hướng dẫn xử lý lỗi mà không cần mở CMD.")}
        action={
          <span className={`status-pill status-pill--${deviceLive ? "healthy" : "warning"}`}>
            {deviceLive ? <CheckCircle2 size={15} /> : <CircleOff size={15} />}
            {deviceLive
              ? text(`${snapshot?.connection.port} is live`, `${snapshot?.connection.port} đang live`)
              : viewMode === "design" ? text("Monitor waiting for backend", "Monitor chờ backend") : text(`Waiting for ${controller?.model ?? "hardware profile"}`, `Đang chờ ${controller?.model ?? "hardware profile"}`)}
          </span>
        }
      />

      <nav className="hardware-mode-switch" aria-label={text("Select hardware architecture", "Chọn kiến trúc phần cứng")}>
        <button
          type="button"
          className={viewMode === "design" ? "is-active" : ""}
          onClick={() => setViewMode("design")}
          aria-pressed={viewMode === "design"}
        >
          <span className="hardware-mode-switch__icon"><RotateCcw size={18} /></span>
          <span><strong>{text("Three-wheel vehicle · Monitor", "Xe 2 motor · Monitor")}</strong><small>{text("Telemetry, PID, alerts, and logs", "Telemetry, PID, cảnh báo và log")}</small></span>
          <span className={`hardware-mode-switch__dot${deviceLive ? " is-live" : ""}`} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={viewMode === "live" ? "is-active" : ""}
          onClick={() => setViewMode("live")}
          aria-pressed={viewMode === "live"}
        >
          <span className="hardware-mode-switch__icon"><Activity size={18} /></span>
          <span><strong>{text("Single-motor rig · live", "Rig 1 motor · live")}</strong><small>{text("COM, telemetry, and physical logs", "COM, telemetry và log thật")}</small></span>
          <span className={`hardware-mode-switch__dot${deviceLive ? " is-live" : ""}`} aria-hidden="true" />
        </button>
      </nav>

      {viewMode === "design" ? <DualMotorArchitecture /> : <>

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
            {deviceLive ? text("Data is updating in real time", "Dữ liệu đang cập nhật realtime") : text("No live telemetry stream", "Chưa có luồng telemetry trực tiếp")}
          </strong>
          <p>
            {streamStatus !== "live"
              ? text("The UI is reconnecting to the backend. Keep the Backend window running.", "UI đang thử nối lại backend. Hãy giữ cửa sổ Backend đang chạy.")
              : localizeConnectionMessage(snapshot?.connection, language)}
          </p>
        </div>
        <span className="connection-banner__meta">
          {text("Last packet:", "Gói cuối:")} {timeLabel(snapshot?.connection.last_seen_at ?? null, locale)}
        </span>
        {!deviceLive && <button className="button button--secondary connection-banner__action" type="button" onClick={reconnect}><RefreshCw size={15} /> {text("Reconnect", "Thử nối lại")}</button>}
      </section>

      <KeyboardMotorControl
        enabled={motorControlReady}
        maxPwmPercent={limits?.max_pwm_percent ?? 80}
        defaultPwmPercent={hardwareProfile?.firmware.default_motor_test_pwm_percent ?? 50}
        disabledReason={motorControlReason}
      />

      <section className="card graph-card">
        <div className="panel__header graph-card__header">
          <div className="graph-card__heading">
            <p className="eyebrow">BOM · {text("Overview", "Tổng quan")}</p>
            <h2 className="graph-card__title">{nodes.length} {text("components monitored", "linh kiện đang theo dõi")}</h2>
            <p className="graph-card__summary">
              {text("Search and select a component to inspect its state and connections.", "Tìm và chọn một linh kiện để xem trạng thái và kết nối.")}
            </p>
          </div>
          <span className={`status-pill status-pill--${snapshot?.health.status ?? "warning"}`}>
            {activeDiagnostics.length} {text("open faults", "lỗi đang mở")}
          </span>
        </div>
        <div className="hardware-explorer">
          <aside className="hardware-index" aria-label={text("BOM component list", "Danh sách linh kiện trong BOM")}>
            <label className="hardware-search">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={componentQuery}
                onChange={(event) => {
                  const nextQuery = event.target.value;
                  const normalizedQuery = nextQuery.trim().toLocaleLowerCase("vi");
                  setComponentQuery(nextQuery);
                  if (!normalizedQuery) return;
                  const selectedStillMatches = selectedNode
                    && (selectedNode.name.toLocaleLowerCase("vi").includes(normalizedQuery)
                      || selectedNode.type.toLocaleLowerCase("vi").includes(normalizedQuery));
                  if (!selectedStillMatches) {
                    const firstMatch = nodes.find((node) =>
                      node.name.toLocaleLowerCase("vi").includes(normalizedQuery)
                      || node.type.toLocaleLowerCase("vi").includes(normalizedQuery),
                    );
                    if (firstMatch) setSelectedComponentId(firstMatch.id);
                  }
                }}
                placeholder={text("Search by component name or type", "Tìm tên hoặc loại linh kiện")}
                aria-label={text("Search components", "Tìm linh kiện")}
              />
            </label>
            <div className="hardware-index__meta" aria-live="polite">
              <strong>{filteredNodes.length}</strong> / {nodes.length} {text("components", "linh kiện")}
            </div>
            <ul className="hardware-index__list">
              {filteredNodes.map(({ id, name, type, icon: Icon, tone, state }) => {
                const position = nodes.findIndex((node) => node.id === id) + 1;
                return (
                  <li key={id}>
                    <button
                      className={`hardware-index__item${selectedNode?.id === id ? " is-selected" : ""}`}
                      type="button"
                      onClick={() => setSelectedComponentId(id)}
                      aria-pressed={selectedNode?.id === id}
                      aria-label={`${position}. ${name}, ${stateLabel(state, text)}`}
                    >
                      <span className="hardware-index__number">{position}</span>
                      <span className={`hardware-index__icon hardware-index__icon--${tone}`}>
                        <Icon size={17} aria-hidden="true" />
                      </span>
                      <span className="hardware-index__copy">
                        <small>{type}</small>
                        <strong title={name}>{name}</strong>
                      </span>
                      <span className={`hardware-index__health hardware-index__health--${state}`} title={stateLabel(state, text)} />
                    </button>
                  </li>
                );
              })}
              {filteredNodes.length === 0 && (
                <li className="hardware-index__empty">{text("No matching components.", "Không có linh kiện phù hợp.")}</li>
              )}
            </ul>
          </aside>

          {selectedNode && SelectedComponentIcon && (
            <article className="hardware-detail" data-testid="hardware-detail" aria-live="polite">
              <div className="hardware-detail__header">
                <span className={`hardware-detail__icon hardware-detail__icon--${selectedNode.tone}`}>
                  <SelectedComponentIcon size={22} aria-hidden="true" />
                </span>
                <div className="hardware-detail__heading">
                  <small>{selectedNode.type} · {selectedPosition + 1}/{nodes.length}</small>
                  <h3 title={selectedNode.name}>{selectedNode.name}</h3>
                </div>
                <span className={`status-pill status-pill--${selectedNode.state === "waiting" ? "warning" : selectedNode.state}`}>
                  {stateLabel(selectedNode.state, text)}
                </span>
              </div>

              <div className="hardware-detail__runtime">
                <span>{text("Current reading", "Thông số hiện tại")}</span>
                <strong>{selectedNode.detail}</strong>
              </div>

              <dl className="hardware-detail__facts">
                <div><dt>Component ID</dt><dd title={selectedNode.id}>{selectedNode.id}</dd></div>
                <div><dt>{text("Connections", "Kết nối")}</dt><dd>{selectedConnections.length} {text("paths", "đường")}</dd></div>
                <div><dt>{text("Declared pins", "Chân khai báo")}</dt><dd>{selectedComponent?.pins.length ?? 0} {text("pins", "chân")}</dd></div>
              </dl>

              <div className="hardware-detail__capabilities">
                <span>{text("Capabilities", "Khả năng")}</span>
                <div>
                  {(selectedComponent?.capabilities.length
                    ? selectedComponent.capabilities.slice(0, 3)
                    : [text("Not declared", "Chưa khai báo")]
                  ).map((capability) => <small key={capability}>{capability}</small>)}
                  {(selectedComponent?.capabilities.length ?? 0) > 3 && (
                    <small>+{(selectedComponent?.capabilities.length ?? 0) - 3}</small>
                  )}
                </div>
              </div>

              <div className="hardware-detail__path" aria-label={text("Position in signal flow", "Vị trí trong luồng tín hiệu")}>
                <span title={previousNode?.name}>{previousNode?.name ?? text("Start", "Điểm bắt đầu")}</span>
                <ArrowRight size={14} aria-hidden="true" />
                <strong>{text("Selected", "Đang chọn")}</strong>
                <ArrowRight size={14} aria-hidden="true" />
                <span title={nextNode?.name}>{nextNode?.name ?? text("End", "Điểm kết thúc")}</span>
              </div>
            </article>
          )}
        </div>
        <div className="graph-legend">
          <span>
            <i
              className={`legend-dot${deviceLive ? " legend-dot--live" : " legend-dot--offline"}`}
            />
            {deviceLive ? "Live telemetry" : text("Waiting for data", "Đang chờ dữ liệu")}
          </span>
          <span className="graph-legend__profile" title={profileLabel}>{profileLabel}</span>
        </div>
      </section>

      <WiringGuide
        profile={hardwareProfile}
        selectedComponentId={selectedNode?.id}
        onSelectComponent={setSelectedComponentId}
      />

      <section className="card signal-card" aria-labelledby="compatibility-title">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Hardware fingerprint</p>
            <h2 id="compatibility-title">{text("Firmware and BOM compatibility", "Đối chiếu firmware với BOM")}</h2>
          </div>
          <ShieldCheck size={21} />
        </div>
        <p className="signal-card__intro">
          {text("NeXus verifies the firmware declaration and chip identity before trusting measurements. Firmware and sensor mismatches are reported separately.", "NeXus kiểm tra firmware khai báo đúng bộ phần cứng và xác minh identity của chip trước khi tin số đo. Sai firmware và sai cảm biến được báo thành hai lỗi riêng.")}
        </p>
        <div className="signal-grid compatibility-grid" aria-live="polite">
          {compatibilityChecks.map((check) => (
            <article className={`signal-item signal-item--${check.state}`} key={check.id}>
              <span className={`node-state node-state--${check.state}`}>
                {stateLabel(check.state, text)}
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
            <h2 id="signal-health-title">{text("Signal wire health", "Tình trạng dây tín hiệu")}</h2>
          </div>
          <Cable size={21} />
        </div>
        <p className="signal-card__intro">
          {text("SDA/SCL are checked on every packet. Encoders are verified only while the motor is commanded to run; waiting does not mean the wire is faulty.", "SDA/SCL được kiểm tra ở từng gói. Encoder chỉ được xác nhận khi motor thực sự được lệnh chạy; trạng thái chờ không có nghĩa là dây đã hỏng.")}
        </p>
        <div className="signal-grid" aria-live="polite">
          {signalChecks.map((signal) => (
            <article className={`signal-item signal-item--${signal.state}`} key={signal.id}>
              <span className={`node-state node-state--${signal.state}`}>
                {stateLabel(signal.state, text)}
              </span>
              <strong>{signal.label}</strong>
              <small>{signal.pin}</small>
              <p>{signal.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="monitor-grid">
        <HardwareDiagnosticsPanel mode="single" />
        <HardwareLiveLog mode="single" />
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Latest packet</p><h2>{text("Physical telemetry from the board", "Telemetry thật từ board")}</h2></div><Gauge size={22} /></div>
          <dl className="detail-list">
            <div><dt>Bus voltage</dt><dd>{valueOrDash(measurements?.bus_voltage_v, 3)} V</dd></div>
            <div><dt>Current</dt><dd>{valueOrDash(measurements?.current_ma, 2)} mA</dd></div>
            <div><dt>Power</dt><dd>{valueOrDash(measurements?.power_mw, 2)} mW</dd></div>
            <div><dt>Driver / PWM</dt><dd>{measurements ? `${measurements.driver_enabled ? "ON" : "OFF"} / ${measurements.pwm_percent}%` : "--"}</dd></div>
            <div><dt>Sequence</dt><dd>{telemetry?.sequence ?? "--"}</dd></div>
          </dl>
        </article>
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">MVP guardrails</p><h2>{text("Locked hardware baseline", "Bộ phần cứng đã khóa")}</h2></div><Activity size={22} /></div>
          <dl className="detail-list">
            <div><dt>Mainboard</dt><dd>{controller?.model ?? "--"}</dd></div>
            <div><dt>{text("Sensor", "Cảm biến")}</dt><dd>{sensor ? `${sensor.model} · SDA GPIO${gpio("i2c_sda")} / SCL GPIO${gpio("i2c_scl")}` : "--"}</dd></div>
            <div><dt>Driver</dt><dd>{driver ? `${driver.model} · ENA ${gpio("motor_enable")} / IN1 ${gpio("motor_in1")} / IN2 ${gpio("motor_in2")}` : "--"}</dd></div>
            <div><dt>Motor</dt><dd>{actuator ? `${actuator.model} · Encoder A${gpio("encoder_a")} / B${gpio("encoder_b")}` : "--"}</dd></div>
            <div><dt>{text("Power", "Nguồn")}</dt><dd>{power?.model ?? "--"}</dd></div>
          </dl>
        </article>
      </section>
      </>}
    </div>
  );
}
