import {
  ChevronDown,
  ChevronsDown,
  Circle,
  Download,
  Pause,
  Play,
  Search,
  Square,
  TerminalSquare,
  Trash2,
} from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useHardwareMonitor, type LiveLog } from "../realtime/HardwareMonitorContext";
import { useI18n, type Language } from "../i18n/I18nContext";

interface TelemetryLogPayload {
  sequence?: number;
  device_id?: string;
  measurements?: {
    bus_voltage_v?: number | null;
    current_ma?: number | null;
    total_current_ma?: number | null;
    power_mw?: number | null;
    pwm_percent?: number | null;
    driver_enabled?: boolean | null;
    motor_rpm?: number | null;
    rpm_left?: number | null;
    rpm_right?: number | null;
    rpm_rear?: number | null;
    rpm_delta?: number | null;
    pwm_left_percent?: number | null;
    pwm_right_percent?: number | null;
    pwm_rear_percent?: number | null;
    pid_state?: string | null;
    ps2_connected?: boolean;
    ps2_failsafe_active?: boolean;
  };
}

interface LogPresentation {
  title: string;
  summary: string;
  raw: string;
  telemetry: TelemetryLogPayload | null;
}

interface HardwareLiveLogProps {
  title?: string;
  ariaLabel?: string;
  mode: "single" | "dual";
}

const timeLabel = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(value))
    : "--:--:--";

const valueOrDash = (value: number | null | undefined, digits = 2) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

function logPresentation(item: LiveLog, language: Language): LogPresentation {
  const text = (en: string, vi: string) => language === "vi" ? vi : en;
  const message = item.message.trim();
  if (message.startsWith("{")) {
    try {
      const payload = JSON.parse(message) as TelemetryLogPayload;
      if (payload.measurements && typeof payload.measurements === "object") {
        return {
          title: `Telemetry${payload.sequence == null ? "" : ` #${payload.sequence}`}`,
          summary: payload.device_id ? text(`Device ${payload.device_id}`, `Thiết bị ${payload.device_id}`) : text("New measurement packet from device", "Gói đo mới từ thiết bị"),
          raw: JSON.stringify(payload, null, 2),
          telemetry: payload,
        };
      }
    } catch {
      // Keep partial firmware JSON visible so wiring/serial faults remain debuggable.
    }
  }

  if (message.includes("[HARDWARE_PROFILE]")) {
    const profileId = message.match(/profile_id=([^\s]+)/)?.[1];
    return {
      title: text("Hardware configuration verified", "Cấu hình phần cứng đã xác nhận"),
      summary: profileId ? `Profile ${profileId}` : text("Firmware sent its hardware fingerprint", "Firmware đã gửi hardware fingerprint"),
      raw: message,
      telemetry: null,
    };
  }

  if (message.includes("[SIGNAL_MONITOR_READY]")) {
    return {
      title: text("Signal wire monitor is ready", "Bộ giám sát dây tín hiệu đã sẵn sàng"),
      summary: text("SDA/SCL are checked on every sample; encoder A/B are checked while the motor runs.", "SDA/SCL được kiểm tra ở từng mẫu; encoder A/B được kiểm tra khi motor chạy."),
      raw: message,
      telemetry: null,
    };
  }

  return {
    title: {
      error: text("Hardware fault", "Lỗi phần cứng"),
      warning: text("Warning to inspect", "Cảnh báo cần kiểm tra"),
      telemetry: "Telemetry",
      info: text("System information", "Thông tin hệ thống"),
    }[item.level],
    summary: message,
    raw: message,
    telemetry: null,
  };
}

