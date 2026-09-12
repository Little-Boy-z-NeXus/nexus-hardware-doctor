import { Activity, ArrowUpRight, Bot, CheckCircle2, Gauge, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";

const formatValue = (value: number | null | undefined, digits: number) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

function MetricTrend({ values, label }: { values: number[]; label: string }) {
  const samples = values.slice(-12);
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const spread = Math.max(max - min, Math.abs(max) * 0.03, 1);

  if (!samples.length) return <span className="metric-empty">Chờ dữ liệu</span>;
  return (
    <span className="sparkline" role="img" aria-label={`${label}, ${samples.length} mẫu gần nhất`}>
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
  const { snapshot, hardwareProfile, streamStatus, history } = useHardwareMonitor();
  const measurements = snapshot?.telemetry?.measurements;
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const hasError = activeDiagnostics.some((item) => item.severity === "error");
  const isLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const status = snapshot?.health.status ?? "warning";
  const signalQuality = snapshot?.telemetry?.quality.signal_quality_percent ?? 0;
  const source = snapshot?.telemetry?.quality.source;
  const sourceLabel = source === "device"
    ? "Thiết bị thật"
    : source === "replay"
      ? "Replay"
      : source === "simulator"
        ? "Mô phỏng"
        : "--";
  const controllerName = hardwareProfile?.controller.model ?? "board đã khai báo";
  const unitFor = (field: string) => hardwareProfile?.telemetry.measurements.find(
    (item) => item.field === field,
  )?.unit ?? "";
  const metrics = [
    {
      label: "Điện áp bus",
      value: formatValue(measurements?.bus_voltage_v, 2),
      unit: unitFor("bus_voltage_v"),
      values: history.map((item) => item.measurements.bus_voltage_v),
      icon: Zap,
    },
    {
      label: "Dòng điện",
      value: formatValue(measurements?.current_ma, 1),
      unit: unitFor("current_ma"),
      values: history.map((item) => item.measurements.current_ma),
      icon: Activity,
    },
    {
      label: "Công suất",
      value: formatValue(measurements?.power_mw, 1),
      unit: unitFor("power_mw"),
      values: history.map((item) => item.measurements.power_mw),
      icon: Gauge,
    },
  ];
  const timeline = activeDiagnostics.length
    ? activeDiagnostics.slice(0, 3).map((item) => ({
        time: "Hiện tại",
        title: item.title,
        detail: item.action,
        tone: item.severity === "error" ? "error" : "warn",
      }))
    : [
        {
          time: "Hiện tại",
          title: isLive ? "Telemetry realtime đang hoạt động" : "Đang chờ ESP32",
          detail: snapshot?.connection.message ?? "Đang tải trạng thái runtime từ backend.",
          tone: isLive ? "good" : "warn",
        },
      ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Tổng quan hệ thống"
        title={hasError ? "Phần cứng cần được kiểm tra" : status === "healthy" ? "Hệ thống đang ổn định" : "Đang chờ phần cứng"}
        description={`Theo dõi dữ liệu trực tiếp của ${hardwareProfile?.name ?? "hardware profile đang được tải"}.`}
        action={<Link className="button button--primary" to="/doctor"><Sparkles size={17} /> Hỏi Bác sĩ AI</Link>}
      />

      <section className="hero-health card" aria-labelledby="health-heading">
        <div className="hero-health__copy">
          <span className={`status-pill status-pill--${status}`}><CheckCircle2 size={15} /> {status === "healthy" ? "Ổn định" : status === "error" ? "Cần xử lý" : "Đang chờ"}</span>
          <h2 id="health-heading">{status === "healthy" ? "Các tín hiệu điện đang trong giới hạn MVP" : hasError ? "NeXus đã phát hiện một vấn đề phần cứng" : "Chưa có telemetry trực tiếp từ board"}</h2>
          <p>{hasError ? "Mở Sơ đồ phần cứng để xem linh kiện liên quan và việc cần làm ngay." : isLive ? `Mỗi thay đổi dưới đây đến trực tiếp từ ${controllerName} qua backend.` : `Kết nối ${controllerName} và giữ backend đang chạy; NeXus sẽ tự nối lại.`}</p>
          <div className="hero-health__meta">
            <span><strong>{snapshot?.telemetry?.device_id ?? "--"}</strong><small>Thiết bị</small></span>
            <span><strong>{snapshot?.connection.port ?? "--"}</strong><small>Cổng serial</small></span>
            <span><strong>{snapshot?.telemetry ? `${signalQuality}%` : "--"}</strong><small>Chất lượng tín hiệu</small></span>
            <span><strong>{sourceLabel}</strong><small>Nguồn dữ liệu</small></span>
          </div>
        </div>
        <div className="health-score" aria-label={`Chất lượng telemetry ${signalQuality} trên 100`}>
          <div
            className="health-score__ring"
            style={{
              background: `radial-gradient(closest-side, white 80%, transparent 81% 99%), conic-gradient(${status === "error" ? "#d85b55" : status === "warning" ? "#dda24c" : "#28ad8f"} ${signalQuality}%, #e8efed 0)`,
            }}
          ><strong>{snapshot?.telemetry ? signalQuality : "--"}</strong><span>/100</span></div>
          <p>Chất lượng telemetry</p>
        </div>
      </section>

      <section className="metric-grid" aria-label="Telemetry trực tiếp">
        {metrics.map(({ label, value, unit, values, icon: Icon }) => (
          <article className="metric-card card" key={label}>
            <div className="metric-card__top"><span className="metric-icon"><Icon size={19} /></span><span className="metric-change">{isLive ? "LIVE" : "ĐANG CHỜ"}</span></div>
            <p>{label}</p>
            <strong>{value}<small>{unit}</small></strong>
            <MetricTrend values={values} label={label} />
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Phòng ngừa</p><h2>Giám sát rủi ro</h2></div><span className={`status-pill status-pill--${status}`}><ShieldCheck size={14} /> {activeDiagnostics.length} cảnh báo</span></div>
          <div className="risk-row"><div className="risk-gauge"><span>{activeDiagnostics.length}</span></div><div><strong>{activeDiagnostics.length === 0 ? "Không có cảnh báo đang mở" : "Hãy kiểm tra hướng dẫn phần cứng"}</strong><p>Kết quả trực tiếp từ diagnostics backend và giới hạn trong profile đang chọn.</p></div></div>
          <Link className="text-link" to="/hardware">Mở sơ đồ và log <ArrowUpRight size={15} /></Link>
        </article>

        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Hoạt động gần đây</p><h2>Dòng thời gian hệ thống</h2></div></div>
          <ol className="timeline">
            {timeline.map((item) => <li key={`${item.time}-${item.title}`}><span className={`timeline__dot timeline__dot--${item.tone}`} /><time>{item.time}</time><div><strong>{item.title}</strong><p>{item.detail}</p></div></li>)}
          </ol>
        </article>
      </section>

      <section className="doctor-cta card">
        <span className="doctor-cta__icon"><Bot size={25} /></span>
        <div><p className="eyebrow">Chẩn đoán thủ công</p><h2>Bạn thấy motor có biểu hiện lạ?</h2><p>Mô tả điều bạn nhìn hoặc nghe thấy. Bác sĩ AI sẽ đối chiếu với telemetry trước khi đưa ra bước kiểm tra an toàn.</p></div>
        <Link className="button button--secondary" to="/doctor">Bắt đầu chẩn đoán <ArrowUpRight size={16} /></Link>
      </section>
    </div>
  );
}
