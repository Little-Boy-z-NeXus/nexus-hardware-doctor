"""Exercise repeatable N05 fault profiles on the real NeXus motor rig."""

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
EVIDENCE_ROOT = ROOT / "artifacts" / "N05"
OPEN_OUTPUT_MAX_DELTA_MA = 10.0


class FaultAcceptanceError(RuntimeError):
    """Raised when an N05 fault does not reproduce or reset safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    parser.add_argument("--confirm-hardware", action="store_true")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--software-only", action="store_true")
    modes.add_argument("--manual-out2-confirmed", action="store_true")
    modes.add_argument("--verify-restored", action="store_true")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--pwm-percent", type=int, default=30)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def send_fault_command(device: serial.Serial, command: str) -> dict[str, str]:
    for _attempt in range(2):
        device.write((command + "\n").encode("ascii"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            line = device.readline().decode("utf-8", errors="replace").strip()
            if "[NEXUS][ERROR][FAULT_" in line:
                raise FaultAcceptanceError(line)
            marker = "[NEXUS][INFO][FAULT_PROFILE] "
            if marker not in line:
                continue
            fields: dict[str, str] = {}
            for item in line.split(marker, 1)[1].split():
                key, separator, value = item.partition("=")
                if separator:
                    fields[key] = value
            return fields
    raise FaultAcceptanceError(f"No fault status returned for {command}")


def number(value: object, label: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise FaultAcceptanceError(f"{label} is not finite: {value!r}")
    return float(value)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if not args.confirm_hardware:
        raise FaultAcceptanceError("Pass --confirm-hardware after securing the motor")
    if not 1 <= args.cycles <= 10 or not 1 <= args.pwm_percent <= 30:
        raise FaultAcceptanceError("Use 1..10 cycles and conservative PWM 1..30%")
    port = args.port or detect_port()
    if not port:
        raise FaultAcceptanceError("No GOOUUU ESP32-S3 serial port was found")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    session_id = timestamp.rsplit("-", 1)[-1]
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    mode = (
        "software"
        if args.software_only
        else "out2-manual"
        if args.manual_out2_confirmed
        else "restored"
    )
    ndjson_path = EVIDENCE_ROOT / f"{mode}-{timestamp}.ndjson"
    report_path = EVIDENCE_ROOT / f"{mode}-{timestamp}.md"
    records: list[dict[str, Any]] = []
    checks: list[tuple[str, bool, str]] = []
    failures: list[str] = []
    request_counter = 0

    def record(kind: str, value: object) -> None:
        records.append({"occurred_at": now_iso(), "kind": kind, "value": value})

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append((name, passed, detail))
        if not passed:
            failures.append(f"{name}: {detail}")

    device = serial.Serial(timeout=0.25, dsrdtr=False, rtscts=False)

    def run(command: str, **options: object):
        nonlocal request_counter
        request_counter += 1
        request = build_request(
            command,
            request_id=f"n05-{session_id}-{mode}-{request_counter}",
            timeout_ms=4000,
            **options,
        )
        record("request", request)
        try:
            result = exchange(device, request)
        except DeviceCommandError as exc:
            if "Timed out" not in str(exc):
                raise
            record("transport_retry", {"request_id": request["request_id"], "reason": str(exc)})
            result = exchange(device, request)
        record("ack", result.ack)
        record("terminal", result.terminal)
        if result.terminal.get("response_type") != "result":
            error = result.terminal.get("error", {})
            code = error.get("code", "DEVICE_COMMAND_FAILED")
            message = error.get("message", "Device returned a non-result response")
            raise FaultAcceptanceError(f"{command} failed: {code}: {message}")
        time.sleep(0.03)
        return result

    try:
        device.dtr = False
        device.rts = False
        device.port = port
        device.baudrate = 115_200
        device.open()
        time.sleep(2.0)
        device.reset_input_buffer()
        record("test_config", {"port": port, "mode": mode, "cycles": args.cycles})
        record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))
        run("reset_driver")
        idle = number(run("read_current").terminal["result"].get("current_ma"), "idle current")

        if args.software_only:
            for cycle in range(1, args.cycles + 1):
                status = send_fault_command(device, "NEXUS FAULT APPLY PWM_ZERO")
                record("fault_apply", status)
                run("set_pwm", pwm_percent=args.pwm_percent)
                result = run("enable_driver", enabled=True).terminal
                passed = (
                    status.get("profile") == "pwm_zero"
                    and result["after"]["pwm_percent"] == 0
                    and result["after"]["driver_enabled"] is False
                )
                check(f"PWM_ZERO {cycle}/{args.cycles}", passed, "motion suppressed at PWM 0")
                run("reset_driver")
                record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))

            for cycle in range(1, args.cycles + 1):
                status = send_fault_command(device, "NEXUS FAULT APPLY PWM_FREQUENCY_LOW")
                record("fault_apply", status)
                run("set_pwm", pwm_percent=args.pwm_percent)
                result = run("enable_driver", enabled=True).terminal
                active_current = number(result["after"].get("current_ma"), "active current")
                passed = (
                    status.get("profile") == "pwm_frequency_low"
                    and status.get("pwm_frequency_hz") == "100"
                    and result["after"]["driver_enabled"] is True
                    and active_current > idle + 5
                )
                check(
                    f"PWM_FREQUENCY_LOW {cycle}/{args.cycles}",
                    passed,
                    f"100 Hz profile; load current {active_current:.1f} mA",
                )
                run("reset_driver")
                record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))

            for cycle in range(1, args.cycles + 1):
                time.sleep(0.4)
                cycle_idle = number(
                    run("read_current").terminal["result"].get("current_ma"),
                    "cycle idle current",
                )
                status = send_fault_command(device, "NEXUS FAULT APPLY CURRENT_OFFSET")
                record("fault_apply", status)
                time.sleep(0.2)
                shifted = number(
                    run("read_current").terminal["result"].get("current_ma"),
                    "offset current",
                )
                record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))
                time.sleep(0.4)
                restored = number(
                    run("read_current").terminal["result"].get("current_ma"),
                    "restored current",
                )
                passed = (
                    status.get("profile") == "current_offset"
                    and abs((shifted - cycle_idle) - 200.0) <= 5.0
                    and abs(restored - cycle_idle) <= 10.0
                )
                check(
                    f"CURRENT_OFFSET {cycle}/{args.cycles}",
                    passed,
                    f"idle {cycle_idle:.1f}, shifted {shifted:.1f}, restored {restored:.1f} mA",
                )

        elif args.manual_out2_confirmed:
            bus = number(
                run("read_voltage").terminal["result"].get("bus_voltage_v"),
                "OUT2-open bus voltage",
            )
            if not 9.5 <= bus <= 13.0:
                raise FaultAcceptanceError(
                    "OUT2-open preflight failed: INA226 bus voltage "
                    f"is {bus:.3f} V; expected 9.5..13.0 V. Check the 12 V "
                    "adapter, common GND, VIN+ and VIN-/VBS before retrying."
                )
            record("manual_out2_preflight", {"bus_voltage_v": bus, "safe": True})
            for cycle in range(1, args.cycles + 1):
                status = send_fault_command(device, "NEXUS FAULT APPLY OUT2_OPEN_MANUAL")
                record("fault_apply", status)
                run("set_pwm", pwm_percent=args.pwm_percent)
                result = run("enable_driver", enabled=True).terminal
                active_current = number(result["after"].get("current_ma"), "OUT2-open current")
                current_delta = active_current - idle
                passed = (
                    status.get("manual_action_required") == "true"
                    and result["after"]["driver_enabled"] is True
                    and current_delta <= OPEN_OUTPUT_MAX_DELTA_MA
                )
                check(
                    f"OUT2_OPEN_MANUAL {cycle}/{args.cycles}",
                    passed,
                    "driver commanded on; current "
                    f"{active_current:.1f} mA (idle delta {current_delta:+.1f} mA, "
                    f"limit +{OPEN_OUTPUT_MAX_DELTA_MA:.1f} mA)",
                )
                run("reset_driver")
            record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))

        else:
            bus = number(run("read_voltage").terminal["result"].get("bus_voltage_v"), "bus")
            motor = run(
                "run_motor_test",
                duration_ms=500,
                pwm_percent=args.pwm_percent,
            ).terminal
            check(
                "Restored baseline",
                9.5 <= bus <= 13.0
                and motor["response_type"] == "result"
                and motor["after"]["driver_enabled"] is False
                and motor["after"]["pwm_percent"] == 0,
                f"bus {bus:.3f} V; bounded motor test returned to safe state",
            )
    except (
        DeviceCommandError,
        FaultAcceptanceError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        failures.append(str(exc))
        record("exception", {"type": type(exc).__name__, "message": str(exc)})
    finally:
        if device.is_open:
            try:
                run("reset_driver")
                record("fault_reset", send_fault_command(device, "NEXUS FAULT RESET"))
            except (DeviceCommandError, FaultAcceptanceError, OSError) as exc:
                failures.append(f"Final safe reset not confirmed: {exc}")
            device.close()

    outcome = "PASS" if not failures else "FAIL"
    record("result", {"outcome": outcome, "checks": len(checks), "failures": failures})
    ndjson_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    rows = "\n".join(
        f"| {name} | {'PASS' if passed else 'FAIL'} | {detail} |"
        for name, passed, detail in checks
    )
    errors = "\n".join(f"- {item}" for item in failures) or "- Không có"
    report = f"""# N05 — Fault profile acceptance ({mode})

- Kết quả: **{outcome}**
- Thời gian UTC: `{now_iso()}`
- Hardware: GOOUUU ESP32-S3-N16R8 → INA226 R100 → L298N → JGB37-520 12 V
- Chu kỳ: `{args.cycles}`
- PWM giới hạn: `{args.pwm_percent}%`
- Evidence: `{ndjson_path}`

| Kiểm tra | Kết quả | Chi tiết |
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
    except FaultAcceptanceError as exc:
        print(f"[NEXUS][ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