function downloadLogFile(logs: LiveLog[], suffix: string) {
  const body = logs
    .map((item) => `[${item.occurred_at}] [${item.level.toUpperCase()}] [${item.source}] ${item.message}`)
    .join("\n");
  const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `nexus-${suffix}-${new Date().toISOString().replaceAll(":", "-")}.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function HardwareLiveLog({
  title,
  ariaLabel,
  mode,
}: HardwareLiveLogProps) {
  const { language, locale, text } = useI18n();
  const resolvedTitle = title ?? "ESP32 Live Log";
  const resolvedAriaLabel = ariaLabel ?? text("Real-time ESP32 log", "Log realtime từ ESP32");
  const { snapshot } = useHardwareMonitor();
  const logs = useMemo(() => snapshot?.logs ?? [], [snapshot?.logs]);
  const [pausedLogs, setPausedLogs] = useState<LiveLog[] | null>(null);
  const [hiddenBefore, setHiddenBefore] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const [logLevel, setLogLevel] = useState<"all" | LiveLog["level"]>("all");
  const [followLatest, setFollowLatest] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedLogs, setRecordedLogs] = useState<LiveLog[]>([]);
  const [recordingStartedAt, setRecordingStartedAt] = useState<string | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const userLogScrollRef = useRef(false);
  const recordedIdsRef = useRef(new Set<string>());

  const visibleLogs = (pausedLogs ?? logs).filter((item) => {
    const afterClear = !hiddenBefore || item.occurred_at > hiddenBefore;
    const levelMatches = logLevel === "all" || item.level === logLevel;
    const query = logQuery.trim().toLocaleLowerCase("vi");
    const queryMatches = !query || item.message.toLocaleLowerCase("vi").includes(query);
    return afterClear && levelMatches && queryMatches;
  });
  const latestVisibleLog = visibleLogs.at(-1);
  const savedLogName = snapshot?.connection.log_file?.split(/[\\/]/).pop() ?? text("waiting for log", "đang chờ log");

  useEffect(() => {
    if (!isRecording || !recordingStartedAt) return;
    const additions = logs.filter(
      (item) => item.occurred_at >= recordingStartedAt && !recordedIdsRef.current.has(item.id),
    );
    if (!additions.length) return;
    additions.forEach((item) => recordedIdsRef.current.add(item.id));
    setRecordedLogs((current) => [...current, ...additions]);
  }, [isRecording, logs, recordingStartedAt]);

  useLayoutEffect(() => {
    if (!pausedLogs && followLatest && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [latestVisibleLog?.id, pausedLogs, followLatest, logLevel, logQuery]);

  const jumpToLatest = () => {
    userLogScrollRef.current = false;
    setFollowLatest(true);
    requestAnimationFrame(() => {
      terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const handleLogScroll = () => {
    if (!terminalRef.current || !userLogScrollRef.current) return;
    const distanceFromBottom = terminalRef.current.scrollHeight
      - terminalRef.current.scrollTop
      - terminalRef.current.clientHeight;
    const isAtLatest = distanceFromBottom <= 32;
    setFollowLatest(isAtLatest);
    if (isAtLatest) userLogScrollRef.current = false;
  };

  const togglePause = () => setPausedLogs((current) => {
    if (current) {
      userLogScrollRef.current = false;
      setFollowLatest(true);
      return null;
    }
    return [...logs];
  });

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      return;
    }
    const startedAt = new Date().toISOString();
    recordedIdsRef.current = new Set();
    setRecordedLogs([]);
    setRecordingStartedAt(startedAt);
    setIsRecording(true);
  };

  return (
    <article className="card terminal-card" data-testid={`hardware-live-log-${mode}`}>
      <div className="terminal-card__header">
        <div className="terminal-card__title">
          <span className="terminal-card__icon"><TerminalSquare size={18} /></span>
          <span>
            <strong>{resolvedTitle}</strong>
            <small className={pausedLogs ? "is-paused" : followLatest ? "is-following" : "is-browsing"}>
              <i aria-hidden="true" />
              {pausedLogs
                ? text("Paused", "Đã tạm dừng")
                : followLatest
                  ? text("Following the latest log", "Đang theo dõi log mới nhất")
                  : text("Viewing older logs", "Bạn đang xem log cũ")}
            </small>
          </span>
        </div>
        <div className="terminal-actions">
          <button
            className={isRecording ? "is-recording" : ""}
            type="button"
            onClick={toggleRecording}
            aria-pressed={isRecording}
          >
            {isRecording ? <Square size={13} /> : <Circle size={13} />}
            {isRecording ? text("Stop recording", "Dừng ghi") : text("Start recording", "Bắt đầu ghi")}
          </button>
          <button type="button" onClick={togglePause}>
            {pausedLogs ? <Play size={14} /> : <Pause size={14} />}
            {pausedLogs ? text("Resume", "Tiếp tục") : text("Pause", "Tạm dừng")}
          </button>
          <button type="button" onClick={() => {
            userLogScrollRef.current = false;
            setHiddenBefore(new Date().toISOString());
            setFollowLatest(true);
          }}><Trash2 size={14} />{text("Hide old logs", "Ẩn log cũ")}</button>
          <button type="button" onClick={() => downloadLogFile(visibleLogs, `${mode}-live-log`)} disabled={!visibleLogs.length}>
            <Download size={14} />{text("Download log", "Tải log")}
          </button>
        </div>
      </div>

      <div className="terminal-recording" data-active={isRecording ? "true" : "false"} aria-live="polite">
        <span><i aria-hidden="true" />{isRecording ? text("Recording test session", "Đang ghi phiên kiểm thử") : recordedLogs.length ? text("Recording stopped", "Phiên ghi đã dừng") : text("No separate recording", "Chưa ghi phiên riêng")}</span>
        <strong>{recordedLogs.length} {text("records", "bản ghi")}</strong>
        {recordingStartedAt && <small>{text("Started", "Bắt đầu")} {timeLabel(recordingStartedAt, locale)}</small>}
        <button type="button" onClick={() => downloadLogFile(recordedLogs, `${mode}-recording`)} disabled={!recordedLogs.length}>
          <Download size={13} />{text("Download recording", "Tải phiên ghi")}
        </button>
      </div>

      <div className="terminal-toolbar">
        <label>
          <Search size={15} aria-hidden="true" />
          <span className="sr-only">{text("Search logs", "Tìm trong log")}</span>
          <input value={logQuery} onChange={(event) => setLogQuery(event.target.value)} placeholder={text("Search error code or value…", "Tìm mã lỗi hoặc giá trị…")} />
        </label>
        <select value={logLevel} onChange={(event) => setLogLevel(event.target.value as typeof logLevel)} aria-label={text("Filter logs by level", "Lọc log theo mức")}>
          <option value="all">{text("All levels", "Tất cả mức")}</option>
          <option value="error">{text("Error", "Lỗi")}</option>
          <option value="warning">{text("Warning", "Cảnh báo")}</option>
          <option value="telemetry">Telemetry</option>
          <option value="info">{text("Information", "Thông tin")}</option>
        </select>
        <span className="terminal-toolbar__count"><strong>{visibleLogs.length}</strong> {text("records", "bản ghi")}</span>
      </div>

      <div className="terminal-card__meta">
        <span>{text("Backend is saving", "Backend đang lưu")} <strong title={savedLogName}>{savedLogName}</strong></span>
        {latestVisibleLog && <span>{text("Latest at", "Mới nhất lúc")} <strong>{timeLabel(latestVisibleLog.occurred_at, locale)}</strong></span>}
      </div>

      <div
        className="terminal-feed"
        ref={terminalRef}
        role="log"
        aria-label={resolvedAriaLabel}
        aria-live="off"
        tabIndex={0}
        onScroll={handleLogScroll}
        onWheel={() => { userLogScrollRef.current = true; }}
        onTouchStart={() => { userLogScrollRef.current = true; }}
        onPointerDown={(event) => {
          if (event.target === event.currentTarget) userLogScrollRef.current = true;
        }}
        onKeyDown={(event) => {
          if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(event.key)) {
            userLogScrollRef.current = true;
          }
        }}
      >
        {visibleLogs.length === 0 && (
          <p className="terminal-empty">{text("Firmware logs will appear here as soon as ESP32 sends data.", "Log firmware sẽ hiện tại đây ngay khi ESP32 gửi dữ liệu.")}</p>
        )}
        {visibleLogs.map((item, index) => {
          const presentation = logPresentation(item, language);
          const metrics = presentation.telemetry?.measurements;
          const hasDualMetrics = metrics?.rpm_left != null || metrics?.rpm_right != null || metrics?.rpm_rear != null;
          return (
            <article
              className={`terminal-line terminal-line--${item.level}`}
              data-latest={index === visibleLogs.length - 1 ? "true" : undefined}
              key={item.id}
            >
              <div className="terminal-line__meta">
                <time>{timeLabel(item.occurred_at, locale)}</time>
                <span>{item.level === "telemetry" ? "Telemetry" : item.level === "info" ? text("Information", "Thông tin") : item.level === "warning" ? text("Warning", "Cảnh báo") : text("Error", "Lỗi")}</span>
              </div>
              <div className="terminal-line__content">
                <div className="terminal-line__heading">
                  <strong>{presentation.title}</strong>
                  <small>{item.source === "firmware" ? "Firmware" : "Backend"}</small>
                </div>
                {metrics ? (
                  <div className={`terminal-metrics${hasDualMetrics ? " terminal-metrics--dual" : ""}`} aria-label={text(`${presentation.title} measurements`, `Số đo ${presentation.title}`)}>
                    <span><small>{text("Voltage", "Điện áp")}</small><strong>{valueOrDash(metrics.bus_voltage_v, 3)} V</strong></span>
                    <span><small>{text("Total current", "Dòng tổng")}</small><strong>{valueOrDash(metrics.total_current_ma ?? metrics.current_ma, 1)} mA</strong></span>
                    {hasDualMetrics ? <>
                      <span><small>{text("Left RPM", "RPM trái")}</small><strong>{valueOrDash(metrics.rpm_left, 0)}</strong></span>
                      <span><small>{text("Right RPM", "RPM phải")}</small><strong>{valueOrDash(metrics.rpm_right, 0)}</strong></span>
                      <span><small>{text("Rear RPM", "RPM sau")}</small><strong>{valueOrDash(metrics.rpm_rear, 0)}</strong></span>
                      <span><small>Δ RPM</small><strong>{valueOrDash(metrics.rpm_delta, 0)}</strong></span>
                      <span><small>{text("Left/right/rear PWM", "PWM trái/phải/sau")}</small><strong>{valueOrDash(metrics.pwm_left_percent, 0)} / {valueOrDash(metrics.pwm_right_percent, 0)} / {valueOrDash(metrics.pwm_rear_percent, 0)}%</strong></span>
                      <span><small>{text("PS2 controller", "Tay PS2")}</small><strong>{metrics.ps2_connected && !metrics.ps2_failsafe_active ? text("Connected", "Đã nối") : "Failsafe"}</strong></span>
                    </> : <>
                      <span><small>{text("Power", "Công suất")}</small><strong>{valueOrDash(metrics.power_mw, 1)} mW</strong></span>
                      <span><small>Motor</small><strong>{metrics.driver_enabled ? text(`On · ${metrics.pwm_percent ?? 0}%`, `Bật · ${metrics.pwm_percent ?? 0}%`) : text("Off", "Tắt")}</strong></span>
                    </>}
                  </div>
                ) : (
                  <p>{presentation.summary}</p>
                )}
                <details className="terminal-raw">
                  <summary><ChevronDown size={14} /> {text("View raw data", "Xem dữ liệu gốc")}</summary>
                  <pre>{presentation.raw}</pre>
                </details>
              </div>
            </article>
          );
        })}
        {!followLatest && visibleLogs.length > 0 && !pausedLogs && (
          <button className="terminal-jump" type="button" onClick={jumpToLatest}>
            <ChevronsDown size={16} />{text("Go to latest log", "Về log mới nhất")}
          </button>
        )}
      </div>
    </article>
  );
}
