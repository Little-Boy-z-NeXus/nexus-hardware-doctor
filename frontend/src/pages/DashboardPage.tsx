import { Activity, ArrowUpRight, Bot, CheckCircle2, Gauge, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { env } from "../config/env";

const metrics = [
  { label: "Voltage", value: "11.96", unit: "V", change: "+0.02", icon: Zap },
  { label: "Current", value: "0.84", unit: "A", change: "Stable", icon: Activity },
  { label: "Power", value: "10.05", unit: "W", change: "Normal", icon: Gauge },
];

const timeline = [
  { time: "Now", title: "Telemetry healthy", detail: "All readings inside safe envelope", tone: "good" },
  { time: "2m", title: "Prevent scan completed", detail: "No early fault signature detected", tone: "good" },
  { time: "18m", title: "Current spike observed", detail: "Recovered in 420 ms", tone: "warn" },
];

export function DashboardPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="System overview"
        title="Your hardware is healthy"
        description="A focused view of the demo rig, live signals and the next best action."
        action={<Link className="button button--primary" to="/doctor"><Sparkles size={17} /> Ask AI Doctor</Link>}
      />

      <section className="hero-health card">
        <div className="hero-health__copy">
          <span className="status-pill status-pill--healthy"><CheckCircle2 size={15} /> Healthy</span>
          <h2>Motor system is operating normally</h2>
          <p>NeXus sees no active fault. Current and voltage remain inside the expected range for this hardware model.</p>
          <div className="hero-health__meta">
            <span><strong>{env.deviceId}</strong><small>Device</small></span>
            <span><strong>37 ms</strong><small>Last packet</small></span>
            <span><strong>99.8%</strong><small>Signal quality</small></span>
          </div>
        </div>
        <div className="health-score" aria-label="Health score 94 out of 100">
          <div className="health-score__ring"><strong>94</strong><span>/100</span></div>
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
          <div className="panel__header"><div><p className="eyebrow">Prevent</p><h2>Risk monitor</h2></div><span className="status-pill status-pill--healthy"><ShieldCheck size={14} /> Low risk</span></div>
          <div className="risk-row"><div className="risk-gauge"><span>8%</span></div><div><strong>No intervention needed</strong><p>Estimated anomaly risk in the next 30 minutes.</p></div></div>
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
