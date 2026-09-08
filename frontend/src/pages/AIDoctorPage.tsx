import { ArrowUp, Bot, CheckCircle2, MessageSquareText, ShieldCheck, Sparkles, UserRound } from "lucide-react";

import { PageHeader } from "../components/PageHeader";

const prompts = ["Why did current spike?", "Run a preventive check", "Is the motor safe?"];

export function AIDoctorPage() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Diagnosis workspace" title="AI Doctor" description="Talk naturally. NeXus combines your symptom with the hardware graph and live telemetry." action={<span className="status-pill status-pill--healthy"><ShieldCheck size={14} /> Safety policy on</span>} />

      <section className="doctor-layout">
        <article className="card chat-panel">
          <div className="chat-panel__header"><span className="ai-avatar"><Bot size={21} /></span><div><strong>NeXus Doctor</strong><small><i className="online-dot" /> Online · watching demo rig</small></div></div>
          <div className="chat-feed">
            <div className="message message--ai"><span className="message__avatar"><Bot size={17} /></span><div><p>I’m connected to the ESP32 motor rig. What are you seeing or hearing?</p><time>Just now</time></div></div>
            <div className="message message--user"><div><p>The motor briefly slowed down. Is something wrong?</p><time>Just now</time></div><span className="message__avatar"><UserRound size={17} /></span></div>
            <div className="message message--ai"><span className="message__avatar"><Sparkles size={17} /></span><div><p>I found one short current spike 18 minutes ago, but voltage stayed stable and the motor recovered in 420 ms. The rig is safe now.</p><div className="message__evidence"><CheckCircle2 size={15} /><span><strong>Evidence checked</strong> INA219 current · Motor RPM · L298N PWM</span></div><time>Just now</time></div></div>
          </div>
          <div className="prompt-row">{prompts.map((prompt) => <button type="button" key={prompt}>{prompt}</button>)}</div>
          <form className="composer" onSubmit={(event) => event.preventDefault()}>
            <MessageSquareText size={19} />
            <label className="sr-only" htmlFor="doctor-question">Ask AI Doctor</label>
            <input id="doctor-question" placeholder="Describe a symptom or ask about the rig…" />
            <button type="submit" aria-label="Send question"><ArrowUp size={18} /></button>
          </form>
        </article>

        <aside className="diagnosis-panel">
          <article className="card panel">
            <div className="panel__header"><div><p className="eyebrow">Current assessment</p><h2>Transient load</h2></div><span className="confidence">92%</span></div>
            <p className="panel-copy">Most likely a brief mechanical load, not an electrical fault.</p>
            <div className="confidence-bar"><i /></div>
            <div className="diagnosis-facts"><span><small>Severity</small><strong>Low</strong></span><span><small>Action</small><strong>Observe</strong></span></div>
          </article>
          <article className="card safety-card"><ShieldCheck size={22} /><div><strong>Safe by design</strong><p>NeXus explains every proposed action and blocks commands outside the fixed safety envelope.</p></div></article>
        </aside>
      </section>
    </div>
  );
}
