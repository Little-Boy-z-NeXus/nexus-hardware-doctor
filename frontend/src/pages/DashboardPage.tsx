import { Activity, ArrowUpRight, Bot, CheckCircle2, Gauge, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";
import { localizeConnectionMessage, localizeDiagnostic } from "../i18n/runtimeCopy";

const formatValue = (value: number | null | undefined, digits: number) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

function MetricTrend({ values, label }: { values: number[]; label: string }) {
  const { text } = useI18n();
  const samples = values.slice(-12);
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const spread = Math.max(max - min, Math.abs(max) * 0.03, 1);

  if (!samples.length) return <span className="metric-empty">{text("Waiting for data", "Chờ dữ liệu")}</span>;
  return (
    <span className="sparkline" role="img" aria-label={text(`${label}, latest ${samples.length} samples`, `${label}, ${samples.length} mẫu gần nhất`)}>
      {samples.map((value, index) => (
        <i
          key={`${index}-${value}`}
          style={{ height: `${10 + ((value - min) / spread) * 24}px` }}
        />
      ))}
    </span>
  );
}

export function DashboardPage() {
  const { language, text } = useI18n();
  const { snapshot, hardwareProfile, streamStatus, history } = useHardwareMonitor();
  const measurements = snapshot?.telemetry?.measurements;
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const hasError = activeDiagnostics.some((item) => item.severity === "error");
  const isLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const status = snapshot?.health.status ?? "warning";
  const signalQuality = snapshot?.telemetry?.quality.signal_quality_percent ?? 0;
  const source = snapshot?.telemetry?.quality.source;
  const sourceLabel = source === "device"
    ? text("Physical device", "Thiết bị thật")
    : source === "replay"
      ? "Replay"
      : source === "simulator"
        ? text("Simulator", "Mô phỏng")
        : "--";
  const controllerName = hardwareProfile?.controller.model ?? text("declared board", "board đã khai báo");
  const unitFor = (field: string) => hardwareProfile?.telemetry.measurements.find(
    (item) => item.field === field,
  )?.unit ?? "";
  const metrics = [
    {
      label: text("Bus voltage", "Điện áp bus"),
      value: formatValue(measurements?.bus_voltage_v, 2),
      unit: unitFor("bus_voltage_v"),
      values: history.map((item) => item.measurements.bus_voltage_v),
      icon: Zap,
    },
    {
      label: text("Current", "Dòng điện"),
      value: formatValue(measurements?.current_ma, 1),
      unit: unitFor("current_ma"),
      values: history.map((item) => item.measurements.current_ma),
      icon: Activity,
    },
    {
      label: text("Power", "Công suất"),
      value: formatValue(measurements?.power_mw, 1),
      unit: unitFor("power_mw"),
      values: history.map((item) => item.measurements.power_mw),
      icon: Gauge,
    },
  ];
  const timeline = activeDiagnostics.length
    ? activeDiagnostics.slice(0, 3).map((item) => ({
        time: text("Now", "Hiện tại"),
        title: localizeDiagnostic(item, language).title,
        detail: localizeDiagnostic(item, language).action,
        tone: item.severity === "error" ? "error" : "warn",
      }))
    : [
        {
          time: text("Now", "Hiện tại"),
          title: isLive ? text("Real-time telemetry is active", "Telemetry realtime đang hoạt động") : text("Waiting for ESP32", "Đang chờ ESP32"),
          detail: localizeConnectionMessage(snapshot?.connection, language),
          tone: isLive ? "good" : "warn",
        },
      ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={text("System overview", "Tổng quan hệ thống")}
        title={hasError ? text("Hardware needs attention", "Phần cứng cần được kiểm tra") : status === "healthy" ? text("System is stable", "Hệ thống đang ổn định") : text("Waiting for hardware", "Đang chờ phần cứng")}
        description={text(`Live data from ${hardwareProfile?.name ?? "the hardware profile being loaded"}.`, `Theo dõi dữ liệu trực tiếp của ${hardwareProfile?.name ?? "hardware profile đang được tải"}.`)}
        action={<Link className="button button--primary" to="/doctor"><Sparkles size={17} /> {text("Ask AI Doctor", "Hỏi Bác sĩ AI")}</Link>}
      />

      <section className="hero-health card" aria-labelledby="health-heading">
        <div className="hero-health__copy">
          <span className={`status-pill status-pill--${status}`}><CheckCircle2 size={15} /> {status === "healthy" ? text("Stable", "Ổn định") : status === "error" ? text("Action required", "Cần xử lý") : text("Waiting", "Đang chờ")}</span>
          <h2 id="health-heading">{status === "healthy" ? text("Electrical signals are within MVP limits", "Các tín hiệu điện đang trong giới hạn MVP") : hasError ? text("NeXus detected a hardware issue", "NeXus đã phát hiện một vấn đề phần cứng") : text("No live telemetry from the board yet", "Chưa có telemetry trực tiếp từ board")}</h2>
          <p>{hasError ? text("Open Hardware Graph to inspect the affected component and immediate action.", "Mở Sơ đồ phần cứng để xem linh kiện liên quan và việc cần làm ngay.") : isLive ? text(`Every value below comes directly from ${controllerName} through the backend.`, `Mỗi thay đổi dưới đây đến trực tiếp từ ${controllerName} qua backend.`) : text(`Connect ${controllerName} and keep the backend running; NeXus will reconnect automatically.`, `Kết nối ${controllerName} và giữ backend đang chạy; NeXus sẽ tự nối lại.`)}</p>
          <div className="hero-health__meta">
            <span><strong>{snapshot?.telemetry?.device_id ?? "--"}</strong><small>{text("Device", "Thiết bị")}</small></span>
            <span><strong>{snapshot?.connection.port ?? "--"}</strong><small>{text("Serial port", "Cổng serial")}</small></span>
            <span><strong>{snapshot?.telemetry ? `${signalQuality}%` : "--"}</strong><small>{text("Signal quality", "Chất lượng tín hiệu")}</small></span>
            <span><strong>{sourceLabel}</strong><small>{text("Data source", "Nguồn dữ liệu")}</small></span>
          </div>
        </div>
        <div className="health-score" aria-label={text(`Telemetry quality ${signalQuality} out of 100`, `Chất lượng telemetry ${signalQuality} trên 100`)}>
          <div
            className="health-score__ring"
            style={{
              background: `radial-gradient(closest-side, white 80%, transparent 81% 99%), conic-gradient(${status === "error" ? "#d85b55" : status === "warning" ? "#dda24c" : "#28ad8f"} ${signalQuality}%, #e8efed 0)`,
            }}
          ><strong>{snapshot?.telemetry ? signalQuality : "--"}</strong><span>/100</span></div>
          <p>{text("Telemetry quality", "Chất lượng telemetry")}</p>
        </div>
      </section>

      <section className="metric-grid" aria-label={text("Live telemetry", "Telemetry trực tiếp")}>
        {metrics.map(({ label, value, unit, values, icon: Icon }) => (
          <article className="metric-card card" key={label}>
            <div className="metric-card__top"><span className="metric-icon"><Icon size={19} /></span><span className="metric-change">{isLive ? "LIVE" : text("WAITING", "ĐANG CHỜ")}</span></div>
            <p>{label}</p>
            <strong>{value}<small>{unit}</small></strong>
            <MetricTrend values={values} label={label} />
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">{text("Prevent", "Phòng ngừa")}</p><h2>{text("Risk monitoring", "Giám sát rủi ro")}</h2></div><span className={`status-pill status-pill--${status}`}><ShieldCheck size={14} /> {activeDiagnostics.length} {text("alerts", "cảnh báo")}</span></div>
          <div className="risk-row"><div className="risk-gauge"><span>{activeDiagnostics.length}</span></div><div><strong>{activeDiagnostics.length === 0 ? text("No open alerts", "Không có cảnh báo đang mở") : text("Check the hardware guidance", "Hãy kiểm tra hướng dẫn phần cứng")}</strong><p>{text("Live results from backend diagnostics and the selected profile limits.", "Kết quả trực tiếp từ diagnostics backend và giới hạn trong profile đang chọn.")}</p></div></div>
          <Link className="text-link" to="/hardware">{text("Open graph and logs", "Mở sơ đồ và log")} <ArrowUpRight size={15} /></Link>
        </article>

        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">{text("Recent activity", "Hoạt động gần đây")}</p><h2>{text("System timeline", "Dòng thời gian hệ thống")}</h2></div></div>
          <ol className="timeline">
            {timeline.map((item) => <li key={`${item.time}-${item.title}`}><span className={`timeline__dot timeline__dot--${item.tone}`} /><time>{item.time}</time><div><strong>{item.title}</strong><p>{item.detail}</p></div></li>)}
          </ol>
        </article>
      </section>

      <section className="doctor-cta card">
        <span className="doctor-cta__icon"><Bot size={25} /></span>
        <div><p className="eyebrow">{text("Manual diagnosis", "Chẩn đoán thủ công")}</p><h2>{text("Does the motor look or sound unusual?", "Bạn thấy motor có biểu hiện lạ?")}</h2><p>{text("Describe what you see or hear. AI Doctor will compare it with telemetry before recommending a safe check.", "Mô tả điều bạn nhìn hoặc nghe thấy. Bác sĩ AI sẽ đối chiếu với telemetry trước khi đưa ra bước kiểm tra an toàn.")}</p></div>
        <Link className="button button--secondary" to="/doctor">{text("Start diagnosis", "Bắt đầu chẩn đoán")} <ArrowUpRight size={16} /></Link>
      </section>
    </div>
  );
}
