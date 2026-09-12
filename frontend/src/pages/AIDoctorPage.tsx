import { ArrowUp, Bot, CheckCircle2, MessageSquareText, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { PageHeader } from "../components/PageHeader";
import { useHardwareMonitor, type HardwareSnapshot } from "../realtime/HardwareMonitorContext";

const prompts = ["Dòng điện hiện tại thế nào?", "Kiểm tra phòng ngừa", "Motor có đang an toàn không?"];

interface ChatMessage {
  id: number;
  role: "ai" | "user";
  text: string;
  evidence?: string;
}

function explainSnapshot(question: string, snapshot: HardwareSnapshot, isLive: boolean) {
  const telemetry = snapshot.telemetry;
  const measurements = telemetry?.measurements;
  const issue = snapshot.diagnostics.find((item) => item.active);
  const normalized = question.toLocaleLowerCase("vi");

  if (!isLive) {
    return {
      text: `Tôi chưa có telemetry trực tiếp. ${snapshot.connection.message}`,
      evidence: "Chưa có gói ESP32 mới · Không đề xuất thao tác motor",
    };
  }
  if (issue) {
    return {
      text: `${issue.title}. ${issue.message} Việc nên làm: ${issue.action}`,
      evidence: `${issue.code} · ${issue.occurrences} mẫu liên tiếp`,
    };
  }
  if (!measurements || !telemetry) {
    return {
      text: "Backend đã kết nối nhưng chưa có mẫu telemetry hợp lệ để kết luận.",
      evidence: "Đang chờ INA226 và ESP32 gửi đủ dữ liệu",
    };
  }

  const source = telemetry.quality.source === "device" ? "thiết bị thật" : telemetry.quality.source;
  if (normalized.includes("dòng") || normalized.includes("current")) {
    return {
      text: `Dòng hiện tại là ${measurements.current_ma.toFixed(1)} mA, công suất ${measurements.power_mw.toFixed(1)} mW. NeXus chưa thấy cảnh báo dòng vượt giới hạn.`,
      evidence: `INA226 · ${source} · mẫu #${telemetry.sequence}`,
    };
  }
  if (normalized.includes("nguồn") || normalized.includes("điện áp") || normalized.includes("voltage")) {
    return {
      text: `Điện áp bus đang là ${measurements.bus_voltage_v.toFixed(2)} V, nằm trong cửa sổ an toàn 9,5–13,0 V của MVP.`,
      evidence: `INA226 · chất lượng ${telemetry.quality.signal_quality_percent}%`,
    };
  }
  if (normalized.includes("motor") || normalized.includes("an toàn") || normalized.includes("safe")) {
    const driver = measurements.driver_enabled ? `driver đang bật ở PWM ${measurements.pwm_percent}%` : "driver đang tắt và PWM bằng 0";
    return {
      text: `Theo telemetry điện, ${driver}. ${measurements.motor_rpm == null ? "Encoder chưa có RPM nên NeXus không khẳng định chuyển động cơ học." : `Tốc độ đo được là ${measurements.motor_rpm.toFixed(0)} RPM.`}`,
      evidence: `L298N + INA226 · ${source} · không tự chạy lệnh vật lý`,
    };
  }
  return {
    text: `Hệ thống điện đang ổn định: ${measurements.bus_voltage_v.toFixed(2)} V, ${measurements.current_ma.toFixed(1)} mA, PWM ${measurements.pwm_percent}%. Tôi chưa thấy cảnh báo đang mở.`,
    evidence: `Telemetry ${source} · mẫu #${telemetry.sequence}`,
  };
}

export function AIDoctorPage() {
  const { snapshot, streamStatus } = useHardwareMonitor();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "ai",
      text: "Hãy mô tả điều bạn nhìn hoặc nghe thấy. Tôi sẽ đối chiếu với telemetry đang có và chỉ đưa ra hướng xử lý trong giới hạn an toàn.",
    },
  ]);
  const isLive = streamStatus === "live" && snapshot.connection.status === "connected";
  const activeDiagnostics = snapshot.diagnostics.filter((item) => item.active);
  const assessment = activeDiagnostics[0]?.title ?? (isLive ? "Tín hiệu điện ổn định" : "Chờ dữ liệu trực tiếp");
  const confidence = isLive ? (activeDiagnostics.length ? 88 : 94) : 0;
  const assessmentCopy = activeDiagnostics[0]?.message ?? (isLive
    ? "Chưa có cảnh báo đang mở trong các giới hạn MVP đã khóa."
    : "Kết nối ESP32 hoặc chạy replay để bắt đầu chẩn đoán theo dữ liệu.");
  const modeLabel = useMemo(() => snapshot.telemetry?.quality.source === "replay" ? "Replay" : isLive ? "Telemetry trực tiếp" : "Chưa có dữ liệu", [snapshot.telemetry?.quality.source, isLive]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    const answer = explainSnapshot(trimmed, snapshot, isLive);
    setMessages((current) => [
      ...current,
      { id: current.length + 1, role: "user", text: trimmed },
      { id: current.length + 2, role: "ai", text: answer.text, evidence: answer.evidence },
    ]);
    setQuestion("");
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Không gian chẩn đoán" title="Bác sĩ AI" description="Hỏi bằng tiếng Việt; NeXus trả lời từ telemetry và cảnh báo đang hiển thị, không tự kích hoạt phần cứng." action={<span className="status-pill status-pill--healthy"><ShieldCheck size={14} /> Safety policy đang bật</span>} />

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
            <button type="submit" aria-label="Gửi câu hỏi" disabled={!question.trim()}><ArrowUp size={18} /></button>
          </form>
        </article>

        <aside className="diagnosis-panel" aria-label="Đánh giá hiện tại">
          <article className="card panel">
            <div className="panel__header"><div><p className="eyebrow">Đánh giá hiện tại</p><h2>{assessment}</h2></div><span className="confidence">{confidence ? `${confidence}%` : "--"}</span></div>
            <p className="panel-copy">{assessmentCopy}</p>
            <div className="confidence-bar" aria-label={`Độ tin cậy ${confidence}%`}><i style={{ width: `${confidence}%` }} /></div>
            <div className="diagnosis-facts"><span><small>Cảnh báo mở</small><strong>{activeDiagnostics.length}</strong></span><span><small>Hành động vật lý</small><strong>Đã khóa</strong></span></div>
          </article>
          <article className="card safety-card"><ShieldCheck size={22} /><div><strong>An toàn ngay từ thiết kế</strong><p>NeXus nêu rõ bằng chứng, không coi dòng điện là bằng chứng motor đã quay và không gửi lệnh vật lý từ màn hình này.</p></div></article>
          <article className="card safety-card safety-card--info"><Sparkles size={22} /><div><strong>Phản hồi tức thì</strong><p>Chẩn đoán nhanh trên UI dùng rules đã khóa. Chế độ Nemotron vẫn do backend kiểm soát khi được cấu hình.</p></div></article>
        </aside>
      </section>
    </div>
  );
}
