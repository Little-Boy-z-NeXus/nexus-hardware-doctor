import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";
import { localizeDiagnostic } from "../i18n/runtimeCopy";

interface HardwareDiagnosticsPanelProps {
  mode: "single" | "dual";
}

export function HardwareDiagnosticsPanel({ mode }: HardwareDiagnosticsPanelProps) {
  const { language, text } = useI18n();
  const { snapshot, streamStatus } = useHardwareMonitor();
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const measurements = snapshot?.telemetry?.measurements;
  const dualMeasurements = measurements as typeof measurements & {
    rpm_left?: number | null;
    rpm_right?: number | null;
    rpm_rear?: number | null;
    pwm_left_percent?: number | null;
    pwm_right_percent?: number | null;
    pwm_rear_percent?: number | null;
    ps2_connected?: boolean;
  };
  const hasDualPacket = dualMeasurements?.rpm_left != null
    || dualMeasurements?.rpm_right != null
    || dualMeasurements?.rpm_rear != null
    || dualMeasurements?.pwm_left_percent != null
    || dualMeasurements?.pwm_right_percent != null
    || dualMeasurements?.pwm_rear_percent != null;

  return (
    <article className="card panel diagnostic-panel">
      <div className="panel__header">
        <div><p className="eyebrow">{text("Fault detection", "Nhận biết lỗi")}</p><h2>{text("Actions required", "Việc cần xử lý")}</h2></div>
        <AlertTriangle size={21} />
      </div>
      <div className="diagnostic-list">
        {streamStatus !== "live" && (
          <div className="diagnostic-item diagnostic-item--error" role="alert">
            <div><strong>{text("Cannot connect to backend", "Không kết nối được backend")}</strong><span>{text("The UI cannot receive real-time logs.", "UI không thể nhận log realtime.")}</span></div>
            <p><b>{text("Do this now:", "Làm ngay:")}</b> {text("Double-click", "Double-click")} <code>nexus-start-app.cmd</code> {text("and keep the Backend window open.", "và giữ cửa sổ Backend mở.")}</p>
          </div>
        )}
        {mode === "dual" && streamStatus === "live" && !hasDualPacket && (
          <div className="diagnostic-item diagnostic-item--warning" role="status">
            <div><strong>{text("No three-motor telemetry packet yet", "Chưa nhận gói telemetry ba motor")}</strong><span>THREE_WHEEL_TELEMETRY_PENDING</span></div>
            <p>{text("The backend and logs are running, but the firmware is not sending per-wheel RPM/PWM yet.", "Backend và log đã hoạt động, nhưng firmware hiện chưa gửi RPM/PWM riêng cho ba bánh.")}</p>
            <p><b>{text("Do this now:", "Làm ngay:")}</b> {text("Flash environment", "Nạp environment")} <code>nexus-esp32-s3-devkitc-3wheel-ps2</code> {text("with fields", "có các field")} <code>rpm_left</code>, <code>rpm_right</code>, <code>rpm_rear</code> {text("and", "và")} <code>ps2_connected</code>.</p>
          </div>
        )}
        {streamStatus === "live" && activeDiagnostics.length === 0 && (mode === "single" || hasDualPacket) && (
          <div className="diagnostic-empty">
            <CheckCircle2 size={24} />
            <strong>{text("No faults detected", "Chưa phát hiện lỗi")}</strong>
            <span>{text("NeXus continues to inspect every new packet.", "NeXus vẫn đang kiểm tra từng gói mới.")}</span>
          </div>
        )}
        {activeDiagnostics.map((item) => {
          const copy = localizeDiagnostic(item, language);
          return (
            <div className={`diagnostic-item diagnostic-item--${item.severity}`} key={item.code}>
              <div><strong>{copy.title}</strong><span>{item.code} · {item.occurrences} {text("consecutive samples", "mẫu liên tiếp")}</span></div>
              <p>{copy.message}</p>
              <p><b>{text("Do this now:", "Làm ngay:")}</b> {copy.action}</p>
            </div>
          );
        })}
      </div>
    </article>
  );
}
