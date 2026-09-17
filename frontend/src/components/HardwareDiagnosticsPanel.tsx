import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";

interface HardwareDiagnosticsPanelProps {
  mode: "single" | "dual";
}

export function HardwareDiagnosticsPanel({ mode }: HardwareDiagnosticsPanelProps) {
  const { snapshot, streamStatus } = useHardwareMonitor();
  const activeDiagnostics = snapshot?.diagnostics.filter((item) => item.active) ?? [];
  const measurements = snapshot?.telemetry?.measurements;
  const dualMeasurements = measurements as typeof measurements & {
    rpm_left?: number | null;
    rpm_right?: number | null;
    pwm_left_percent?: number | null;
    pwm_right_percent?: number | null;
  };
  const hasDualPacket = dualMeasurements?.rpm_left != null
    || dualMeasurements?.rpm_right != null
    || dualMeasurements?.pwm_left_percent != null
    || dualMeasurements?.pwm_right_percent != null;

  return (
    <article className="card panel diagnostic-panel">
      <div className="panel__header">
        <div><p className="eyebrow">Nhận biết lỗi</p><h2>Việc cần xử lý</h2></div>
        <AlertTriangle size={21} />
      </div>
      <div className="diagnostic-list">
        {streamStatus !== "live" && (
          <div className="diagnostic-item diagnostic-item--error" role="alert">
            <div><strong>Không kết nối được backend</strong><span>UI không thể nhận log realtime.</span></div>
            <p><b>Làm ngay:</b> Double-click <code>nexus-start-app.cmd</code> và giữ cửa sổ Backend mở.</p>
          </div>
        )}
        {mode === "dual" && streamStatus === "live" && !hasDualPacket && (
          <div className="diagnostic-item diagnostic-item--warning" role="status">
            <div><strong>Chưa nhận gói telemetry hai motor</strong><span>DUAL_MOTOR_TELEMETRY_PENDING</span></div>
            <p>Backend và log đã hoạt động, nhưng firmware hiện chưa gửi RPM/PWM riêng cho bánh trái và phải.</p>
            <p><b>Làm ngay:</b> Nạp firmware dual-motor có các field <code>rpm_left</code>, <code>rpm_right</code>, <code>pwm_left_percent</code> và <code>pwm_right_percent</code>.</p>
          </div>
        )}
        {streamStatus === "live" && activeDiagnostics.length === 0 && (mode === "single" || hasDualPacket) && (
          <div className="diagnostic-empty">
            <CheckCircle2 size={24} />
            <strong>Chưa phát hiện lỗi</strong>
            <span>NeXus vẫn đang kiểm tra từng gói mới.</span>
          </div>
        )}
        {activeDiagnostics.map((item) => (
          <div className={`diagnostic-item diagnostic-item--${item.severity}`} key={item.code}>
            <div><strong>{item.title}</strong><span>{item.code} · {item.occurrences} mẫu liên tiếp</span></div>
            <p>{item.message}</p>
            <p><b>Làm ngay:</b> {item.action}</p>
          </div>
        ))}
      </div>
    </article>
  );
}
