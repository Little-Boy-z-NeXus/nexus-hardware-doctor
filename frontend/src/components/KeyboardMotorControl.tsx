import { AlertTriangle, Keyboard, ShieldCheck, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { env } from "../config/env";
import { useI18n } from "../i18n/I18nContext";

type DriveDirection = "forward" | "reverse";

interface KeyboardMotorControlProps {
  enabled: boolean;
  maxPwmPercent: number;
  defaultPwmPercent?: number;
  disabledReason?: string;
}

const HOLD_MS = 700;
const RENEW_MS = 300;

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function KeyboardMotorControl({
  enabled,
  maxPwmPercent,
  defaultPwmPercent = 50,
  disabledReason,
}: KeyboardMotorControlProps) {
  const { text } = useI18n();
  const localizedDisabledReason = disabledReason ?? text(
    "Waiting for hardware safety checks to pass.",
    "Đang chờ hardware vượt qua kiểm tra an toàn.",
  );
  const pwmPercent = Math.min(Math.max(defaultPwmPercent, 1), maxPwmPercent);
  const [direction, setDirection] = useState<DriveDirection | null>(null);
  const [message, setMessage] = useState(text("Hold W to move forward or S to reverse.", "Giữ W để tiến hoặc S để lùi."));
  const [hasError, setHasError] = useState(false);
  const heldDirection = useRef<DriveDirection | null>(null);
  const renewTimer = useRef<number | null>(null);
  const requestInFlight = useRef(false);
  const mounted = useRef(true);

  const clearRenewTimer = useCallback(() => {
    if (renewTimer.current !== null) {
      window.clearInterval(renewTimer.current);
      renewTimer.current = null;
    }
  }, []);

  const stopMotor = useCallback(async () => {
    clearRenewTimer();
    heldDirection.current = null;
    if (mounted.current) {
      setDirection(null);
      setMessage(text("Stopped · hold W or S to drive again.", "Đã dừng · giữ W hoặc S để chạy tiếp."));
    }
    try {
      await fetch(`${env.apiBaseUrl}/api/v1/motor/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop", pwm_percent: pwmPercent, hold_ms: HOLD_MS }),
        keepalive: true,
      });
    } catch {
      // The firmware lease is the final stop path if the browser/backend disappears.
    }
  }, [clearRenewTimer, pwmPercent, text]);

  const sendDrive = useCallback(async (nextDirection: DriveDirection) => {
    if (!enabled || heldDirection.current !== nextDirection || requestInFlight.current) return;
    requestInFlight.current = true;
    try {
      const response = await fetch(`${env.apiBaseUrl}/api/v1/motor/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: nextDirection,
          pwm_percent: pwmPercent,
          hold_ms: HOLD_MS,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail || `HTTP ${response.status}`);
      }
      if (mounted.current && heldDirection.current === nextDirection) {
        setHasError(false);
        setMessage(nextDirection === "forward"
          ? text("Moving forward · release W to stop", "Đang tiến · nhả W để dừng")
          : text("Reversing · release S to stop", "Đang lùi · nhả S để dừng"));
      } else if (heldDirection.current === null) {
        void stopMotor();
      }
    } catch (error) {
      clearRenewTimer();
      heldDirection.current = null;
      if (mounted.current) {
        setDirection(null);
        setHasError(true);
        setMessage(error instanceof Error ? error.message : text("Could not send the command to ESP32.", "Không thể gửi lệnh xuống ESP32."));
      }
      void stopMotor();
    } finally {
      requestInFlight.current = false;
    }
  }, [clearRenewTimer, enabled, pwmPercent, stopMotor, text]);

  useEffect(() => {
    mounted.current = true;
    const start = (nextDirection: DriveDirection) => {
      if (!enabled) {
        setHasError(true);
        setMessage(localizedDisabledReason);
        return;
      }
      if (heldDirection.current === nextDirection) return;
      clearRenewTimer();
      heldDirection.current = nextDirection;
      setDirection(nextDirection);
      setHasError(false);
      setMessage(text("Verifying safety conditions…", "Đang xác nhận điều kiện an toàn..."));
      void sendDrive(nextDirection);
      renewTimer.current = window.setInterval(() => void sendDrive(nextDirection), RENEW_MS);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat || isTypingTarget(event.target)) return;
      const key = event.key.toLowerCase();
      if (key === "w" || key === "s") {
        event.preventDefault();
        start(key === "w" ? "forward" : "reverse");
      } else if (key === "escape") {
        void stopMotor();
      }
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const released = key === "w" ? "forward" : key === "s" ? "reverse" : null;
      if (released && heldDirection.current === released) {
        event.preventDefault();
        void stopMotor();
      }
    };
    const stopForVisibility = () => {
      if (document.visibilityState !== "visible") void stopMotor();
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", stopMotor);
    document.addEventListener("visibilitychange", stopForVisibility);
    return () => {
      mounted.current = false;
      clearRenewTimer();
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", stopMotor);
      document.removeEventListener("visibilitychange", stopForVisibility);
      void fetch(`${env.apiBaseUrl}/api/v1/motor/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop", pwm_percent: pwmPercent, hold_ms: HOLD_MS }),
        keepalive: true,
      }).catch(() => undefined);
    };
  }, [clearRenewTimer, enabled, localizedDisabledReason, pwmPercent, sendDrive, stopMotor, text]);

  useEffect(() => {
    if (!enabled && heldDirection.current !== null) void stopMotor();
  }, [enabled, stopMotor]);

  return (
    <section className={`card keyboard-drive${hasError ? " keyboard-drive--error" : ""}`} aria-labelledby="keyboard-drive-title">
      <div className="keyboard-drive__intro">
        <span className="keyboard-drive__icon"><Keyboard size={22} aria-hidden="true" /></span>
        <div>
          <p className="eyebrow">{text("Direct control", "Điều khiển trực tiếp")} · PWM {pwmPercent}%</p>
          <h2 id="keyboard-drive-title">{text("Hold to drive, release to stop", "Giữ phím để chạy, nhả để dừng")}</h2>
          <p>{message}</p>
        </div>
      </div>
      <div className="keyboard-drive__keys" aria-label={text("Drive keys", "Các phím điều khiển")}>
        <span className={`keyboard-key${direction === "forward" ? " is-active" : ""}`}><kbd>W</kbd><small>{text("Forward", "Tiến")}</small></span>
        <span className={`keyboard-key${direction === "reverse" ? " is-active" : ""}`}><kbd>S</kbd><small>{text("Reverse", "Lùi")}</small></span>
        <button type="button" className="keyboard-stop" onClick={() => void stopMotor()}>
          <Square size={15} fill="currentColor" /> {text("Stop", "Dừng")}
        </button>
      </div>
      <div className={`keyboard-drive__guard${enabled ? " is-ready" : ""}`}>
        {enabled ? <ShieldCheck size={17} /> : <AlertTriangle size={17} />}
        <span>{enabled ? text("Backend, firmware, INA226, and motor power are verified.", "Đã xác minh backend, firmware, INA226 và nguồn motor.") : localizedDisabledReason}</span>
      </div>
    </section>
  );
}
