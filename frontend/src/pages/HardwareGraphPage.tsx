import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Cable,
  CheckCircle2,
  CircleOff,
  ChevronDown,
  ChevronsDown,
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
import { useLayoutEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { WiringGuide } from "../components/WiringGuide";
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

interface TelemetryLogPayload {
  sequence?: number;
  device_id?: string;
  measurements?: {
    bus_voltage_v?: number | null;
    current_ma?: number | null;
    power_mw?: number | null;
    pwm_percent?: number | null;
    driver_enabled?: boolean | null;
    motor_rpm?: number | null;
  };
}

interface LogPresentation {
  title: string;
  summary: string;
  raw: string;
  telemetry: TelemetryLogPayload | null;
}

function logPresentation(item: LiveLog): LogPresentation {
  const message = item.message.trim();
  if (message.startsWith("{")) {
    try {
      const payload = JSON.parse(message) as TelemetryLogPayload;
      if (payload.measurements && typeof payload.measurements === "object") {
        return {
          title: `Telemetry${payload.sequence == null ? "" : ` #${payload.sequence}`}`,
          summary: payload.device_id ? `Thiết bị ${payload.device_id}` : "Gói đo mới từ thiết bị",
          raw: JSON.stringify(payload, null, 2),
          telemetry: payload,
        };
      }
    } catch {
      // Dòng JSON chưa hoàn chỉnh vẫn được giữ nguyên để người dùng kiểm tra.
    }
  }

  if (message.includes("[HARDWARE_PROFILE]")) {
    const profileId = message.match(/profile_id=([^\s]+)/)?.[1];
    return {
      title: "Cấu hình phần cứng đã xác nhận",
      summary: profileId ? `Profile ${profileId}` : "Firmware đã gửi hardware fingerprint",
      raw: message,
      telemetry: null,
    };
  }

  if (message.includes("[SIGNAL_MONITOR_READY]")) {
    return {
      title: "Bộ giám sát dây tín hiệu đã sẵn sàng",
      summary: "SDA/SCL được kiểm tra ở từng mẫu; encoder A/B được kiểm tra khi motor chạy.",
      raw: message,
      telemetry: null,
    };
  }

  return {
    title: {
      error: "Lỗi phần cứng",
      warning: "Cảnh báo cần kiểm tra",
      telemetry: "Telemetry",
      info: "Thông tin hệ thống",
    }[item.level],
    summary: message,
    raw: message,
    telemetry: null,
  };
}

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
  const [componentQuery, setComponentQuery] = useState("");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [pausedLogs, setPausedLogs] = useState<LiveLog[] | null>(null);
  const [hiddenBefore, setHiddenBefore] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const [logLevel, setLogLevel] = useState<"all" | LiveLog["level"]>("all");
  const [followLatest, setFollowLatest] = useState(true);
  const terminalRef = useRef<HTMLDivElement>(null);
  const userLogScrollRef = useRef(false);
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
  const latestVisibleLog = visibleLogs.at(-1);

  useLayoutEffect(() => {
    if (!pausedLogs && followLatest && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [latestVisibleLog?.id, pausedLogs, followLatest, logLevel, logQuery]);

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
  const profileLabel = `Profile ${snapshot?.hardware.profile_schema_version ?? hardwareProfile?.schema_version ?? "--"} · ${snapshot?.hardware.profile_id ?? hardwareProfile?.profile_id ?? "đang tải"}`;

  const jumpToLatest = () => {
    userLogScrollRef.current = false;
    setFollowLatest(true);
    requestAnimationFrame(() => {
      if (terminalRef.current) {
        terminalRef.current.scrollTo({ top: terminalRef.current.scrollHeight, behavior: "smooth" });
      }
    });
  };
  const handleLogScroll = () => {
    if (!terminalRef.current || !userLogScrollRef.current) return;
    const distanceFromBottom = terminalRef.current.scrollHeight
      - terminalRef.current.scrollTop
      - terminalRef.current.clientHeight;
    const isAtLatest = distanceFromBottom <= 32;
    setFollowLatest(isAtLatest);
    if (isAtLatest) userLogScrollRef.current = false;
  };
  const togglePause = () => setPausedLogs((current) => {
    if (current) {
      userLogScrollRef.current = false;
      setFollowLatest(true);
      return null;
    }
    return [...(snapshot?.logs ?? [])];
  });
  const clearVisibleLogs = () => {
    userLogScrollRef.current = false;
    setHiddenBefore(new Date().toISOString());
    setFollowLatest(true);
  };
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
            <p className="eyebrow">BOM · Tổng quan</p>
            <h2 className="graph-card__title">{nodes.length} linh kiện đang theo dõi</h2>
            <p className="graph-card__summary">
              Tìm và chọn một linh kiện để xem trạng thái và kết nối.
            </p>
          </div>
          <span className={`status-pill status-pill--${snapshot?.health.status ?? "warning"}`}>
            {activeDiagnostics.length} lỗi đang mở
          </span>
        </div>
        <div className="hardware-explorer">
          <aside className="hardware-index" aria-label="Danh sách linh kiện trong BOM">
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
                placeholder="Tìm tên hoặc loại linh kiện"
                aria-label="Tìm linh kiện"
              />
            </label>
            <div className="hardware-index__meta" aria-live="polite">
              <strong>{filteredNodes.length}</strong> / {nodes.length} linh kiện
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
                      aria-label={`${position}. ${name}, ${stateLabel(state)}`}
                    >
                      <span className="hardware-index__number">{position}</span>
                      <span className={`hardware-index__icon hardware-index__icon--${tone}`}>
                        <Icon size={17} aria-hidden="true" />
                      </span>
                      <span className="hardware-index__copy">
                        <small>{type}</small>
                        <strong title={name}>{name}</strong>
                      </span>
                      <span className={`hardware-index__health hardware-index__health--${state}`} title={stateLabel(state)} />
                    </button>
                  </li>
                );
              })}
              {filteredNodes.length === 0 && (
                <li className="hardware-index__empty">Không có linh kiện phù hợp.</li>
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
                  {stateLabel(selectedNode.state)}
                </span>
              </div>

              <div className="hardware-detail__runtime">
                <span>Thông số hiện tại</span>
                <strong>{selectedNode.detail}</strong>
              </div>

              <dl className="hardware-detail__facts">
                <div><dt>Component ID</dt><dd title={selectedNode.id}>{selectedNode.id}</dd></div>
                <div><dt>Kết nối</dt><dd>{selectedConnections.length} đường</dd></div>
                <div><dt>Chân khai báo</dt><dd>{selectedComponent?.pins.length ?? 0} chân</dd></div>
              </dl>

              <div className="hardware-detail__capabilities">
                <span>Khả năng</span>
                <div>
                  {(selectedComponent?.capabilities.length
                    ? selectedComponent.capabilities.slice(0, 3)
                    : ["Chưa khai báo"]
                  ).map((capability) => <small key={capability}>{capability}</small>)}
                  {(selectedComponent?.capabilities.length ?? 0) > 3 && (
                    <small>+{(selectedComponent?.capabilities.length ?? 0) - 3}</small>
                  )}
                </div>
              </div>

              <div className="hardware-detail__path" aria-label="Vị trí trong luồng tín hiệu">
                <span title={previousNode?.name}>{previousNode?.name ?? "Điểm bắt đầu"}</span>
                <ArrowRight size={14} aria-hidden="true" />
                <strong>Đang chọn</strong>
                <ArrowRight size={14} aria-hidden="true" />
                <span title={nextNode?.name}>{nextNode?.name ?? "Điểm kết thúc"}</span>
              </div>
            </article>
          )}
        </div>
        <div className="graph-legend">
          <span>
            <i
              className={`legend-dot${deviceLive ? " legend-dot--live" : " legend-dot--offline"}`}
            />
            {deviceLive ? "Live telemetry" : "Đang chờ dữ liệu"}
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
            <div className="terminal-card__title">
              <span className="terminal-card__icon"><TerminalSquare size={18} /></span>
              <span>
                <strong>ESP32 Live Log</strong>
                <small className={pausedLogs ? "is-paused" : followLatest ? "is-following" : "is-browsing"}>
                  <i aria-hidden="true" />
                  {pausedLogs
                    ? "Đã tạm dừng"
                    : followLatest
                      ? "Đang theo dõi log mới nhất"
                      : "Bạn đang xem log cũ"}
                </small>
              </span>
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
            <span className="terminal-toolbar__count"><strong>{visibleLogs.length}</strong> bản ghi</span>
          </div>
          <div className="terminal-card__meta">
            <span>Đang lưu <strong title={savedLogName}>{savedLogName}</strong></span>
            {latestVisibleLog && <span>Mới nhất lúc <strong>{timeLabel(latestVisibleLog.occurred_at)}</strong></span>}
          </div>
          <div
            className="terminal-feed"
            ref={terminalRef}
            role="log"
            aria-label="Log realtime từ ESP32"
            aria-live="off"
            tabIndex={0}
            onScroll={handleLogScroll}
            onWheel={() => { userLogScrollRef.current = true; }}
            onTouchStart={() => { userLogScrollRef.current = true; }}
            onPointerDown={(event) => {
              if (event.target === event.currentTarget) userLogScrollRef.current = true;
            }}
            onKeyDown={(event) => {
              if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(event.key)) {
                userLogScrollRef.current = true;
              }
            }}
          >
            {visibleLogs.length === 0 && (
              <p className="terminal-empty">Log từ firmware sẽ hiện tại đây ngay khi ESP32 gửi dữ liệu.</p>
            )}
            {visibleLogs.map((item, index) => {
              const presentation = logPresentation(item);
              const metrics = presentation.telemetry?.measurements;
              return (
                <article
                  className={`terminal-line terminal-line--${item.level}`}
                  data-latest={index === visibleLogs.length - 1 ? "true" : undefined}
                  key={item.id}
                >
                  <div className="terminal-line__meta">
                    <time>{timeLabel(item.occurred_at)}</time>
                    <span>{item.level === "telemetry" ? "Telemetry" : item.level === "info" ? "Thông tin" : item.level === "warning" ? "Cảnh báo" : "Lỗi"}</span>
                  </div>
                  <div className="terminal-line__content">
                    <div className="terminal-line__heading">
                      <strong>{presentation.title}</strong>
                      <small>{item.source === "firmware" ? "Firmware" : "Backend"}</small>
                    </div>
                    {metrics ? (
                      <div className="terminal-metrics" aria-label={`Số đo ${presentation.title}`}>
                        <span><small>Điện áp</small><strong>{valueOrDash(metrics.bus_voltage_v, 3)} V</strong></span>
                        <span><small>Dòng</small><strong>{valueOrDash(metrics.current_ma, 1)} mA</strong></span>
                        <span><small>Công suất</small><strong>{valueOrDash(metrics.power_mw, 1)} mW</strong></span>
                        <span><small>Motor</small><strong>{metrics.driver_enabled ? `Bật · ${metrics.pwm_percent ?? 0}%` : "Tắt"}</strong></span>
                      </div>
                    ) : (
                      <p>{presentation.summary}</p>
                    )}
                    <details className="terminal-raw">
                      <summary><ChevronDown size={14} /> Xem dữ liệu gốc</summary>
                      <pre>{presentation.raw}</pre>
                    </details>
                  </div>
                </article>
              );
            })}
            {!followLatest && visibleLogs.length > 0 && !pausedLogs && (
              <button className="terminal-jump" type="button" onClick={jumpToLatest}>
                <ChevronsDown size={16} />
                Về log mới nhất
              </button>
            )}
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
