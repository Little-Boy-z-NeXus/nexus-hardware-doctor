import { Activity, ArrowRight, Box, Cpu, Gauge, RotateCcw, Zap } from "lucide-react";

import { PageHeader } from "../components/PageHeader";

const nodes = [
  { name: "ESP32-S3", type: "Controller", detail: "N16R8 · Online", icon: Cpu, tone: "blue" },
  { name: "INA219", type: "Power sensor", detail: "12 V · 0.84 A", icon: Activity, tone: "teal" },
  { name: "L298N", type: "Motor driver", detail: "PWM 62%", icon: Zap, tone: "violet" },
  { name: "DC Motor", type: "Actuator", detail: "1,420 RPM", icon: RotateCcw, tone: "orange" },
];

export function HardwareGraphPage() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Digital twin" title="Hardware Graph" description="The fixed MVP topology and the latest health state for every component." action={<button className="button button--secondary" type="button"><Activity size={17} /> Live data</button>} />

      <section className="card graph-card">
        <div className="panel__header"><div><p className="eyebrow">Signal path</p><h2>Demo motor rig</h2></div><span className="status-pill status-pill--healthy">4 nodes online</span></div>
        <div className="hardware-flow">
          {nodes.map(({ name, type, detail, icon: Icon, tone }, index) => (
            <div className="hardware-step" key={name}>
              <button className={`hardware-node hardware-node--${tone}`} type="button">
                <span className="hardware-node__icon"><Icon size={24} /></span>
                <span><small>{type}</small><strong>{name}</strong><em>{detail}</em></span>
              </button>
              {index < nodes.length - 1 && <span className="hardware-edge" aria-hidden="true"><i /><ArrowRight size={17} /></span>}
            </div>
          ))}
        </div>
        <div className="graph-legend"><span><i className="legend-dot legend-dot--live" /> Live telemetry</span><span><i className="legend-line" /> Signal direction</span><span>Updated 37 ms ago</span></div>
      </section>

      <section className="dashboard-grid">
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Selected node</p><h2>DC Motor</h2></div><span className="status-pill status-pill--healthy">Healthy</span></div>
          <dl className="detail-list">
            <div><dt>Model</dt><dd>JGB37-520 12 V with encoder</dd></div>
            <div><dt>Speed</dt><dd>1,420 RPM</dd></div>
            <div><dt>Expected current</dt><dd>0.65–1.10 A</dd></div>
            <div><dt>Control source</dt><dd>L298N · Channel A</dd></div>
          </dl>
        </article>
        <article className="card panel">
          <div className="panel__header"><div><p className="eyebrow">Relationships</p><h2>Why this graph matters</h2></div><Box size={22} /></div>
          <p className="panel-copy">NeXus follows the real signal path when it reasons. A current spike at INA219 can be connected to driver PWM and motor behavior instead of treated as an isolated number.</p>
          <div className="insight-strip"><Gauge size={19} /><span><strong>Context linked</strong><small>4 nodes · 3 edges · schema v1</small></span></div>
        </article>
      </section>
    </div>
  );
}
