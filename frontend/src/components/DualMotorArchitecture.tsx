import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  Cable,
  CircleOff,
  CheckCircle2,
  ChevronDown,
  CircuitBoard,
  Eye,
  FileCode2,
  Gamepad2,
  Gauge,
  GitCompareArrows,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { HardwareDiagnosticsPanel } from "./HardwareDiagnosticsPanel";
import { HardwareLiveLog } from "./HardwareLiveLog";
import {
  DUAL_MOTOR_ARCHITECTURE,
  WIRE_COLOR_LABELS,
  WIRING_SCOPE_LABELS,
  type WiringScope,
} from "../data/dualMotorArchitecture";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";

const architecture = DUAL_MOTOR_ARCHITECTURE;

const sensorIcons = {
  power: Gauge,
} as const;

const scopes = Object.keys(WIRING_SCOPE_LABELS) as WiringScope[];

interface DualMotorMeasurements {
  bus_voltage_v?: number | null;
  current_ma?: number | null;
  total_current_ma?: number | null;
  power_mw?: number | null;
  rpm_left?: number | null;
  rpm_right?: number | null;
  rpm_rear?: number | null;
  rpm_delta?: number | null;
  pwm_left_percent?: number | null;
  pwm_right_percent?: number | null;
  pwm_rear_percent?: number | null;
  pid_state?: string | null;
  ps2_connected?: boolean;
  ps2_failsafe_active?: boolean;
  ps2_last_packet_age_ms?: number;
  control_mode?: "ps2_manual" | "failsafe";
}

const valueOrDash = (value: number | null | undefined, digits = 0) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

const timeLabel = (value: string | null, locale: string) => value
  ? new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value))
  : "--:--:--";

