import { ArrowUp, Bot, CheckCircle2, MessageSquareText, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageHeader } from "../components/PageHeader";
import { env } from "../config/env";
import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";

interface ChatMessage {
  id: number;
  role: "ai" | "user";
  text: string;
  evidence?: string;
}

interface DiagnosisCapabilities {
  live_enabled: boolean;
  live_configured: boolean;
  physical_commands_enabled: boolean;
  serial_reads_enabled: boolean;
  serial_device_id: string | null;
}

interface DiagnosisResult {
  status: string;
  summary: string;
  plan: {
    confidence: number;
    user_message: string;
    stop_condition: string;
    hypotheses: Array<{
      id: string;
      label: string;
      confidence: number;
      evidence_ids: string[];
    }>;
  } | null;
  observations: Array<{
    evidence_id: string;
    tool_name: string;
    status: string;
  }>;
  model_runtime?: {
    provider: string;
    calls: Array<{ response_model?: string; requested_model?: string }>;
  };
  physical_commands_enabled: boolean;
}

interface DiagnosisSession {
  session_id: string;
  result: DiagnosisResult;
}

export function AIDoctorPage() {
  const { snapshot, hardwareProfile } = useHardwareMonitor();
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [capabilities, setCapabilities] = useState<DiagnosisCapabilities | null>(null);
  const [lastResult, setLastResult] = useState<DiagnosisResult | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "ai",
      text: "Hãy mô tả điều bạn nhìn hoặc nghe thấy. Tôi sẽ đối chiếu với telemetry đang có và chỉ đưa ra hướng xử lý trong giới hạn an toàn.",
    },
  ]);
  const telemetry = snapshot?.telemetry;
  const isLive = snapshot?.connection.status === "connected" && telemetry?.quality.source === "device";
  const activeDiagnostics = useMemo(
    () => snapshot?.diagnostics.filter((item) => item.active) ?? [],
    [snapshot],
  );
  const canUseModel = Boolean(
    isLive
      && telemetry?.quality.source === "device"
      && capabilities?.live_enabled
      && capabilities.live_configured
      && capabilities.serial_reads_enabled,
  );
  const assessment = lastResult?.plan?.hypotheses[0]?.label
    ?? activeDiagnostics[0]?.title
    ?? (isLive ? "Chưa chạy chẩn đoán Nemotron" : "Chờ dữ liệu trực tiếp");
  const confidence = lastResult?.plan
    ? Math.round(lastResult.plan.confidence * 100)
    : null;
  const assessmentCopy = lastResult?.plan?.user_message
    ?? activeDiagnostics[0]?.message
    ?? (isLive
      ? "Telemetry đang live. Hãy đặt câu hỏi để Nemotron đọc mẫu mới và đưa ra đánh giá có bằng chứng."
      : "Kết nối thiết bị thật để bắt đầu chẩn đoán.");
  const modeLabel = useMemo(() => telemetry?.quality.source === "device"
    ? canUseModel ? "Nemotron + telemetry thật" : "Telemetry thật · model chưa sẵn sàng"
    : telemetry?.quality.source === "replay"
      ? "Replay · không gọi chẩn đoán thật"
      : telemetry?.quality.source === "simulator"
        ? "Simulator · không gọi chẩn đoán thật"
        : "Chưa có dữ liệu", [telemetry?.quality.source, canUseModel]);
  const prompts = useMemo(() => {
    if (activeDiagnostics[0]) {
      return [
        `Giải thích ${activeDiagnostics[0].title}`,
        `Bước an toàn tiếp theo cho ${activeDiagnostics[0].code} là gì?`,
        "Đọc telemetry mới và kiểm tra lại",
      ];
    }
    if (telemetry) {
      return [
        `Đánh giá mẫu telemetry #${telemetry.sequence}`,
        `Dòng ${telemetry.measurements.current_ma.toFixed(1)} mA có hợp lý không?`,
        `Kiểm tra phòng ngừa theo ${hardwareProfile?.profile_id ?? "profile hiện tại"}`,
      ];
    }
    return ["Kiểm tra kết nối hiện tại"];
  }, [activeDiagnostics, telemetry, hardwareProfile?.profile_id]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${env.apiBaseUrl}/api/diagnosis/capabilities`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<DiagnosisCapabilities>;
      })
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
    return () => controller.abort();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || submitting) return;
    const messageId = Date.now();
    setMessages((current) => [...current, { id: messageId, role: "user", text: trimmed }]);
    setQuestion("");
    if (!canUseModel || !telemetry) {
      setMessages((current) => [...current, {
        id: messageId + 1,
        role: "ai",
        text: "Chưa thể gọi Nemotron bằng dữ liệu thật. Hãy kiểm tra kết nối board, source=device và cấu hình model trên backend.",
        evidence: "Không tạo kết luận khi thiếu runtime thật",
      }]);
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(
        `${env.apiBaseUrl}/api/devices/${encodeURIComponent(telemetry.device_id)}/diagnoses`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symptom: trimmed,
            mode: "live",
            max_steps: 6,
            require_fresh_read: true,
          }),
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(payload.detail ?? `HTTP ${response.status}`);
      }
      const session = await response.json() as DiagnosisSession;
      const result = session.result;
      setLastResult(result);
      const modelCall = result.model_runtime?.calls.at(-1);
      const model = modelCall?.response_model ?? modelCall?.requested_model ?? "model runtime";
      const evidenceIds = Array.from(new Set(
        result.plan?.hypotheses.flatMap((item) => item.evidence_ids) ?? [],
      ));
      const tools = result.observations
        .filter((item) => item.status === "succeeded")
        .map((item) => item.tool_name);
      const evidence = [
        `${result.model_runtime?.provider ?? "provider"}/${model}`,
        tools.length ? `tool ${tools.join(", ")}` : null,
        evidenceIds.length ? `${evidenceIds.length} bằng chứng` : null,
        `session ${session.session_id.slice(0, 8)}`,
      ].filter(Boolean).join(" · ");
      setMessages((current) => [...current, {
        id: messageId + 1,
        role: "ai",
        text: result.plan?.user_message ?? result.summary,
        evidence,
      }]);
    } catch (error) {
      setMessages((current) => [...current, {
        id: messageId + 1,
        role: "ai",
        text: `Không thể hoàn tất lượt chẩn đoán: ${error instanceof Error ? error.message : "lỗi không xác định"}`,
        evidence: "Backend không trả về kết quả model hợp lệ",
      }]);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Không gian chẩn đoán" title="Bác sĩ AI" description="Mỗi câu hỏi gọi backend, đọc một mẫu serial mới và nhận kết quả có bằng chứng từ Nemotron." action={<span className={`status-pill status-pill--${canUseModel ? "healthy" : "warning"}`}><ShieldCheck size={14} /> {canUseModel ? "Nemotron đã sẵn sàng" : "Đang chờ runtime thật"}</span>} />

      <section className="doctor-layout">
        <article className="card chat-panel">
          <div className="chat-panel__header"><span className="ai-avatar"><Bot size={21} /></span><div><strong>NeXus Doctor</strong><small><i className={`online-dot${isLive ? "" : " online-dot--offline"}`} /> {modeLabel}</small></div></div>
          <div className="chat-feed" role="log" aria-live="polite" aria-label="Hội thoại chẩn đoán">
            {messages.map((message) => (
              <div className={`message message--${message.role}`} key={message.id}>
                {message.role === "ai" && <span className="message__avatar"><Bot size={17} /></span>}
                <div>
                  <p>{message.text}</p>
                  {message.evidence && <div className="message__evidence"><CheckCircle2 size={15} /><span><strong>Bằng chứng đã dùng</strong>{message.evidence}</span></div>}
                  <time>Vừa xong</time>
                </div>
                {message.role === "user" && <span className="message__avatar"><UserRound size={17} /></span>}
              </div>
            ))}
          </div>
          <div className="prompt-row" aria-label="Câu hỏi gợi ý">{prompts.map((prompt) => <button type="button" key={prompt} onClick={() => setQuestion(prompt)}>{prompt}</button>)}</div>
          <form className="composer" onSubmit={submit}>
            <MessageSquareText size={19} aria-hidden="true" />
            <label className="sr-only" htmlFor="doctor-question">Hỏi Bác sĩ AI</label>
            <input id="doctor-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Mô tả triệu chứng hoặc hỏi về bộ demo…" autoComplete="off" />
            <button type="submit" aria-label="Gửi câu hỏi" disabled={!question.trim() || submitting}><ArrowUp size={18} /></button>
          </form>
        </article>

        <aside className="diagnosis-panel" aria-label="Đánh giá hiện tại">
          <article className="card panel">
            <div className="panel__header"><div><p className="eyebrow">Đánh giá hiện tại</p><h2>{assessment}</h2></div><span className="confidence">{confidence === null ? "--" : `${confidence}%`}</span></div>
            <p className="panel-copy">{assessmentCopy}</p>
            <div className="confidence-bar" aria-label={confidence === null ? "Chưa có độ tin cậy từ model" : `Độ tin cậy ${confidence}%`}><i style={{ width: `${confidence ?? 0}%` }} /></div>
            <div className="diagnosis-facts"><span><small>Cảnh báo mở</small><strong>{activeDiagnostics.length}</strong></span><span><small>Hành động vật lý</small><strong>{capabilities?.physical_commands_enabled ? "Được bật" : "Đã khóa"}</strong></span></div>
          </article>
          <article className="card safety-card"><ShieldCheck size={22} /><div><strong>An toàn ngay từ thiết kế</strong><p>NeXus nêu rõ bằng chứng, không coi dòng điện là bằng chứng motor đã quay và không gửi lệnh vật lý từ màn hình này.</p></div></article>
          <article className="card safety-card safety-card--info"><Sparkles size={22} /><div><strong>Runtime có thể kiểm chứng</strong><p>UI chỉ hiển thị kết quả backend cùng model, tool, evidence và session thực tế; không tự dựng câu trả lời.</p></div></article>
        </aside>
      </section>
    </div>
  );
}
