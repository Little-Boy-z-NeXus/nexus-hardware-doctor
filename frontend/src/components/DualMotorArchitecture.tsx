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
  Gauge,
  GitCompareArrows,
  Leaf,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Vibrate,
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

const architecture = DUAL_MOTOR_ARCHITECTURE;

const sensorIcons = {
  power: Gauge,
  environment: Leaf,
  motion: Vibrate,
} as const;

const scopes = Object.keys(WIRING_SCOPE_LABELS) as WiringScope[];

interface DualMotorMeasurements {
  bus_voltage_v?: number | null;
  current_ma?: number | null;
  total_current_ma?: number | null;
  power_mw?: number | null;
  rpm_left?: number | null;
  rpm_right?: number | null;
  rpm_delta?: number | null;
  pwm_left_percent?: number | null;
  pwm_right_percent?: number | null;
  pid_state?: string | null;
  yaw_rate_dps?: number | null;
  temperature_c?: number | null;
  humidity_percent?: number | null;
}

const valueOrDash = (value: number | null | undefined, digits = 0) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

const timeLabel = (value: string | null) => value
  ? new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value))
  : "--:--:--";

export function DualMotorArchitecture() {
  const { snapshot, streamStatus, reconnect } = useHardwareMonitor();
  const [scope, setScope] = useState<WiringScope>("all");
  const [showDiagram, setShowDiagram] = useState(false);
  const visibleWires = useMemo(
    () => architecture.wires.filter((wire) => scope === "all" || wire.scope === scope),
    [scope],
  );
  const measurements = snapshot?.telemetry?.measurements as DualMotorMeasurements | undefined;
  const deviceLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const hasDualPacket = measurements?.rpm_left != null
    || measurements?.rpm_right != null
    || measurements?.pwm_left_percent != null
    || measurements?.pwm_right_percent != null;
  const signalHealth = snapshot?.signal_health;
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const logFileName = snapshot?.connection.log_file?.split(/[\\/]/).pop() ?? "chưa có file log";

  return (
    <div className="architecture-stack" data-testid="dual-motor-architecture">
      <section className="card architecture-hero" aria-labelledby="architecture-title">
        <div className="architecture-hero__copy">
          <div className="architecture-hero__eyebrow">
            <span className={`status-pill status-pill--${hasDualPacket ? "healthy" : deviceLive ? "warning" : "error"}`}>
              {hasDualPacket ? "Telemetry 2 motor · live" : deviceLive ? "Backend live · chờ packet 2 motor" : "Monitor đang chờ kết nối"}
            </span>
            <span>Hardware-as-code {architecture.schemaVersion}</span>
          </div>
          <h2 id="architecture-title">Xe hai motor tự cân bằng tốc độ bằng PID</h2>
          <p>
            Hai encoder đo độc lập từng bánh, ESP32-S3 so sánh RPM và điều chỉnh hai kênh PWM.
            INA226, BME680 và BNO055 bổ sung bằng chứng điện, môi trường và rung để NeXus chẩn đoán.
          </p>
        </div>
        <div className="architecture-hero__facts" aria-label="Tóm tắt kiến trúc">
          <span><strong>2</strong><small>motor + encoder</small></span>
          <span><strong>3</strong><small>thiết bị I²C</small></span>
          <span><strong>≤ 5%</strong><small>mục tiêu lệch RPM</small></span>
        </div>
      </section>

      <section
        className={`connection-banner connection-banner--${hasDualPacket ? "healthy" : streamStatus === "live" ? "warning" : "error"}`}
        role="status"
        aria-live="polite"
      >
        <span className="connection-banner__icon">
          {hasDualPacket ? <CheckCircle2 size={20} /> : streamStatus === "live" ? <Activity size={20} /> : <CircleOff size={20} />}
        </span>
        <div>
          <strong>{hasDualPacket ? "Xe hai motor đang cập nhật realtime" : streamStatus === "live" ? "Backend monitor đã sẵn sàng" : "Chưa kết nối được backend"}</strong>
          <p>
            {hasDualPacket
              ? "Đã nhận RPM và PWM độc lập cho bánh trái/phải."
              : streamStatus === "live"
                ? "WebSocket đã kết nối; backend sẽ lưu log ngay khi ESP32 gửi dữ liệu. Hãy nạp firmware dual-motor để mở số đo hai bánh."
                : "Mở nexus-start-app.cmd để kết nối WebSocket, telemetry và file log."}
          </p>
        </div>
        <span className="connection-banner__meta">Gói cuối: {timeLabel(snapshot?.connection.last_seen_at ?? null)}</span>
        {streamStatus !== "live" && (
          <button className="button button--secondary connection-banner__action" type="button" onClick={reconnect}>
            <RefreshCw size={15} /> Thử nối lại
          </button>
        )}
      </section>

      <section className="card dual-drive" aria-labelledby="drive-balance-title">
        <header className="dual-drive__header">
          <div>
            <p className="eyebrow">Vòng điều khiển kín</p>
            <h2 id="drive-balance-title">Cân bằng hai bánh</h2>
            <p>Cùng một monitor cho kết nối, cảnh báo, log và telemetry; giá trị hai bánh chỉ hiện khi firmware gửi đúng contract.</p>
          </div>
          <span className={`architecture-readiness${hasDualPacket ? " is-live" : ""}`}>
            {hasDualPacket ? <CheckCircle2 size={16} /> : <FileCode2 size={16} />}
            {hasDualPacket ? "Telemetry dual-motor hợp lệ" : "Chờ firmware dual-motor"}
          </span>
        </header>

        <div className="dual-drive__flow">
          <article className="wheel-card wheel-card--left">
            <span className="wheel-card__side">Kênh A · trái</span>
            <div className="wheel-card__icon"><RotateCcw size={26} /></div>
            <h3>JGB37-520 trái</h3>
            <dl>
              <div><dt>RPM</dt><dd>{valueOrDash(measurements?.rpm_left)}</dd></div>
              <div><dt>PWM</dt><dd>{valueOrDash(measurements?.pwm_left_percent)}%</dd></div>
            </dl>
            <small>Encoder A/B → GPIO16 / GPIO17</small>
          </article>

          <div className="pid-core">
            <div className="pid-core__board">
              <CircuitBoard size={22} />
              <span><small>Bộ điều khiển</small><strong>ESP32-S3-N16R8</strong></span>
            </div>
            <div className="pid-core__delta">
              <GitCompareArrows size={22} />
              <span><small>rpm_delta</small><strong>{measurements?.rpm_delta == null ? "Chờ dữ liệu" : `${valueOrDash(measurements.rpm_delta)} RPM`}</strong></span>
              <em>Mục tiêu = 0</em>
            </div>
            <div className="pid-core__loop">
              <SlidersHorizontal size={17} />
              {measurements?.pid_state ? `PID: ${measurements.pid_state}` : "PID giới hạn PWM 0–80%"}
            </div>
          </div>

          <article className="wheel-card wheel-card--right">
            <span className="wheel-card__side">Kênh B · phải</span>
            <div className="wheel-card__icon"><RotateCcw size={26} /></div>
            <h3>JGB37-520 phải</h3>
            <dl>
              <div><dt>RPM</dt><dd>{valueOrDash(measurements?.rpm_right)}</dd></div>
              <div><dt>PWM</dt><dd>{valueOrDash(measurements?.pwm_right_percent)}%</dd></div>
            </dl>
            <small>Encoder A/B → GPIO7 / GPIO8</small>
          </article>
        </div>

        <div className="dual-drive__contract">
          <span><Activity size={15} /> API dự kiến</span>
          <div>{architecture.expectedTelemetry.map((field) => <code key={field}>{field}</code>)}</div>
        </div>
      </section>

      <section className="architecture-grid" aria-label="Nguồn dữ liệu chẩn đoán">
        <article className="card architecture-panel">
          <header>
            <div><p className="eyebrow">Shared I²C · GPIO1/2</p><h2>Ba lớp bằng chứng</h2></div>
            <Workflow size={21} />
          </header>
          <div className="sensor-list">
            {architecture.i2c.map((sensor) => {
              const Icon = sensorIcons[sensor.icon];
              return (
                <div className="sensor-list__item" key={sensor.name}>
                  <span className="sensor-list__icon"><Icon size={18} /></span>
                  <span><strong>{sensor.name}</strong><small>{sensor.purpose}</small></span>
                  <code>{sensor.address}</code>
                </div>
              );
            })}
          </div>
        </article>

        <article className="card architecture-panel architecture-panel--safety">
          <header>
            <div><p className="eyebrow">Nguồn & bảo vệ</p><h2>LiPo 3S qua một chuỗi an toàn</h2></div>
            <BatteryCharging size={21} />
          </header>
          <ol className="power-chain" aria-label="Chuỗi cấp nguồn 12V">
            <li>LiPo 3S</li><li>Cầu chì 1,5 A</li><li>Công tắc</li><li>Nút ngắt NC</li><li>INA226</li><li>L298N</li>
          </ol>
          <div className="architecture-warning">
            <ShieldCheck size={18} />
            <p><strong>ESP32 chỉ nhận nguồn từ USB.</strong> Không đưa 11,1–12,6 V vào chân 3V3/5V; mọi GND quy về một điểm sao.</p>
          </div>
        </article>
      </section>

      <section className="card dual-monitor-overview" aria-labelledby="dual-monitor-title">
        <header className="dual-monitor-overview__header">
          <div>
            <p className="eyebrow">Realtime telemetry</p>
            <h2 id="dual-monitor-title">Monitor xe hai motor</h2>
            <p>Mọi ô chỉ hiển thị giá trị nhận từ backend; UI không tự tạo số đo thay thế.</p>
          </div>
          <span className={`status-pill status-pill--${hasDualPacket ? "healthy" : "warning"}`}>
            {hasDualPacket ? <CheckCircle2 size={15} /> : <Activity size={15} />}
            {hasDualPacket ? "Packet hợp lệ" : "Chờ contract dual-motor"}
          </span>
        </header>
        <div className="dual-monitor-metrics" aria-live="polite">
          <span><small>RPM trái</small><strong>{valueOrDash(measurements?.rpm_left)}</strong><em>GPIO16/17</em></span>
          <span><small>RPM phải</small><strong>{valueOrDash(measurements?.rpm_right)}</strong><em>GPIO7/8</em></span>
          <span><small>Độ lệch RPM</small><strong>{valueOrDash(measurements?.rpm_delta)}</strong><em>Mục tiêu ≤ 5%</em></span>
          <span><small>PWM trái</small><strong>{valueOrDash(measurements?.pwm_left_percent)}%</strong><em>ENA · GPIO12</em></span>
          <span><small>PWM phải</small><strong>{valueOrDash(measurements?.pwm_right_percent)}%</strong><em>ENB · GPIO4</em></span>
          <span><small>Điện áp bus</small><strong>{valueOrDash(measurements?.bus_voltage_v, 2)} V</strong><em>INA226</em></span>
          <span><small>Dòng tổng</small><strong>{valueOrDash(measurements?.total_current_ma ?? measurements?.current_ma, 1)} mA</strong><em>Hai motor</em></span>
          <span><small>Yaw rate</small><strong>{valueOrDash(measurements?.yaw_rate_dps, 1)} °/s</strong><em>BNO055</em></span>
        </div>
      </section>

      <section className="card signal-card dual-signal-monitor" aria-labelledby="dual-signal-title">
        <div className="panel__header">
          <div><p className="eyebrow">Watchdog & lưu trữ</p><h2 id="dual-signal-title">Tình trạng monitor</h2></div>
          <ShieldCheck size={21} />
        </div>
        <div className="signal-grid dual-signal-grid" aria-live="polite">
          <article className={`signal-item signal-item--${streamStatus === "live" ? "healthy" : "error"}`}>
            <span className={`node-state node-state--${streamStatus === "live" ? "healthy" : "error"}`}>{streamStatus === "live" ? "Ổn định" : "Có lỗi"}</span>
            <strong>Backend / WebSocket</strong>
            <small>{snapshot?.connection.port ?? "Chưa có COM"} · {snapshot?.connection.baud_rate ?? 115200} baud</small>
            <p>{streamStatus === "live" ? "Frontend đang nhận snapshot realtime." : "Chưa nhận được stream; bấm Thử nối lại ở phía trên."}</p>
          </article>
          <article className={`signal-item signal-item--${signalHealth?.i2c_verified ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${signalHealth?.i2c_verified ? "healthy" : "waiting"}`}>{signalHealth?.i2c_verified ? "Ổn định" : "Chờ dữ liệu"}</span>
            <strong>I²C GPIO1 / GPIO2</strong>
            <small>INA226 · BME680 · BNO055</small>
            <p>{signalHealth?.i2c_verified ? "Bus I²C đã vượt qua kiểm tra ở gói mới nhất." : "Chờ firmware scan và xác minh đủ ba identity."}</p>
          </article>
          <article className={`signal-item signal-item--${hasDualPacket ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${hasDualPacket ? "healthy" : "waiting"}`}>{hasDualPacket ? "Ổn định" : "Chờ dữ liệu"}</span>
            <strong>Hai encoder A/B</strong>
            <small>Trái GPIO16/17 · Phải GPIO7/8</small>
            <p>{hasDualPacket ? "Đã nhận dữ liệu tách riêng hai bánh." : "Không đánh dấu khỏe cho tới khi firmware dual-motor gửi dữ liệu."}</p>
          </article>
          <article className={`signal-item signal-item--${snapshot?.connection.log_file ? "healthy" : "waiting"}`}>
            <span className={`node-state node-state--${snapshot?.connection.log_file ? "healthy" : "waiting"}`}>{snapshot?.connection.log_file ? "Đang ghi" : "Chờ dữ liệu"}</span>
            <strong>File log backend</strong>
            <small title={logFileName}>{logFileName}</small>
            <p>{snapshot?.connection.log_file ? "Log thô vẫn được lưu kể cả khi chưa có field dual-motor." : "Backend chưa trả về đường dẫn file log."}</p>
          </article>
        </div>
        {activeDiagnostics.length > 0 && <p className="dual-signal-monitor__issues"><AlertTriangle size={15} /> {activeDiagnostics.length} lỗi đang mở được liệt kê trong “Việc cần xử lý” bên dưới.</p>}
      </section>

      <section className="card architecture-wiring" aria-labelledby="planned-wiring-title">
        <header className="architecture-wiring__header">
          <div>
            <p className="eyebrow">Đấu dây · {architecture.wires.length} đường đã chuẩn hoá</p>
            <h2 id="planned-wiring-title">Nối theo nhóm, không dò trên một sơ đồ dài</h2>
            <p>Chọn đúng cụm đang lắp hoặc đang sửa lỗi. Mỗi hàng ghi đủ hai đầu, chân và màu dây vật lý.</p>
          </div>
          <button className="button button--secondary" type="button" onClick={() => setShowDiagram((value) => !value)} aria-expanded={showDiagram}>
            {showDiagram ? <X size={16} /> : <Eye size={16} />}
            {showDiagram ? "Đóng ảnh" : "Xem ảnh tổng"}
          </button>
        </header>

        {showDiagram && (
          <figure className="architecture-diagram">
            <img src="/nexus-dual-motor-complete-wiring-simple-v6.png" alt="Sơ đồ đấu dây dạng khối, đầy đủ ESP32-S3, INA226, BME680, BNO055, L298N và hai motor JGB37-520" />
            <figcaption>Ảnh tham chiếu tổng thể · thiết kế {architecture.designId}</figcaption>
          </figure>
        )}

        <div className="architecture-wiring__toolbar" aria-label="Lọc nhóm dây">
          {scopes.map((item) => {
            const count = architecture.wires.filter((wire) => item === "all" || wire.scope === item).length;
            return (
              <button className={scope === item ? "is-active" : ""} type="button" key={item} onClick={() => setScope(item)} aria-pressed={scope === item}>
                {WIRING_SCOPE_LABELS[item]} <span>{count}</span>
              </button>
            );
          })}
        </div>

        <div className="architecture-wiring__summary" aria-live="polite">
          <Cable size={16} />
          <span>Đang xem <strong>{visibleWires.length}</strong> đường · {WIRING_SCOPE_LABELS[scope]}</span>
          <span className="architecture-wiring__hint"><AlertTriangle size={14} /> Tắt nguồn 12 V trước khi đổi dây</span>
        </div>

        <ol className="planned-wire-list">
          {visibleWires.map((wire, index) => (
            <li className="planned-wire" data-wire-color={wire.color} key={wire.id}>
              <span className="planned-wire__number">{String(index + 1).padStart(2, "0")}</span>
              <div className="planned-wire__endpoint"><small>Đầu A</small><strong>{wire.from}</strong><code>{wire.fromPin}</code></div>
              <div className="planned-wire__path">
                <span className={`wire-swatch wire-swatch--${wire.color}`} aria-hidden="true" />
                <strong>{WIRE_COLOR_LABELS[wire.color]}</strong>
                {wire.note && <small>{wire.note}</small>}
              </div>
              <div className="planned-wire__endpoint"><small>Đầu B</small><strong>{wire.to}</strong><code>{wire.toPin}</code></div>
            </li>
          ))}
        </ol>

        <details className="architecture-notes">
          <summary><ChevronDown size={15} /> Quy ước bó dây motor 6 màu</summary>
          <p><b>Nhìn từ trái:</b> đỏ M+ · đen GND encoder · vàng encoder A · xanh lá encoder B · xanh dương VCC 3V3 · trắng M−.</p>
        </details>
      </section>

      <section className="monitor-grid" aria-label="Chẩn đoán và log xe hai motor">
        <HardwareDiagnosticsPanel mode="dual" />
        <HardwareLiveLog
          mode="dual"
          title="Xe 2 Motor Live Log"
          ariaLabel="Log realtime xe hai motor"
        />
      </section>

      <section className="architecture-footnote" role="note">
        <CheckCircle2 size={18} />
        <p><strong>Monitor xe hai motor dùng cùng backend realtime với Rig 1 motor.</strong> Log thô luôn được backend lưu; nút “Bắt đầu ghi” tạo thêm một phiên kiểm thử có thể tải riêng từ trình duyệt.</p>
      </section>
    </div>
  );
}
