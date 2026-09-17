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
    rpm_delta?: number | null;
    pwm_left_percent?: number | null;
    pwm_right_percent?: number | null;
    pid_state?: string | null;
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

const timeLabel = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(value))
    : "--:--:--";

const valueOrDash = (value: number | null | undefined, digits = 2) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";

function logPresentation(item: LiveLog): LogPresentation {
  const message = item.message.trim();
  if (message.startsWith("{")) {
    try {
      const payload = JSON.parse(message) as TelemetryLogPayload;
      if (payload.measurements && typeof payload.measurements === "object") {
        return {
          title: `Telemetry${payload.sequence == null ? "" : ` #${payload.sequence}`}`,
          summary: payload.device_id ? `Thiết bị ${payload.device_id}` : "Gói đo mới từ thiết bị",
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
      title: "Cấu hình phần cứng đã xác nhận",
      summary: profileId ? `Profile ${profileId}` : "Firmware đã gửi hardware fingerprint",
      raw: message,
      telemetry: null,
    };
  }

  if (message.includes("[SIGNAL_MONITOR_READY]")) {
    return {
      title: "Bộ giám sát dây tín hiệu đã sẵn sàng",
      summary: "SDA/SCL được kiểm tra ở từng mẫu; encoder A/B được kiểm tra khi motor chạy.",
      raw: message,
      telemetry: null,
    };
  }

  return {
    title: {
      error: "Lỗi phần cứng",
      warning: "Cảnh báo cần kiểm tra",
      telemetry: "Telemetry",
      info: "Thông tin hệ thống",
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
  title = "ESP32 Live Log",
  ariaLabel = "Log realtime từ ESP32",
  mode,
}: HardwareLiveLogProps) {
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
  const savedLogName = snapshot?.connection.log_file?.split(/[\\/]/).pop() ?? "đang chờ log";

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
            <strong>{title}</strong>
            <small className={pausedLogs ? "is-paused" : followLatest ? "is-following" : "is-browsing"}>
              <i aria-hidden="true" />
              {pausedLogs
                ? "Đã tạm dừng"
                : followLatest
                  ? "Đang theo dõi log mới nhất"
                  : "Bạn đang xem log cũ"}
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
            {isRecording ? "Dừng ghi" : "Bắt đầu ghi"}
          </button>
          <button type="button" onClick={togglePause}>
            {pausedLogs ? <Play size={14} /> : <Pause size={14} />}
            {pausedLogs ? "Tiếp tục" : "Tạm dừng"}
          </button>
          <button type="button" onClick={() => {
            userLogScrollRef.current = false;
            setHiddenBefore(new Date().toISOString());
            setFollowLatest(true);
          }}><Trash2 size={14} />Ẩn log cũ</button>
          <button type="button" onClick={() => downloadLogFile(visibleLogs, `${mode}-live-log`)} disabled={!visibleLogs.length}>
            <Download size={14} />Tải log
          </button>
        </div>
      </div>

      <div className="terminal-recording" data-active={isRecording ? "true" : "false"} aria-live="polite">
        <span><i aria-hidden="true" />{isRecording ? "Đang ghi phiên kiểm thử" : recordedLogs.length ? "Phiên ghi đã dừng" : "Chưa ghi phiên riêng"}</span>
        <strong>{recordedLogs.length} bản ghi</strong>
        {recordingStartedAt && <small>Bắt đầu {timeLabel(recordingStartedAt)}</small>}
        <button type="button" onClick={() => downloadLogFile(recordedLogs, `${mode}-recording`)} disabled={!recordedLogs.length}>
          <Download size={13} />Tải phiên ghi
        </button>
      </div>

      <div className="terminal-toolbar">
        <label>
          <Search size={15} aria-hidden="true" />
          <span className="sr-only">Tìm trong log</span>
          <input value={logQuery} onChange={(event) => setLogQuery(event.target.value)} placeholder="Tìm mã lỗi hoặc giá trị…" />
        </label>
        <select value={logLevel} onChange={(event) => setLogLevel(event.target.value as typeof logLevel)} aria-label="Lọc log theo mức">
          <option value="all">Tất cả mức</option>
          <option value="error">Lỗi</option>
          <option value="warning">Cảnh báo</option>
          <option value="telemetry">Telemetry</option>
          <option value="info">Thông tin</option>
        </select>
        <span className="terminal-toolbar__count"><strong>{visibleLogs.length}</strong> bản ghi</span>
      </div>

      <div className="terminal-card__meta">
        <span>Backend đang lưu <strong title={savedLogName}>{savedLogName}</strong></span>
        {latestVisibleLog && <span>Mới nhất lúc <strong>{timeLabel(latestVisibleLog.occurred_at)}</strong></span>}
      </div>

      <div
        className="terminal-feed"
        ref={terminalRef}
        role="log"
        aria-label={ariaLabel}
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
          <p className="terminal-empty">Log firmware sẽ hiện tại đây ngay khi ESP32 gửi dữ liệu.</p>
        )}
        {visibleLogs.map((item, index) => {
          const presentation = logPresentation(item);
          const metrics = presentation.telemetry?.measurements;
          const hasDualMetrics = metrics?.rpm_left != null || metrics?.rpm_right != null;
          return (
            <article
              className={`terminal-line terminal-line--${item.level}`}
              data-latest={index === visibleLogs.length - 1 ? "true" : undefined}
              key={item.id}
            >
              <div className="terminal-line__meta">
                <time>{timeLabel(item.occurred_at)}</time>
                <span>{item.level === "telemetry" ? "Telemetry" : item.level === "info" ? "Thông tin" : item.level === "warning" ? "Cảnh báo" : "Lỗi"}</span>
              </div>
              <div className="terminal-line__content">
                <div className="terminal-line__heading">
                  <strong>{presentation.title}</strong>
                  <small>{item.source === "firmware" ? "Firmware" : "Backend"}</small>
                </div>
                {metrics ? (
                  <div className={`terminal-metrics${hasDualMetrics ? " terminal-metrics--dual" : ""}`} aria-label={`Số đo ${presentation.title}`}>
                    <span><small>Điện áp</small><strong>{valueOrDash(metrics.bus_voltage_v, 3)} V</strong></span>
                    <span><small>Dòng tổng</small><strong>{valueOrDash(metrics.total_current_ma ?? metrics.current_ma, 1)} mA</strong></span>
                    {hasDualMetrics ? <>
                      <span><small>RPM trái</small><strong>{valueOrDash(metrics.rpm_left, 0)}</strong></span>
                      <span><small>RPM phải</small><strong>{valueOrDash(metrics.rpm_right, 0)}</strong></span>
                      <span><small>Δ RPM</small><strong>{valueOrDash(metrics.rpm_delta, 0)}</strong></span>
                      <span><small>PWM trái/phải</small><strong>{valueOrDash(metrics.pwm_left_percent, 0)} / {valueOrDash(metrics.pwm_right_percent, 0)}%</strong></span>
                    </> : <>
                      <span><small>Công suất</small><strong>{valueOrDash(metrics.power_mw, 1)} mW</strong></span>
                      <span><small>Motor</small><strong>{metrics.driver_enabled ? `Bật · ${metrics.pwm_percent ?? 0}%` : "Tắt"}</strong></span>
                    </>}
                  </div>
                ) : (
                  <p>{presentation.summary}</p>
                )}
                <details className="terminal-raw">
                  <summary><ChevronDown size={14} /> Xem dữ liệu gốc</summary>
                  <pre>{presentation.raw}</pre>
                </details>
              </div>
            </article>
          );
        })}
        {!followLatest && visibleLogs.length > 0 && !pausedLogs && (
          <button className="terminal-jump" type="button" onClick={jumpToLatest}>
            <ChevronsDown size={16} />Về log mới nhất
          </button>
        )}
      </div>
    </article>
  );
}
