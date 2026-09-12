"""Run the N06 closed-loop Auto Heal acceptance on the physical NeXus rig."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import serial
from nexus_device_command import (
    DeviceCommandError,
    build_request,
    detect_port,
    exchange,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "artifacts" / "N06"
MIN_BUS_VOLTAGE_V = 9.5
MAX_BUS_VOLTAGE_V = 13.0
MAX_CURRENT_MA = 1500.0
MAX_ACCEPTANCE_PWM = 30
MAX_TEST_DURATION_MS = 1000


class AutoHealAcceptanceError(RuntimeError):
    """Raised when the physical Auto Heal loop cannot establish safe evidence."""


def finite_number(value: object) -> float | None:
    if type(value) not in {int, float}:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def safety_decision(snapshot: dict[str, object], *, pwm_percent: int,
                    duration_ms: int) -> tuple[bool, str]:
    """Default-deny gate used immediately before a physical recovery action."""
    bus = finite_number(snapshot.get("bus_voltage_v"))
    current = finite_number(snapshot.get("current_ma"))
    if bus is None or current is None:
        return False, "INA226 voltage/current evidence is missing or non-finite"
    if not MIN_BUS_VOLTAGE_V <= bus <= MAX_BUS_VOLTAGE_V:
        return False, f"Bus voltage {bus:.3f} V is outside {MIN_BUS_VOLTAGE_V}..{MAX_BUS_VOLTAGE_V} V"
    if abs(current) > MAX_CURRENT_MA:
        return False, f"Current {current:.1f} mA exceeds the {MAX_CURRENT_MA:.0f} mA limit"
    if snapshot.get("driver_enabled") is not False or snapshot.get("pwm_percent") != 0:
        return False, "Recovery must start from PWM 0 with the driver disabled"
    if type(pwm_percent) is not int or not 1 <= pwm_percent <= MAX_ACCEPTANCE_PWM:
        return False, f"Acceptance PWM must be 1..{MAX_ACCEPTANCE_PWM}%"
    if type(duration_ms) is not int or not 100 <= duration_ms <= MAX_TEST_DURATION_MS:
        return False, f"Motor test must be 100..{MAX_TEST_DURATION_MS} ms"
    return True, "Fresh physical measurements and all conservative action limits passed"


def fault_state_passed(after: dict[str, object], *, idle_current_ma: float) -> bool:
    current = finite_number(after.get("current_ma"))
    return (
        current is not None
        and after.get("pwm_percent") == 0
        and after.get("driver_enabled") is False
        and current <= idle_current_ma + 5.0
    )


def healed_state_passed(after: dict[str, object], *, pwm_percent: int,
                        idle_current_ma: float) -> bool:
    current = finite_number(after.get("current_ma"))
    return (
        current is not None
        and after.get("pwm_percent") == pwm_percent
        and after.get("driver_enabled") is True
        and current > idle_current_ma + 5.0
    )


def motor_test_passed(terminal: dict[str, object], *, pwm_percent: int,
                      duration_ms: int) -> bool:
    result = terminal.get("result")
    after = terminal.get("after")
    elapsed = terminal.get("elapsed_ms")
    return (
        terminal.get("response_type") == "result"
        and terminal.get("hardware_effect") is True
        and isinstance(result, dict)
        and result.get("duration_ms") == duration_ms
        and result.get("test_pwm_percent") == pwm_percent
        and result.get("stopped_after_test") is True
        and isinstance(after, dict)
        and after.get("pwm_percent") == 0
        and after.get("driver_enabled") is False
        and type(elapsed) is int
        and duration_ms <= elapsed < duration_ms + 1000
    )


def send_fault_command(device: serial.Serial, command: str) -> dict[str, str]:
    device.write((command + "\n").encode("ascii"))
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        line = device.readline().decode("utf-8", errors="replace").strip()
        if "[NEXUS][ERROR][FAULT_" in line:
            raise AutoHealAcceptanceError(line)
        marker = "[NEXUS][INFO][FAULT_PROFILE] "
        if marker not in line:
            continue
        fields: dict[str, str] = {}
        for item in line.split(marker, 1)[1].split():
            key, separator, value = item.partition("=")
            if separator:
                fields[key] = value
        return fields
    raise AutoHealAcceptanceError(f"No fault status returned for {command}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    parser.add_argument("--confirm-hardware", action="store_true")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--pwm-percent", type=int, default=30)
    parser.add_argument("--duration-ms", type=int, default=500)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if not args.confirm_hardware:
        raise AutoHealAcceptanceError("Pass --confirm-hardware after securing the motor and emergency stop")
    if not 1 <= args.cycles <= 10:
        raise AutoHealAcceptanceError("Use 1..10 bounded recovery cycles")
    # Reject bad action values before opening the COM port.
    if not 1 <= args.pwm_percent <= MAX_ACCEPTANCE_PWM:
        raise AutoHealAcceptanceError(f"Use a conservative PWM between 1 and {MAX_ACCEPTANCE_PWM}%")
    if not 100 <= args.duration_ms <= MAX_TEST_DURATION_MS:
        raise AutoHealAcceptanceError(f"Use a motor-test duration of 100..{MAX_TEST_DURATION_MS} ms")
    port = args.port or detect_port()
    if not port:
        raise AutoHealAcceptanceError("No GOOUUU ESP32-S3 serial port was found")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    session_id = timestamp.rsplit("-", 1)[-1]
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    ndjson_path = EVIDENCE_ROOT / f"auto-heal-{timestamp}.ndjson"
    report_path = EVIDENCE_ROOT / f"auto-heal-{timestamp}.md"
    records: list[dict[str, Any]] = []
    cycle_rows: list[dict[str, object]] = []
    failures: list[str] = []
    request_counter = 0
    trace_id = f"n06-{timestamp}"

    def audit(event_type: str, summary: str, **payload: object) -> None:
        records.append({
            "schema_version": "1.0.0",
            "occurred_at": now_iso(),
            "trace_id": trace_id,
            "event_type": event_type,
            "summary": summary,
            "payload": payload,
        })

    device = serial.Serial(timeout=0.25, dsrdtr=False, rtscts=False)

    def run(command: str, **options: object):
        nonlocal request_counter
        request_counter += 1
        request = build_request(
            command,
            request_id=f"n06-{session_id}-{request_counter}",
            timeout_ms=4000,
            **options,
        )
        audit("tool.requested", f"Request {command}", request=request)
        try:
            completed = exchange(device, request)
        except DeviceCommandError as exc:
            if "Timed out" not in str(exc):
                raise
            audit("transport.retry", "Retry the same idempotent request", request_id=request["request_id"])
            completed = exchange(device, request)
        audit("tool.completed", f"Device completed {command}", ack=completed.ack,
              terminal=completed.terminal)
        time.sleep(0.05)
        return completed.terminal

    try:
        device.dtr = False
        device.rts = False
        device.port = port
        device.baudrate = 115_200
        device.open()
        time.sleep(2.0)
        device.reset_input_buffer()
        audit("acceptance.started", "Start supervised physical Auto Heal acceptance",
              port=port, cycles=args.cycles, pwm_percent=args.pwm_percent,
              duration_ms=args.duration_ms)

        for cycle in range(1, args.cycles + 1):
            run("reset_driver")
            reset_status = send_fault_command(device, "NEXUS FAULT RESET")
            audit("fault.reset", "Restore nominal PWM behavior before the cycle", cycle=cycle,
                  status=reset_status)
            idle_terminal = run("read_current")
            idle = finite_number(idle_terminal["result"].get("current_ma"))
            if idle is None:
                raise AutoHealAcceptanceError("INA226 idle current is unavailable")

            fault_status = send_fault_command(device, "NEXUS FAULT APPLY PWM_ZERO")
            audit("fault.injected", "Inject software-controllable PWM_ZERO fault", cycle=cycle,
                  status=fault_status)
            run("set_pwm", pwm_percent=args.pwm_percent)
            failed_terminal = run("enable_driver", enabled=True)
            failed_after = failed_terminal["after"]
            detected = fault_status.get("profile") == "pwm_zero" and fault_state_passed(
                failed_after, idle_current_ma=idle
            )
            audit("diagnosis.detected" if detected else "diagnosis.failed",
                  "PWM command produced no energized motor state", cycle=cycle,
                  before=failed_terminal["before"], after=failed_after,
                  idle_current_ma=idle)
            if not detected:
                raise AutoHealAcceptanceError(f"Cycle {cycle}: PWM_ZERO fault was not physically observed")

            voltage_terminal = run("read_voltage")
            policy_snapshot = dict(voltage_terminal["after"])
            policy_snapshot["current_ma"] = failed_after["current_ma"]
            allowed, reason = safety_decision(
                policy_snapshot,
                pwm_percent=args.pwm_percent,
                duration_ms=args.duration_ms,
            )
            audit("action.approved" if allowed else "action.rejected", reason, cycle=cycle,
                  requested_action={"fault_reset": True, "set_pwm": args.pwm_percent,
                                    "motor_test_ms": args.duration_ms},
                  before=policy_snapshot)
            if not allowed:
                raise AutoHealAcceptanceError(f"Cycle {cycle}: safety policy rejected recovery: {reason}")

            nominal_status = send_fault_command(device, "NEXUS FAULT RESET")
            audit("action.executed", "Remove PWM_ZERO and restore nominal PWM frequency", cycle=cycle,
                  status=nominal_status)
            run("set_pwm", pwm_percent=args.pwm_percent)
            active_terminal = run("enable_driver", enabled=True)
            active_after = active_terminal["after"]
            healed = healed_state_passed(
                active_after,
                pwm_percent=args.pwm_percent,
                idle_current_ma=idle,
            )
            audit("verification.measurement", "Measure current after the recovery command", cycle=cycle,
                  before=active_terminal["before"], after=active_after,
                  current_rise_ma=(finite_number(active_after.get("current_ma")) or 0) - idle)
            run("reset_driver")
            motor_terminal = run(
                "run_motor_test",
                duration_ms=args.duration_ms,
                pwm_percent=args.pwm_percent,
            )
            bounded = motor_test_passed(
                motor_terminal,
                pwm_percent=args.pwm_percent,
                duration_ms=args.duration_ms,
            )
            final_terminal = run("read_current")
            final_after = final_terminal["after"]
            safe_final = final_after["driver_enabled"] is False and final_after["pwm_percent"] == 0
            passed = healed and bounded and safe_final
            active_current = finite_number(active_after.get("current_ma"))
            detail = (
                f"idle {idle:.1f} mA -> active {active_current:.1f} mA; "
                f"{args.duration_ms} ms motor test; final PWM 0/OFF"
                if active_current is not None
                else "active current unavailable"
            )
            cycle_rows.append({"cycle": cycle, "passed": passed, "detail": detail})
            audit("verification.passed" if passed else "verification.failed",
                  "Motor fail-to-pass recovery verified" if passed else "Recovery evidence was incomplete",
                  cycle=cycle, healed_measurement=healed, bounded_motor_test=bounded,
                  final_safe_state=safe_final, after=final_after)
            if not passed:
                raise AutoHealAcceptanceError(f"Cycle {cycle}: {detail}")
    except (AutoHealAcceptanceError, DeviceCommandError, OSError, KeyError, TypeError, ValueError) as exc:
        failures.append(str(exc))
        audit("acceptance.failed", "N06 acceptance stopped safely", error_type=type(exc).__name__,
              error=str(exc))
    finally:
        if device.is_open:
            try:
                run("reset_driver")
                reset_status = send_fault_command(device, "NEXUS FAULT RESET")
                audit("safety.final_reset", "Force PWM 0/OFF and clear every fault profile",
                      status=reset_status)
            except (AutoHealAcceptanceError, DeviceCommandError, OSError) as exc:
                failures.append(f"Final safe reset not confirmed: {exc}")
            device.close()

    outcome = "PASS" if not failures and len(cycle_rows) == args.cycles else "FAIL"
    audit("acceptance.completed", f"N06 physical Auto Heal {outcome}", outcome=outcome,
          passed_cycles=sum(bool(item["passed"]) for item in cycle_rows),
          required_cycles=args.cycles, failures=failures)
    ndjson_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    rows = "\n".join(
        f"| {item['cycle']}/{args.cycles} | {'PASS' if item['passed'] else 'FAIL'} | {item['detail']} |"
        for item in cycle_rows
    ) or "| - | FAIL | Không có chu kỳ hoàn tất |"
    errors = "\n".join(f"- {item}" for item in failures) or "- Không có"
    report = f"""# N06 — Physical closed-loop Auto Heal acceptance

- Kết quả: **{outcome}**
- Thời gian UTC: `{now_iso()}`
- Hardware: GOOUUU ESP32-S3-N16R8 → INA226 R100 → L298N → JGB37-520 12 V
- Luồng: PWM_ZERO → đo → policy → reset fault → set PWM → đo dòng → motor test → verify → PWM 0/OFF
- Chu kỳ đạt: `{sum(bool(item['passed']) for item in cycle_rows)}/{args.cycles}`
- Evidence audit: `{ndjson_path}`

| Chu kỳ | Kết quả | Bằng chứng fail → pass |
| --- | --- | --- |
{rows}

## Lỗi

{errors}
"""
    report_path.write_text(report, encoding="utf-8")
    print(report)
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoHealAcceptanceError as exc:
        print(f"[NEXUS][ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