export function DualMotorArchitecture() {
  const { language, locale, text } = useI18n();
  const { snapshot, streamStatus, reconnect } = useHardwareMonitor();
  const [scope, setScope] = useState<WiringScope>("all");
  const [showDiagram, setShowDiagram] = useState(false);
  const visibleWires = useMemo(
    () => architecture.wires.filter((wire) => scope === "all" || wire.scope === scope),
    [scope],
  );
  const measurements = snapshot?.telemetry?.measurements as DualMotorMeasurements | undefined;
  const deviceLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const hasThreeWheelPacket = measurements?.rpm_left != null
    || measurements?.rpm_right != null
    || measurements?.rpm_rear != null
    || measurements?.pwm_left_percent != null
    || measurements?.pwm_right_percent != null
    || measurements?.pwm_rear_percent != null;
  const signalHealth = snapshot?.signal_health;
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const logFileName = snapshot?.connection.log_file?.split(/[\\/]/).pop() ?? text("no log file", "chưa có file log");
  const scopeLabel = (item: WiringScope) => ({
    all: text("All", "Tất cả"), power: text("Power & safety", "Nguồn & an toàn"), i2c: "I²C",
    ps2: text("PS2 controller", "Tay cầm PS2"), motor1: "Motor 1", motor2: "Motor 2", motor3: "Motor 3",
  })[item];
  const wireColorLabel = (color: keyof typeof WIRE_COLOR_LABELS) => ({
    red: text("Red", "Đỏ"), black: text("Black", "Đen"), green: text("Green", "Xanh lá"), yellow: text("Yellow", "Vàng"), blue: text("Blue", "Xanh dương"), orange: text("Orange", "Cam"), purple: text("Purple", "Tím"), white: text("White", "Trắng"), gray: text("Gray", "Xám"),
  })[color];
  const architectureText = (value: string) => {
    if (language === "vi") return value;
    const translations: Record<string, string> = {
      "Pin LiPo 3S": "3S LiPo battery", "Đế cầu chì 4 A": "4 A fuse holder",
      "Điểm GND chung": "Common GND point", "Đầu thu PS2": "PS2 receiver",
      "Tụ ceramic 100 nF": "100 nF ceramic capacitor", "Chân 1": "Lead 1",
      "Địa chỉ 0x40; A0/A1 OFF": "Address 0x40; A0/A1 OFF", "Không đảo SDA/SCL": "Do not swap SDA/SCL",
      "Bắt đầu ở 3,3 V; không đưa tín hiệu 5 V vào GPIO": "Start at 3.3 V; never feed a 5 V signal into GPIO",
      "Kéo lên 3V3 bằng điện trở 10 kΩ": "Pull up to 3V3 with a 10 kΩ resistor",
      "PWM; tháo jumper EN": "PWM; remove EN jumper", "M+ / đỏ": "M+ / red", "M− / trắng": "M− / white",
      "Encoder VCC / xanh dương": "Encoder VCC / blue", "Encoder GND / đen": "Encoder GND / black",
      "Encoder A / vàng": "Encoder A / yellow", "Encoder B / xanh lá": "Encoder B / green",
      "Hàn ngang hai cực motor nếu có": "Solder across both motor terminals if available",
      "Điện áp, dòng và công suất tổng của ba motor": "Total voltage, current, and power for all three motors",
      "Motor 1 · trước trái": "Motor 1 · front left", "Motor 2 · trước phải": "Motor 2 · front right", "Motor 3 · bánh sau": "Motor 3 · rear wheel",
      "VCC / đỏ": "VCC / red", "GND / đen": "GND / black", "DATA / xanh dương": "DATA / blue",
      "CMD / xanh lá": "CMD / green", "ATTN / cam": "ATTN / orange", "CLK / xám": "CLK / gray",
    };
    return translations[value] ?? value;
  };

  return (
    <div className="architecture-stack" data-testid="dual-motor-architecture">
      <section className="card architecture-hero" aria-labelledby="architecture-title">
        <div className="architecture-hero__copy">
          <div className="architecture-hero__eyebrow">
            <span className={`status-pill status-pill--${hasThreeWheelPacket ? "healthy" : deviceLive ? "warning" : "error"}`}>
              {hasThreeWheelPacket ? text("Three-motor telemetry · live", "Telemetry 3 motor · live") : deviceLive ? text("Backend live · waiting for three-motor packet", "Backend live · chờ packet 3 motor") : text("Monitor waiting for connection", "Monitor đang chờ kết nối")}
            </span>
            <span>Hardware-as-code {architecture.schemaVersion}</span>
          </div>
          <h2 id="architecture-title">{text("Triangular three-wheel vehicle with PS2 control", "Xe ba bánh tam giác điều khiển bằng tay PS2")}</h2>
          <p>
            {text("ESP32-S3 mixes three motion vectors from the PS2 controller, drives three PWM channels through two L298N modules, and measures each encoder independently. INA219 SEN0291 monitors the shared supply and blocks unsafe motion.", "ESP32-S3 trộn ba vector chuyển động từ tay PS2, điều khiển ba kênh PWM qua hai L298N và đo RPM độc lập từ ba encoder. INA219 SEN0291 giám sát nguồn chung và chặn chuyển động khi không an toàn.")}
          </p>
        </div>
        <div className="architecture-hero__facts" aria-label={text("Architecture summary", "Tóm tắt kiến trúc")}>
          <span><strong>3</strong><small>motor + encoder</small></span>
          <span><strong>2</strong><small>module L298N</small></span>
          <span><strong>350 ms</strong><small>PS2 failsafe</small></span>
        </div>
      </section>

      <section
        className={`connection-banner connection-banner--${hasThreeWheelPacket ? "healthy" : streamStatus === "live" ? "warning" : "error"}`}
        role="status"
        aria-live="polite"
      >
        <span className="connection-banner__icon">
          {hasThreeWheelPacket ? <CheckCircle2 size={20} /> : streamStatus === "live" ? <Activity size={20} /> : <CircleOff size={20} />}
        </span>
        <div>
          <strong>{hasThreeWheelPacket ? text("Three-wheel vehicle is updating in real time", "Xe ba bánh đang cập nhật realtime") : streamStatus === "live" ? text("Backend monitor is ready", "Backend monitor đã sẵn sàng") : text("Cannot connect to backend", "Chưa kết nối được backend")}</strong>
          <p>
            {hasThreeWheelPacket
              ? text("Received RPM, PWM, and PS2 status for all three wheels.", "Đã nhận RPM, PWM và trạng thái tay PS2 cho cả ba bánh.")
              : streamStatus === "live"
                ? text("WebSocket is connected; flash the 3-wheel-ps2 firmware to enable three-wheel measurements.", "WebSocket đã kết nối; hãy nạp firmware 3-wheel-ps2 để mở số đo ba bánh.")
                : text("Open nexus-start-app.cmd to connect WebSocket, telemetry, and log storage.", "Mở nexus-start-app.cmd để kết nối WebSocket, telemetry và file log.")}
          </p>
        </div>
        <span className="connection-banner__meta">{text("Last packet:", "Gói cuối:")} {timeLabel(snapshot?.connection.last_seen_at ?? null, locale)}</span>
        {streamStatus !== "live" && (
          <button className="button button--secondary connection-banner__action" type="button" onClick={reconnect}>
            <RefreshCw size={15} /> {text("Reconnect", "Thử nối lại")}
          </button>
        )}
      </section>

      <section className="card dual-drive" aria-labelledby="drive-balance-title">
        <header className="dual-drive__header">
          <div>
            <p className="eyebrow">{text("120° motion mixer", "Bộ trộn chuyển động 120°")}</p>
            <h2 id="drive-balance-title">{text("Three-wheel control", "Điều khiển ba bánh")}</h2>
            <p>{text("The left joystick controls X/Y, the right joystick rotates the vehicle; SELECT is emergency stop, and losing PS2 signal stops every motor.", "Joystick trái điều khiển X/Y, joystick phải xoay xe; SELECT dừng khẩn và mất tín hiệu PS2 sẽ dừng toàn bộ motor.")}</p>
          </div>
          <span className={`architecture-readiness${hasThreeWheelPacket ? " is-live" : ""}`}>
            {hasThreeWheelPacket ? <CheckCircle2 size={16} /> : <FileCode2 size={16} />}
            {hasThreeWheelPacket ? text("Valid three-motor telemetry", "Telemetry 3 motor hợp lệ") : text("Waiting for 3-wheel-ps2 firmware", "Chờ firmware 3-wheel-ps2")}
          </span>
        </header>

        <div className="dual-drive__flow">
          <article className="wheel-card wheel-card--left">
            <span className="wheel-card__side">L298N #1 · {text("channel A", "kênh A")}</span>
            <div className="wheel-card__icon"><RotateCcw size={26} /></div>
            <h3>{text("Motor 1 · front left", "Motor 1 · trước trái")}</h3>
            <dl>
              <div><dt>RPM</dt><dd>{valueOrDash(measurements?.rpm_left)}</dd></div>
              <div><dt>PWM</dt><dd>{valueOrDash(measurements?.pwm_left_percent)}%</dd></div>
            </dl>
            <small>Encoder A/B → GPIO16 / GPIO17</small>
          </article>

          <div className="pid-core">
            <div className="pid-core__board">
              <CircuitBoard size={22} />
              <span><small>{text("Controller", "Bộ điều khiển")}</small><strong>ESP32-S3 + PS2</strong></span>
            </div>
            <div className="pid-core__delta">
              <GitCompareArrows size={22} />
              <span><small>{text("three-wheel rpm_delta", "rpm_delta ba bánh")}</small><strong>{measurements?.rpm_delta == null ? text("Waiting for data", "Chờ dữ liệu") : `${valueOrDash(measurements.rpm_delta)} RPM`}</strong></span>
              <em>{text("Reserved for later calibration", "Chỉ số để hiệu chỉnh sau")}</em>
            </div>
            <div className="pid-core__loop">
              <Gamepad2 size={17} />
              {measurements?.ps2_connected ? text("PS2 connected", "PS2 đã kết nối") : text("PS2 signal lost", "PS2 đang mất tín hiệu")}
            </div>
          </div>

          <article className="wheel-card wheel-card--right">
            <span className="wheel-card__side">L298N #1 · {text("channel B", "kênh B")}</span>
            <div className="wheel-card__icon"><RotateCcw size={26} /></div>
            <h3>{text("Motor 2 · front right", "Motor 2 · trước phải")}</h3>
            <dl>
              <div><dt>RPM</dt><dd>{valueOrDash(measurements?.rpm_right)}</dd></div>
              <div><dt>PWM</dt><dd>{valueOrDash(measurements?.pwm_right_percent)}%</dd></div>
            </dl>
            <small>Encoder A/B → GPIO4 / GPIO5</small>
          </article>

          <article className="wheel-card wheel-card--rear">
            <span className="wheel-card__side">L298N #2 · {text("channel A", "kênh A")}</span>
            <div className="wheel-card__icon"><RotateCcw size={26} /></div>
            <h3>{text("Motor 3 · rear wheel", "Motor 3 · bánh sau")}</h3>
            <dl>
              <div><dt>RPM</dt><dd>{valueOrDash(measurements?.rpm_rear)}</dd></div>
              <div><dt>PWM</dt><dd>{valueOrDash(measurements?.pwm_rear_percent)}%</dd></div>
            </dl>
            <small>Encoder A/B → GPIO9 / GPIO10</small>
          </article>
        </div>

        <div className="dual-drive__contract">
          <span><Activity size={15} /> {text("Expected API", "API dự kiến")}</span>
          <div>{architecture.expectedTelemetry.map((field) => <code key={field}>{field}</code>)}</div>
        </div>
      </section>

      <section className="architecture-grid" aria-label={text("Diagnostic data sources", "Nguồn dữ liệu chẩn đoán")}>
        <article className="card architecture-panel">
          <header>
            <div><p className="eyebrow">I²C · GPIO1/2</p><h2>{text("INA219 power monitor", "Giám sát nguồn INA219")}</h2></div>
            <Workflow size={21} />
          </header>
          <div className="sensor-list">
            {architecture.i2c.map((sensor) => {
              const Icon = sensorIcons[sensor.icon];
              return (
                <div className="sensor-list__item" key={sensor.name}>
                  <span className="sensor-list__icon"><Icon size={18} /></span>
                  <span><strong>{sensor.name}</strong><small>{architectureText(sensor.purpose)}</small></span>
                  <code>{sensor.address}</code>
                </div>
              );
            })}
          </div>
        </article>

        <article className="card architecture-panel architecture-panel--safety">
          <header>
            <div><p className="eyebrow">{text("Power & protection", "Nguồn & bảo vệ")}</p><h2>{text("LiPo 3S through a safety chain", "LiPo 3S qua một chuỗi an toàn")}</h2></div>
            <BatteryCharging size={21} />
          </header>
          <ol className="power-chain" aria-label={text("12 V power chain", "Chuỗi cấp nguồn 12V")}>
            <li>LiPo 3S</li><li>{text("4 A fuse", "Cầu chì 4 A")}</li><li>Relay</li><li>{text("NC emergency stop", "Nút ngắt NC")}</li><li>INA219</li><li>L298N</li>
          </ol>
          <div className="architecture-warning">
            <ShieldCheck size={18} />
            <p><strong>{text("ESP32 is powered only from USB.", "ESP32 chỉ nhận nguồn từ USB.")}</strong> {text("Never feed 11.1–12.6 V into 3V3/5V; connect every GND to one star point.", "Không đưa 11,1–12,6 V vào chân 3V3/5V; mọi GND quy về một điểm sao.")}</p>
          </div>
        </article>
      </section>

      <section className="card dual-monitor-overview" aria-labelledby="dual-monitor-title">
        <header className="dual-monitor-overview__header">
          <div>
            <p className="eyebrow">Realtime telemetry</p>
            <h2 id="dual-monitor-title">{text("Three-wheel monitor", "Monitor xe ba bánh")}</h2>
            <p>{text("Every card displays only backend values; the UI never invents replacement measurements.", "Mọi ô chỉ hiển thị giá trị nhận từ backend; UI không tự tạo số đo thay thế.")}</p>
          </div>
          <span className={`status-pill status-pill--${hasThreeWheelPacket ? "healthy" : "warning"}`}>
            {hasThreeWheelPacket ? <CheckCircle2 size={15} /> : <Activity size={15} />}
            {hasThreeWheelPacket ? text("Valid packet", "Packet hợp lệ") : text("Waiting for three-motor contract", "Chờ contract 3 motor")}
          </span>
        </header>
        <div className="dual-monitor-metrics" aria-live="polite">
          <span><small>{text("Front-left RPM", "RPM trước trái")}</small><strong>{valueOrDash(measurements?.rpm_left)}</strong><em>GPIO16/17</em></span>
          <span><small>{text("Front-right RPM", "RPM trước phải")}</small><strong>{valueOrDash(measurements?.rpm_right)}</strong><em>GPIO4/5</em></span>
          <span><small>{text("Rear RPM", "RPM bánh sau")}</small><strong>{valueOrDash(measurements?.rpm_rear)}</strong><em>GPIO9/10</em></span>
          <span><small>{text("RPM delta", "Độ lệch RPM")}</small><strong>{valueOrDash(measurements?.rpm_delta)}</strong><em>{text("Target ≤ 5%", "Mục tiêu ≤ 5%")}</em></span>
          <span><small>{text("Left PWM", "PWM trái")}</small><strong>{valueOrDash(measurements?.pwm_left_percent)}%</strong><em>ENA · GPIO12</em></span>
          <span><small>{text("Right PWM", "PWM phải")}</small><strong>{valueOrDash(measurements?.pwm_right_percent)}%</strong><em>ENB · GPIO15</em></span>
          <span><small>{text("Rear PWM", "PWM sau")}</small><strong>{valueOrDash(measurements?.pwm_rear_percent)}%</strong><em>ENA · GPIO6</em></span>
          <span><small>{text("Bus voltage", "Điện áp bus")}</small><strong>{valueOrDash(measurements?.bus_voltage_v, 2)} V</strong><em>INA219</em></span>
          <span><small>{text("Total current", "Dòng tổng")}</small><strong>{valueOrDash(measurements?.total_current_ma ?? measurements?.current_ma, 1)} mA</strong><em>{text("Three motors", "Ba motor")}</em></span>
          <span><small>{text("PS2 controller", "Tay PS2")}</small><strong>{measurements?.ps2_connected ? text("Connected", "Đã nối") : text("Signal lost", "Mất tín hiệu")}</strong><em>{measurements?.control_mode ?? "failsafe"}</em></span>
        </div>
      </section>

      <section className="card signal-card dual-signal-monitor" aria-labelledby="dual-signal-title">
        <div className="panel__header">
          <div><p className="eyebrow">Watchdog & {text("storage", "lưu trữ")}</p><h2 id="dual-signal-title">{text("Monitor health", "Tình trạng monitor")}</h2></div>
          <ShieldCheck size={21} />
        </div>
        <div className="signal-grid dual-signal-grid" aria-live="polite">
          <article className={`signal-item signal-item--${streamStatus === "live" ? "healthy" : "error"}`}>
            <span className={`node-state node-state--${streamStatus === "live" ? "healthy" : "error"}`}>{streamStatus === "live" ? text("Stable", "Ổn định") : text("Fault", "Có lỗi")}</span>
            <strong>Backend / WebSocket</strong>
            <small>{snapshot?.connection.port ?? text("No COM port", "Chưa có COM")} · {snapshot?.connection.baud_rate ?? 115200} baud</small>
            <p>{streamStatus === "live" ? text("Frontend is receiving real-time snapshots.", "Frontend đang nhận snapshot realtime.") : text("No stream received; use Reconnect above.", "Chưa nhận được stream; bấm Thử nối lại ở phía trên.")}</p>
          </article>
          <article className={`signal-item signal-item--${signalHealth?.i2c_verified ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${signalHealth?.i2c_verified ? "healthy" : "waiting"}`}>{signalHealth?.i2c_verified ? text("Stable", "Ổn định") : text("Waiting for data", "Chờ dữ liệu")}</span>
            <strong>I²C GPIO1 / GPIO2</strong>
            <small>INA219 SEN0291 · {text("address", "địa chỉ")} 0x40</small>
            <p>{signalHealth?.i2c_verified ? text("I²C bus passed the check in the latest packet.", "Bus I²C đã vượt qua kiểm tra ở gói mới nhất.") : text("Waiting for firmware to verify SEN0291 and SDA/SCL wiring.", "Chờ firmware xác minh đúng SEN0291 và dây SDA/SCL.")}</p>
          </article>
          <article className={`signal-item signal-item--${hasThreeWheelPacket ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${hasThreeWheelPacket ? "healthy" : "waiting"}`}>{hasThreeWheelPacket ? text("Stable", "Ổn định") : text("Waiting for data", "Chờ dữ liệu")}</span>
            <strong>{text("Three A/B encoders", "Ba encoder A/B")}</strong>
            <small>M1 16/17 · M2 4/5 · M3 9/10</small>
            <p>{hasThreeWheelPacket ? text("Received separate data for all three wheels.", "Đã nhận dữ liệu tách riêng cả ba bánh.") : text("Waiting for 3-wheel-ps2 firmware telemetry.", "Chờ firmware 3-wheel-ps2 gửi telemetry.")}</p>
          </article>
          <article className={`signal-item signal-item--${measurements?.ps2_connected && !measurements?.ps2_failsafe_active ? "healthy" : "error"}`}>
            <span className={`node-state node-state--${measurements?.ps2_connected && !measurements?.ps2_failsafe_active ? "healthy" : "error"}`}>
              {measurements?.ps2_connected && !measurements?.ps2_failsafe_active ? text("Connected", "Đã nối") : "Failsafe"}
            </span>
            <strong>{text("PS2 controller / receiver", "Tay cầm / đầu thu PS2")}</strong>
            <small>DATA 38 · CMD 39 · ATTN 40 · CLK 41</small>
            <p>{measurements?.ps2_connected && !measurements?.ps2_failsafe_active ? text("Firmware is receiving valid control packets.", "Firmware đang nhận packet điều khiển hợp lệ.") : text("Motors are locked; check pairing and the four signal wires.", "Motor bị khóa; kiểm tra ghép cặp và bốn dây tín hiệu.")}</p>
          </article>
          <article className={`signal-item signal-item--${snapshot?.connection.log_file ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${snapshot?.connection.log_file ? "healthy" : "waiting"}`}>{snapshot?.connection.log_file ? text("Recording", "Đang ghi") : text("Waiting for data", "Chờ dữ liệu")}</span>
            <strong>{text("Backend log file", "File log backend")}</strong>
            <small title={logFileName}>{logFileName}</small>
            <p>{snapshot?.connection.log_file ? text("Raw logs are stored even before three-motor fields are available.", "Log thô vẫn được lưu kể cả khi chưa có field ba motor.") : text("Backend has not returned a log file path.", "Backend chưa trả về đường dẫn file log.")}</p>
          </article>
        </div>
        {activeDiagnostics.length > 0 && <p className="dual-signal-monitor__issues"><AlertTriangle size={15} /> {text(`${activeDiagnostics.length} open faults are listed under “Actions required” below.`, `${activeDiagnostics.length} lỗi đang mở được liệt kê trong “Việc cần xử lý” bên dưới.`)}</p>}
      </section>

      <section className="card architecture-wiring" aria-labelledby="planned-wiring-title">
        <header className="architecture-wiring__header">
          <div>
            <p className="eyebrow">{text("Wiring", "Đấu dây")} · {architecture.wires.length} {text("standardized paths", "đường đã chuẩn hoá")}</p>
            <h2 id="planned-wiring-title">{text("Wire by group, not one oversized diagram", "Nối theo nhóm, không dò trên một sơ đồ dài")}</h2>
            <p>{text("Select the group being assembled or debugged. Every row names both endpoints, pins, and physical wire color.", "Chọn đúng cụm đang lắp hoặc đang sửa lỗi. Mỗi hàng ghi đủ hai đầu, chân và màu dây vật lý.")}</p>
          </div>
          <button className="button button--secondary" type="button" onClick={() => setShowDiagram((value) => !value)} aria-expanded={showDiagram}>
            {showDiagram ? <X size={16} /> : <Eye size={16} />}
            {showDiagram ? text("Close image", "Đóng ảnh") : text("View overview image", "Xem ảnh tổng")}
          </button>
        </header>

        {showDiagram && (
          <figure className="architecture-diagram">
            <img src="/nexus-three-wheel-layout-v9.png" alt={text("Triangular vehicle layout with two front wheels, one rear wheel, and separate wiring corridors", "Bố trí xe tam giác với hai bánh trước, một bánh sau và hai hành lang dây tách biệt")} />
            <figcaption>{text("Overall reference image", "Ảnh tham chiếu tổng thể")} · {text("design", "thiết kế")} {architecture.designId}</figcaption>
          </figure>
        )}

        <div className="architecture-wiring__toolbar" aria-label={text("Filter wire groups", "Lọc nhóm dây")}>
          {scopes.map((item) => {
            const count = architecture.wires.filter((wire) => item === "all" || wire.scope === item).length;
            return (
              <button className={scope === item ? "is-active" : ""} type="button" key={item} onClick={() => setScope(item)} aria-pressed={scope === item}>
                {scopeLabel(item)} <span>{count}</span>
              </button>
            );
          })}
        </div>

        <div className="architecture-wiring__summary" aria-live="polite">
          <Cable size={16} />
          <span>{text("Viewing", "Đang xem")} <strong>{visibleWires.length}</strong> {text("paths", "đường")} · {scopeLabel(scope)}</span>
          <span className="architecture-wiring__hint"><AlertTriangle size={14} /> {text("Turn off 12 V before changing wires", "Tắt nguồn 12 V trước khi đổi dây")}</span>
        </div>

        <ol className="planned-wire-list">
          {visibleWires.map((wire, index) => (
            <li className="planned-wire" data-wire-color={wire.color} key={wire.id}>
              <span className="planned-wire__number">{String(index + 1).padStart(2, "0")}</span>
              <div className="planned-wire__endpoint"><small>{text("Endpoint A", "Đầu A")}</small><strong>{architectureText(wire.from)}</strong><code>{architectureText(wire.fromPin)}</code></div>
              <div className="planned-wire__path">
                <span className={`wire-swatch wire-swatch--${wire.color}`} aria-hidden="true" />
                <strong>{wireColorLabel(wire.color)}</strong>
                {wire.note && <small>{architectureText(wire.note)}</small>}
              </div>
              <div className="planned-wire__endpoint"><small>{text("Endpoint B", "Đầu B")}</small><strong>{architectureText(wire.to)}</strong><code>{architectureText(wire.toPin)}</code></div>
            </li>
          ))}
        </ol>

        <details className="architecture-notes">
          <summary><ChevronDown size={15} /> {text("Six-color motor harness convention", "Quy ước bó dây motor 6 màu")}</summary>
          <p><b>{text("From the left:", "Nhìn từ trái:")}</b> {text("red M+ · black encoder GND · yellow encoder A · green encoder B · blue 3V3 VCC · white M−.", "đỏ M+ · đen GND encoder · vàng encoder A · xanh lá encoder B · xanh dương VCC 3V3 · trắng M−.")}</p>
        </details>
      </section>

      <section className="monitor-grid" aria-label={text("Three-wheel diagnostics and logs", "Chẩn đoán và log xe ba bánh")}>
        <HardwareDiagnosticsPanel mode="dual" />
        <HardwareLiveLog
          mode="dual"
          title={text("Three-Wheel Live Log", "Xe 3 Bánh Live Log")}
          ariaLabel={text("Real-time three-wheel log", "Log realtime xe ba bánh")}
        />
      </section>

      <section className="architecture-footnote" role="note">
        <CheckCircle2 size={18} />
        <p><strong>{text("The three-wheel monitor uses the same real-time backend as the single-motor rig.", "Monitor xe ba bánh dùng cùng backend realtime với Rig 1 motor.")}</strong> {text("Raw logs are always stored by the backend; Start recording creates an additional test session that can be downloaded from the browser.", "Log thô luôn được backend lưu; nút “Bắt đầu ghi” tạo thêm một phiên kiểm thử có thể tải riêng từ trình duyệt.")}</p>
      </section>
    </div>
  );
}
