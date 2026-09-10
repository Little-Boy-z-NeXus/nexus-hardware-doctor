import { Activity, ArrowUpRight, Bot, CheckCircle2, Gauge, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { env } from "../config/env";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";

const formatValue = (value: number | null | undefined, digits: number) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

export function DashboardPage() {
  const { snapshot, streamStatus } = useHardwareMonitor();
  const measurements = snapshot.telemetry?.measurements;
  const activeDiagnostics = snapshot.diagnostics.filter((item) => item.active);
  const hasError = activeDiagnostics.some((item) => item.severity === "error");
  const isLive = streamStatus === "live" && snapshot.connection.status === "connected";
  const status = hasError ? "error" : isLive && !activeDiagnostics.length ? "healthy" : "warning";
  const healthScore = status === "healthy" ? 94 : status === "warning" ? 62 : 28;
  const metrics = [
    {
      label: "Voltage",
      value: formatValue(measurements?.bus_voltage_v, 2),
      unit: "V",
      change: isLive ? "Live" : "Waiting",
      icon: Zap,
    },
    {
      label: "Current",
      value: formatValue(measurements ? measurements.current_ma / 1000 : null, 3),
      unit: "A",
      change: isLive ? "Live" : "Waiting",
      icon: Activity,
    },
    {
      label: "Power",
      value: formatValue(measurements ? measurements.power_mw / 1000 : null, 2),
      unit: "W",
      change: isLive ? "Live" : "Waiting",
      icon: Gauge,
    },
  ];
  const timeline = activeDiagnostics.length
    ? activeDiagnostics.slice(0, 3).map((item) => ({
        time: "Now",
        title: item.title,
        detail: item.action,
        tone: item.severity === "error" ? "error" : "warn",
      }))
    : [
        {
          time: "Now",
          title: isLive ? "Telemetry realtime đang hoạt động" : "Đang chờ ESP32",
          detail: snapshot.connection.message,
          tone: isLive ? "good" : "warn",
        },
      ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="System overview"
        title={hasError ? "Hardware needs attention" : status === "healthy" ? "Your hardware is healthy" : "Waiting for your hardware"}
        description="Live signals and clear next steps for the fixed NeXus MVP motor rig."
        action={<Link className="button button--primary" to="/doctor"><Sparkles size={17} /> Ask AI Doctor</Link>}
      />

      <section className="hero-health card">
        <div className="hero-health__copy">
          <span className={`status-pill status-pill--${status}`}><CheckCircle2 size={15} /> {status === "healthy" ? "Healthy" : status === "error" ? "Needs attention" : "Waiting"}</span>
          <h2>{status === "healthy" ? "Motor system is operating normally" : hasError ? "NeXus found a hardware issue" : "Waiting for live hardware data"}</h2>
          <p>{hasError ? "Open Hardware Graph to see the likely cause and the exact next step." : isLive ? "Current and voltage are coming directly from the ESP32 serial stream." : "Connect the GOOUUU ESP32-S3 and keep the backend window open."}</p>
          <div className="hero-health__meta">
            <span><strong>{env.deviceId}</strong><small>Device</small></span>
            <span><strong>{snapshot.connection.port ?? "--"}</strong><small>Serial port</small></span>
            <span><strong>{snapshot.telemetry ? `${snapshot.telemetry.quality.signal_quality_percent}%` : "--"}</strong><small>Signal quality</small></span>
          </div>
        </div>
        <div className="health-score" aria-label={`Health score ${healthScore} out of 100`}>
          <div
            className="health-score__ring"
            style={{
              background: `radial-gradient(closest-side, white 80%, transparent 81% 99%), conic-gradient(${status === "error" ? "#d85b55" : status === "warning" ? "#dda24c" : "#28ad8f"} ${healthScore}%, #e8efed 0)`,
            }}
          ><strong>{healthScore}</strong><span>/100</span></div>
          <p>Health score</p>
        </div>
      </section>

      <section className="metric-grid" aria-label="Live telemetry">
        {metrics.map(({ label, value, unit, change, icon: Icon }) => (
          <article className="metric-card card" key={label}>
            <div className="metric-card__top"><span className="metric-icon"><Icon size={19} /></span><span className="metric-change">{change}</span></div>
            <p>{label}</p>
            <strong>{value}<small>{unit}</small></strong>
            <div className="sparkline" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /></div>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Prevent</p><h2>Risk monitor</h2></div><span className={`status-pill status-pill--${status}`}><ShieldCheck size={14} /> {activeDiagnostics.length} active</span></div>
          <div className="risk-row"><div className="risk-gauge"><span>{status === "healthy" ? "8%" : status === "warning" ? "38%" : "86%"}</span></div><div><strong>{status === "healthy" ? "No intervention needed" : "Check hardware guidance"}</strong><p>Calculated from deterministic MVP limits and current serial health.</p></div></div>
          <Link className="text-link" to="/hardware">Inspect hardware graph <ArrowUpRight size={15} /></Link>
        </article>

        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Recent activity</p><h2>System timeline</h2></div></div>
          <ol className="timeline">
            {timeline.map((item) => <li key={`${item.time}-${item.title}`}><span className={`timeline__dot timeline__dot--${item.tone}`} /><time>{item.time}</time><div><strong>{item.title}</strong><p>{item.detail}</p></div></li>)}
          </ol>
        </article>
      </section>

      <section className="doctor-cta card">
        <span className="doctor-cta__icon"><Bot size={25} /></span>
        <div><p className="eyebrow">Manual diagnose</p><h2>Something feels wrong?</h2><p>Describe the symptom naturally. AI Doctor will connect it to live telemetry before suggesting a safe action.</p></div>
        <Link className="button button--secondary" to="/doctor">Start diagnosis <ArrowUpRight size={16} /></Link>
      </section>
    </div>
  );
}
