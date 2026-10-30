import {
  Activity, AlertTriangle, ArrowUp, Ban, Bot, CheckCircle2, Download,
  FlaskConical, MessageSquareText, RefreshCw, ShieldCheck, Sparkles, UserRound, Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  nexusApi, type DeviceSummary, type DiagnosisCapabilities,
  type DiagnosisMode, type DiagnosisSession,
} from "../api/nexusApi";
import { PageHeader } from "../components/PageHeader";
import type { LifecycleEventV1 } from "../contracts/v1";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";

interface ChatMessage {
  id: number;
  role: "ai" | "user";
  text: string;
  evidence?: string;
  error?: boolean;
}

function eventTone(event: LifecycleEventV1) {
  if (event.event_type === "action.rejected" || event.event_type === "verification.failed") return "danger";
  if (event.event_type === "verification.passed" || event.event_type === "action.executed") return "success";
  return event.severity === "warning" || event.severity === "error" ? "warning" : "info";
}

function downloadJson(session: DiagnosisSession) {
  const blob = new Blob([JSON.stringify(session, null, 2)], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = `nexus-diagnosis-${session.session_id}.json`;
  anchor.click();
  URL.revokeObjectURL(href);
}

export function AIDoctorPage() {
  const { locale, text } = useI18n();
  const { snapshot, hardwareProfile } = useHardwareMonitor();
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [capabilities, setCapabilities] = useState<DiagnosisCapabilities | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [mode, setMode] = useState<DiagnosisMode>("live");
  const [session, setSession] = useState<DiagnosisSession | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const [loadError, setLoadError] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 1,
    role: "ai",
    text: text("Describe what you see or hear. I will compare telemetry, the BOM, and safety policy before reaching a conclusion.", "Mô tả điều bạn nhìn hoặc nghe thấy. Tôi sẽ đối chiếu telemetry, BOM và chính sách an toàn trước khi kết luận."),
  }]);
  const telemetry = snapshot?.telemetry;
  const isLive = snapshot?.connection.status === "connected" && telemetry?.quality.source === "device";
  const activeDiagnostics = useMemo(
    () => snapshot?.diagnostics.filter((item) => item.active) ?? [],
    [snapshot],
  );
  const liveReady = Boolean(
    isLive && capabilities?.live_enabled && capabilities.live_configured && capabilities.serial_reads_enabled,
  );
  const mockReady = Boolean(capabilities?.mock_available);
  const canDiagnose = mode === "live" ? liveReady : mockReady;
  const result = session?.result ?? null;
  const assessment = result?.plan?.hypotheses[0]?.label
    ?? activeDiagnostics[0]?.title
    ?? (isLive ? text("Telemetry is ready", "Telemetry đã sẵn sàng") : text("Waiting for live data", "Chờ dữ liệu trực tiếp"));
  const confidence = result?.plan ? Math.round(result.plan.confidence * 100) : null;
  const assessmentCopy = result?.plan?.user_message
    ?? activeDiagnostics[0]?.message
    ?? (isLive
      ? text("Choose Live Nebius to read a fresh sample, or use simulation to test the demo flow without an API key.", "Chọn Live Nebius để đọc mẫu mới, hoặc dùng mô phỏng để duyệt luồng demo không cần API key.")
      : text("Connect a physical device or choose safe simulation to test the complete experience.", "Kết nối thiết bị thật hoặc chọn mô phỏng an toàn để kiểm tra toàn bộ trải nghiệm."));
  const prompts = useMemo(() => {
    if (activeDiagnostics[0]) return [
      text(`Explain ${activeDiagnostics[0].title}`, `Giải thích ${activeDiagnostics[0].title}`),
      text(`What is the next safe step for ${activeDiagnostics[0].code}?`, `Bước an toàn tiếp theo cho ${activeDiagnostics[0].code} là gì?`),
      text("Read fresh telemetry and check again", "Đọc telemetry mới và kiểm tra lại"),
    ];
    if (telemetry) return [
      text(`Assess telemetry sample #${telemetry.sequence}`, `Đánh giá mẫu telemetry #${telemetry.sequence}`),
      text(`Is ${telemetry.measurements.current_ma.toFixed(1)} mA reasonable?`, `Dòng ${telemetry.measurements.current_ma.toFixed(1)} mA có hợp lý không?`),
      text(`Run preventive checks for ${hardwareProfile?.profile_id ?? "the current profile"}`, `Kiểm tra phòng ngừa theo ${hardwareProfile?.profile_id ?? "profile hiện tại"}`),
    ];
    return [text("Check the system before running the motor", "Kiểm tra hệ thống trước khi chạy motor"), text("Why does the motor run unevenly?", "Vì sao motor không quay đều?")];
  }, [activeDiagnostics, telemetry, hardwareProfile?.profile_id, text]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([nexusApi.capabilities(controller.signal), nexusApi.devices(controller.signal)])
      .then(([nextCapabilities, nextDevices]) => {
        setCapabilities(nextCapabilities);
        setDevices(nextDevices);
        if (!(nextCapabilities.live_enabled && nextCapabilities.live_configured)
          && nextCapabilities.mock_available) setMode("mock");
        setLoadError("");
      })
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") {
          setLoadError(error instanceof Error ? error.message : text("Could not read backend status.", "Không đọc được trạng thái backend."));
        }
      });
    return () => controller.abort();
  }, [text]);

  const runDiagnosis = async (symptom: string) => {
    setSubmitting(true);
    setLoadError("");
    try {
      let deviceId = telemetry?.device_id ?? devices.find((item) => item.source === "device")?.device_id;
      if (mode === "mock") {
        let simulator = devices.find((item) => item.source === "simulator");
        if (!simulator) {
          const bootstrapped = await nexusApi.bootstrapSimulator();
          simulator = bootstrapped.device;
          setDevices((current) => [
            ...current.filter((item) => item.device_id !== simulator?.device_id),
            simulator as DeviceSummary,
          ]);
        }
        deviceId = simulator.device_id;
      }
      if (!deviceId || !canDiagnose) {
        throw new Error(mode === "live"
          ? text("Live Nebius is not ready: source=device, the serial bridge, and a valid API key are required.", "Live Nebius chưa sẵn sàng: cần source=device, serial bridge và API key hợp lệ.")
          : text("The local simulator is not enabled on the backend.", "Backend chưa bật simulator cục bộ."));
      }
      const nextSession = await nexusApi.diagnose(deviceId, symptom, mode);
      setSession(nextSession);
      const modelCall = nextSession.result.model_runtime?.calls.at(-1);
      const model = modelCall?.response_model ?? modelCall?.requested_model ?? "deterministic planner";
      const evidenceIds = Array.from(new Set(
        nextSession.result.plan?.hypotheses.flatMap((item) => item.evidence_ids) ?? [],
      ));
      const tools = nextSession.result.observations
        .filter((item) => item.status === "succeeded")
        .map((item) => item.tool_name);
      const evidence = [
        `${nextSession.result.model_runtime?.provider ?? mode}/${model}`,
        tools.length ? `tool ${tools.join(", ")}` : null,
        evidenceIds.length ? text(`${evidenceIds.length} evidence items`, `${evidenceIds.length} bằng chứng`) : null,
        `session ${nextSession.session_id.slice(0, 8)}`,
      ].filter(Boolean).join(" · ");
      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: "ai",
        text: nextSession.result.plan?.user_message ?? nextSession.result.summary,
        evidence,
      }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : text("Unknown error", "Lỗi không xác định");
      setLoadError(message);
      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: "ai",
        text: text(`Could not complete diagnosis: ${message}`, `Không thể hoàn tất lượt chẩn đoán: ${message}`),
        evidence: text("No conclusion is generated until the backend returns a valid contract", "Không tạo kết luận khi backend chưa trả về contract hợp lệ"),
        error: true,
      }]);
    } finally {
      setSubmitting(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || submitting) return;
    setMessages((current) => [...current, { id: Date.now(), role: "user", text: trimmed }]);
    setLastQuestion(trimmed);
    setQuestion("");
    await runDiagnosis(trimmed);
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={text("Diagnosis workspace", "Không gian chẩn đoán")}
        title={text("AI Doctor", "Bác sĩ AI")}
        description={text("Evidence-based diagnosis, an audit timeline, and safe remediation for physical devices and local demos.", "Chẩn đoán có bằng chứng, timeline kiểm toán và hướng xử lý an toàn cho thiết bị thật lẫn demo cục bộ.")}
        action={<span className={`status-pill status-pill--${canDiagnose ? "healthy" : "warning"}`}><ShieldCheck size={14} /> {canDiagnose ? text("Ready to diagnose", "Sẵn sàng chẩn đoán") : text("Runtime setup required", "Cần cấu hình runtime")}</span>}
      />

      <section className="card doctor-mode-bar" aria-label={text("Select diagnosis mode", "Chọn chế độ chẩn đoán")}>
        <div><strong>{text("Diagnosis source", "Nguồn chẩn đoán")}</strong><small>{text("Live reads fresh telemetry; simulation sends no command to hardware.", "Live đọc telemetry mới; mô phỏng không gửi lệnh tới phần cứng.")}</small></div>
        <div className="doctor-mode-switch">
          <button type="button" className={mode === "live" ? "is-active" : ""} aria-pressed={mode === "live"} onClick={() => setMode("live")}><Activity size={16} /> Live Nebius</button>
          <button type="button" className={mode === "mock" ? "is-active" : ""} aria-pressed={mode === "mock"} disabled={!mockReady && capabilities !== null} onClick={() => setMode("mock")}><FlaskConical size={16} /> {text("Safe simulation", "Mô phỏng an toàn")}</button>
        </div>
      </section>

      {loadError && (
        <div className="connection-banner connection-banner--danger" role="alert">
          <AlertTriangle size={18} /><p><strong>{text("Diagnosis did not complete", "Chẩn đoán chưa hoàn tất")}</strong>{loadError}</p>
          {lastQuestion && <button type="button" className="doctor-retry" disabled={submitting} onClick={() => runDiagnosis(lastQuestion)}><RefreshCw size={15} className={submitting ? "spin" : ""} /> {text("Retry", "Thử lại")}</button>}
        </div>
      )}

      <section className="doctor-layout">
        <article className="card chat-panel">
          <div className="chat-panel__header"><span className="ai-avatar"><Bot size={21} /></span><div><strong>NeXus Doctor</strong><small><i className={`online-dot${canDiagnose ? "" : " online-dot--offline"}`} /> {mode === "live" ? (liveReady ? text("Nemotron + physical telemetry", "Nemotron + telemetry thật") : text("Live requirements not met", "Live chưa đủ điều kiện")) : text("Simulator · no hardware impact", "Simulator · không tác động phần cứng")}</small></div></div>
          <div className="chat-feed" role="log" aria-live="polite" aria-label={text("Diagnosis conversation", "Hội thoại chẩn đoán")}>
            {messages.map((message) => (
              <div className={`message message--${message.role}${message.error ? " message--error" : ""}`} key={message.id}>
                {message.role === "ai" && <span className="message__avatar"><Bot size={17} /></span>}
                <div><p>{message.text}</p>{message.evidence && <div className="message__evidence"><CheckCircle2 size={15} /><span><strong>{text("Evidence used", "Bằng chứng đã dùng")}</strong>{message.evidence}</span></div>}<time>{text("Just now", "Vừa xong")}</time></div>
                {message.role === "user" && <span className="message__avatar"><UserRound size={17} /></span>}
              </div>
            ))}
          </div>
          <div className="prompt-row" aria-label={text("Suggested questions", "Câu hỏi gợi ý")}>{prompts.map((prompt) => <button type="button" key={prompt} onClick={() => setQuestion(prompt)}>{prompt}</button>)}</div>
          <form className="composer" onSubmit={submit}>
            <MessageSquareText size={19} aria-hidden="true" /><label className="sr-only" htmlFor="doctor-question">{text("Ask AI Doctor", "Hỏi Bác sĩ AI")}</label>
            <input id="doctor-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={text("Describe a symptom or ask about the vehicle…", "Mô tả triệu chứng hoặc hỏi về xe…")} autoComplete="off" />
            <button type="submit" aria-label={text("Send question", "Gửi câu hỏi")} disabled={!question.trim() || submitting}><ArrowUp size={18} /></button>
          </form>
        </article>

        <aside className="diagnosis-panel" aria-label={text("Current assessment", "Đánh giá hiện tại")}>
          <article className="card panel">
            <div className="panel__header"><div><p className="eyebrow">{text("Current assessment", "Đánh giá hiện tại")}</p><h2>{assessment}</h2></div><span className="confidence">{confidence === null ? "--" : `${confidence}%`}</span></div>
            <p className="panel-copy">{assessmentCopy}</p><div className="confidence-bar" aria-label={confidence === null ? text("No model confidence yet", "Chưa có độ tin cậy từ model") : text(`Confidence ${confidence}%`, `Độ tin cậy ${confidence}%`)}><i style={{ width: `${confidence ?? 0}%` }} /></div>
            <div className="diagnosis-facts"><span><small>{text("Open alerts", "Cảnh báo mở")}</small><strong>{activeDiagnostics.length}</strong></span><span><small>{text("Physical commands", "Lệnh vật lý")}</small><strong>{capabilities?.physical_commands_enabled ? text("Enabled", "Được bật") : text("Locked", "Đã khóa")}</strong></span></div>
            {session && <button type="button" className="diagnosis-export" onClick={() => downloadJson(session)}><Download size={15} /> {text("Export JSON evidence", "Xuất bằng chứng JSON")}</button>}
          </article>
          <article className="card safety-card"><ShieldCheck size={22} /><div><strong>{text("Safety by design", "An toàn ngay từ thiết kế")}</strong><p>{text("Current alone is not proof that the motor rotated; dangerous commands must pass Safety Policy and independent verification.", "Không coi dòng điện là bằng chứng motor đã quay; lệnh nguy hiểm phải qua Safety Policy và verify độc lập.")}</p></div></article>
          <article className="card safety-card safety-card--info"><Sparkles size={22} /><div><strong>{text("No hidden reasoning shown", "Không hiển thị suy luận nội bộ")}</strong><p>{text("The UI shows only conclusions, evidence, tool calls, and auditable sessions returned by the backend.", "UI chỉ trình bày kết luận, evidence, tool call và session kiểm toán do backend trả về.")}</p></div></article>
        </aside>
      </section>

      <section className="card diagnosis-timeline" aria-labelledby="diagnosis-timeline-title">
        <div className="diagnosis-timeline__header"><div><p className="eyebrow">G06 · Diagnosis Timeline</p><h2 id="diagnosis-timeline-title">{text("From telemetry to verification", "Từ telemetry đến xác minh")}</h2></div><span>{result?.events.length ?? 0} {text("events", "sự kiện")}</span></div>
        {!result?.events.length ? <p className="diagnosis-timeline__empty">{text("Run a diagnosis to inspect the trace: ingest → hypothesis → policy → tool → verify.", "Chạy một lượt chẩn đoán để xem dấu vết: nhận dữ liệu → giả thuyết → policy → tool → verify.")}</p> : (
          <ol>{result.events.map((event) => {
            const labels: Record<LifecycleEventV1["event_type"], string> = {
              "telemetry.received": text("Telemetry received", "Đã nhận telemetry"), "diagnosis.proposed": text("AI proposed a hypothesis", "AI đưa ra giả thuyết"), "action.approved": text("Safety Policy approved", "Safety Policy phê duyệt"), "action.rejected": text("Safety Policy blocked the command", "Safety Policy chặn lệnh"), "action.executed": text("Tool executed", "Tool đã thực thi"), "verification.passed": text("Verification passed", "Xác minh đạt"), "verification.failed": text("Verification failed", "Xác minh không đạt"),
            };
            return <li key={event.event_id} className={`timeline-event timeline-event--${eventTone(event)}`}><i /><div><strong>{labels[event.event_type]}</strong><p>{event.summary}</p><small>{event.source} · {new Date(event.occurred_at).toLocaleTimeString(locale)}</small></div></li>;
          })}</ol>
        )}
      </section>

      <section className="treatment-grid" aria-label={text("Manual and automatic treatment", "Điều trị thủ công và tự động")}>
        <article className="card treatment-card treatment-card--manual">
          <header><span><Wrench size={18} /></span><div><p className="eyebrow">G07 · Manual Treatment</p><h2>{text("Controlled repair workflow", "Quy trình sửa có kiểm soát")}</h2></div></header>
          <ol><li><strong>{text("1. Safe stop", "1. Dừng an toàn")}</strong><span>{text("SW1 OFF, PWM 0%, and wheels off the ground before touching wires.", "SW1 OFF, PWM 0%, bánh rời mặt đất trước khi chạm dây.")}</span></li><li><strong>{text("2. Verify BOM", "2. Đối chiếu BOM")}</strong><span>{text("Profile, supply, INA219 SEN0291, both L298N drivers, encoders, and PS2 controller must match the configuration.", "Profile, nguồn, INA219 SEN0291, hai L298N, encoder và tay PS2 phải đúng cấu hình.")}</span></li><li><strong>{text("3. Change one variable", "3. Chỉ đổi một biến")}</strong><span>{text("Change one wire or setting at a time to preserve root-cause traceability.", "Sửa đúng một dây hoặc cấu hình để còn truy vết nguyên nhân.")}</span></li><li><strong>{text("4. Verify again", "4. Verify lại")}</strong><span>{text("Run a supervised test and compare before/after samples.", "Chạy test có giám sát và so sánh sample trước/sau.")}</span></li></ol>
        </article>
        <article className="card treatment-card treatment-card--auto">
          <header><span><ShieldCheck size={18} /></span><div><p className="eyebrow">G07 · Auto Treatment</p><h2>{text("Policy-gated, never fakes success", "Policy-gated, không giả thành công")}</h2></div></header>
          <p>{text("The simulator may execute a tool and verify the change. Physical-device MVP mode is read-only; motor commands stay locked until operator approval and E-stop verification.", "Simulator có thể chạy tool rồi verify thay đổi. Với thiết bị thật, MVP hiện chỉ đọc; lệnh motor bị khóa đến khi có operator approval và E-stop được kiểm chứng.")}</p>
          <div className="treatment-status"><Ban size={17} /><span><strong>{result?.physical_operation_verified ? text("Simulated operation verified", "Đã xác minh thao tác mô phỏng") : text("Physical commands are locked", "Lệnh vật lý đang khóa")}</strong>{result?.limitations?.[0] ?? text("No write operation was sent from the browser.", "Không có thao tác ghi nào được gửi từ trình duyệt.")}</span></div>
          {result?.events.some((event) => event.event_type === "action.rejected") && <div className="treatment-event"><CheckCircle2 size={16} /> {text("Safety Policy blocked at least one action that failed its conditions.", "Safety Policy đã chặn ít nhất một hành động không đạt điều kiện.")}</div>}
        </article>
      </section>
    </div>
  );
}
