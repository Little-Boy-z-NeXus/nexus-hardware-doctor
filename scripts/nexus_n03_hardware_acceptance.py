"""Run the supervised N03 command-adapter acceptance matrix on the real rig."""

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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPOSITORY_ROOT / "artifacts" / "N03"


class AcceptanceFailure(RuntimeError):
    """The physical N03 acceptance matrix did not meet its pass conditions."""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def snapshot_number(snapshot: object, key: str) -> float:
    if not isinstance(snapshot, dict):
        raise AcceptanceFailure(f"Missing measurement snapshot for {key}")
    value = snapshot.get(key)
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise AcceptanceFailure(f"Non-finite {key}: {value!r}")
    return float(value)


def raw_exchange(
    device: serial.Serial,
    request: dict[str, object],
    *,
    deadline_seconds: float = 3.0,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    wire = json.dumps(request, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
    device.write(wire)
    deadline = time.monotonic() + deadline_seconds
    ack: dict[str, object] | None = None
    while time.monotonic() < deadline:
        line = device.readline()
        try:
            payload = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("request_id") != request["request_id"]:
            continue
        if payload.get("response_type") == "ack":
            ack = payload
            continue
        if payload.get("response_type") in {"result", "error"}:
            return ack, payload
    raise AcceptanceFailure(f"Timed out waiting for {request['request_id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port; auto-detected when omitted")
    parser.add_argument("--confirm-hardware", action="store_true")
    parser.add_argument("--pwm-percent", type=int, default=30)
    parser.add_argument("--motor-test-ms", type=int, default=500)
    parser.add_argument("--min-current-rise-ma", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if not args.confirm_hardware:
        raise AcceptanceFailure(
            "Pass --confirm-hardware only after securing the motor and placing the 12 V "
            "quick disconnect within reach"
        )
    if not 1 <= args.pwm_percent <= 30:
        raise AcceptanceFailure("Acceptance PWM must stay within the conservative 1..30% range")
    if not 100 <= args.motor_test_ms <= 1000:
        raise AcceptanceFailure("Acceptance motor test must stay within 100..1000 ms")

    port = args.port or detect_port()
    if not port:
        raise AcceptanceFailure("No GOOUUU ESP32-S3 serial port was found")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    ndjson_path = EVIDENCE_ROOT / f"acceptance-{timestamp}.ndjson"
    report_path = EVIDENCE_ROOT / f"acceptance-{timestamp}.md"
    records: list[dict[str, Any]] = []
    checks: list[tuple[str, str]] = []
    failures: list[str] = []
    bus_voltage = float("nan")
    idle_current = float("nan")

    def record(kind: str, value: object) -> None:
        records.append({"occurred_at": now_iso(), "kind": kind, "value": value})

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append((name, f"{'PASS' if condition else 'FAIL'} — {detail}"))
        if not condition:
            failures.append(f"{name}: {detail}")

    device: serial.Serial | None = None

    def run(command: str, request_id: str, **options: object):
        if device is None:
            raise AcceptanceFailure("Serial device is not open")
        request = build_request(command, request_id=request_id, timeout_ms=4000, **options)
        record("request", request)
        result = exchange(device, request)
        record("ack", result.ack)
        record("terminal", result.terminal)
        return result

    try:
        device = serial.Serial(timeout=0.25, dsrdtr=False, rtscts=False)
        device.dtr = False
        device.rts = False
        device.port = port
        device.baudrate = 115_200
        device.open()
        time.sleep(2.0)
        device.reset_input_buffer()
        record(
            "test_config",
            {
                "port": port,
                "pwm_percent": args.pwm_percent,
                "motor_test_ms": args.motor_test_ms,
            },
        )

        emergency = run("reset_driver", "n03-reset-start")
        check(
            "Safe start",
            emergency.terminal["response_type"] == "result"
            and emergency.terminal["after"]["pwm_percent"] == 0
            and emergency.terminal["after"]["driver_enabled"] is False,
            "driver is stopped before testing",
        )

        voltage = run("read_voltage", "n03-voltage")
        bus_voltage = snapshot_number(voltage.terminal.get("after"), "bus_voltage_v")
        check(
            "INA226 bus voltage",
            voltage.terminal["response_type"] == "result" and 9.5 <= bus_voltage <= 13.0,
            f"{bus_voltage:.3f} V within 9.5..13.0 V",
        )

        current = run("read_current", "n03-current")
        idle_current = snapshot_number(current.terminal.get("after"), "current_ma")
        check(
            "INA226 current",
            current.terminal["response_type"] == "result" and abs(idle_current) <= 1500,
            f"finite idle current {idle_current:.2f} mA",
        )

        for pin_id in ("gpio_12", "gpio_13", "gpio_14", "gpio_16", "gpio_17"):
            gpio = run("read_gpio", f"n03-{pin_id}", pin_id=pin_id)
            level = gpio.terminal.get("result", {}).get("level")
            check(f"Read {pin_id}", level in {0, 1}, f"digital level={level}")

        invalid_request = {
            "protocol_version": "1.0.0",
            "request_id": "n03-invalid-command",
            "command": "write_gpio",
            "arguments": {"pin_id": "gpio_12", "level": 1},
            "timeout_ms": 1000,
        }
        record("request", invalid_request)
        invalid_ack, invalid_terminal = raw_exchange(device, invalid_request)
        record("ack", invalid_ack)
        record("terminal", invalid_terminal)
        invalid_error = invalid_terminal.get("error", {})
        check(
            "Unknown command default-deny",
            invalid_terminal.get("response_type") == "error"
            and isinstance(invalid_error, dict)
            and invalid_error.get("code") == "UNKNOWN_COMMAND"
            and invalid_error.get("hardware_effect") is False,
            "write_gpio rejected with no hardware effect",
        )

        timeout_request = {
            "protocol_version": "1.0.0",
            "request_id": "n03-timeout-invalid",
            "command": "run_motor_test",
            "arguments": {"duration_ms": 500, "pwm_percent": args.pwm_percent},
            "timeout_ms": 200,
        }
        record("request", timeout_request)
        timeout_ack, timeout_terminal = raw_exchange(device, timeout_request)
        record("ack", timeout_ack)
        record("terminal", timeout_terminal)
        timeout_error = timeout_terminal.get("error", {})
        check(
            "Unsafe timeout default-deny",
            timeout_terminal.get("response_type") == "error"
            and isinstance(timeout_error, dict)
            and timeout_error.get("code") == "TIMEOUT_TOO_SHORT"
            and timeout_error.get("hardware_effect") is False,
            "too-short timeout rejected before motor motion",
        )

        pwm_request = build_request(
            "set_pwm",
            request_id="n03-pwm-idempotent",
            timeout_ms=1000,
            pwm_percent=args.pwm_percent,
        )
        record("request", pwm_request)
        first_pwm = exchange(device, pwm_request)
        record("ack", first_pwm.ack)
        record("terminal", first_pwm.terminal)
        repeated_pwm = exchange(device, pwm_request)
        record("duplicate_ack", repeated_pwm.ack)
        record("duplicate_terminal", repeated_pwm.terminal)
        check(
            "Duplicate command",
            repeated_pwm.ack.get("duplicate") is True
            and repeated_pwm.terminal == first_pwm.terminal,
            "cached terminal replayed; action not executed twice",
        )

        conflicting_pwm = dict(pwm_request)
        conflicting_pwm["arguments"] = {"pwm_percent": args.pwm_percent + 1}
        record("request", conflicting_pwm)
        conflict_ack, conflict_terminal = raw_exchange(device, conflicting_pwm)
        record("ack", conflict_ack)
        record("terminal", conflict_terminal)
        conflict_error = conflict_terminal.get("error", {})
        check(
            "Request ID conflict",
            conflict_terminal.get("response_type") == "error"
            and isinstance(conflict_error, dict)
            and conflict_error.get("code") == "REQUEST_ID_CONFLICT"
            and conflict_error.get("hardware_effect") is False,
            "same request_id with a different payload rejected",
        )

        enabled = run("enable_driver", "n03-enable", enabled=True)
        running_current = snapshot_number(enabled.terminal.get("after"), "current_ma")
        stopped = run("reset_driver", "n03-reset-after-enable")
        check(
            "Enable then reset",
            enabled.terminal["response_type"] == "result"
            and enabled.terminal["after"]["driver_enabled"] is True
            and enabled.terminal["after"]["pwm_percent"] == args.pwm_percent
            and stopped.terminal["after"]["driver_enabled"] is False
            and stopped.terminal["after"]["pwm_percent"] == 0,
            f"motor current {running_current:.2f} mA; final state PWM 0/off",
        )
        check(
            "Physical load response",
            running_current - idle_current >= args.min_current_rise_ma,
            f"current rise {running_current - idle_current:.2f} mA",
        )

        motor_test = run(
            "run_motor_test",
            "n03-bounded-motor-test",
            duration_ms=args.motor_test_ms,
            pwm_percent=args.pwm_percent,
        )
        check(
            "Bounded motor test",
            motor_test.terminal["response_type"] == "result"
            and motor_test.terminal["result"].get("stopped_after_test") is True
            and motor_test.terminal["after"]["pwm_percent"] == 0
            and motor_test.terminal["after"]["driver_enabled"] is False,
            f"ran {args.motor_test_ms} ms and returned to PWM 0/off",
        )

        calibration = run("recalibrate_sensor", "n03-recalibrate")
        check(
            "Stopped-state recalibration",
            calibration.terminal["response_type"] == "result"
            and calibration.terminal["result"].get("calibrated") is True
            and calibration.terminal["result"].get("shunt_ohms") == 0.1,
            "INA226 R100 calibration reapplied while stopped",
        )
    except (AcceptanceFailure, DeviceCommandError, OSError, ValueError, KeyError, TypeError) as exc:
        failures.append(str(exc))
        record("exception", {"type": type(exc).__name__, "message": str(exc)})
    finally:
        if device is not None and device.is_open:
            try:
                reset_request = build_request(
                    "reset_driver",
                    request_id=f"n03-final-stop-{timestamp}",
                    timeout_ms=1000,
                )
                reset_result = exchange(device, reset_request)
                record("final_stop", reset_result.terminal)
            except (
                AcceptanceFailure,
                DeviceCommandError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
            ) as exc:
                failures.append(f"Final emergency stop could not be confirmed: {exc}")
            device.close()

    outcome = "PASS" if not failures else "FAIL"
    record("result", {"outcome": outcome, "checks": len(checks), "failures": failures})
    ndjson_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    table = "\n".join(f"| {name} | {detail} |" for name, detail in checks)
    failure_lines = "\n".join(f"- {item}" for item in failures) or "- Không có"
    report_path.write_text(
        f"""# N03 — Physical command-adapter acceptance

- Kết quả: **{outcome}**
- Thời gian UTC: `{now_iso()}`
- Cổng: `{port}`
- Hardware: GOOUUU ESP32-S3-N16R8 → INA226 R100 → L298N → JGB37-520 12 V
- Test PWM: `{args.pwm_percent}%`
- Bus voltage: `{bus_voltage:.3f} V`
- Idle current: `{idle_current:.2f} mA`
- Evidence NDJSON: `{ndjson_path}`

| Kiểm tra | Kết quả |
| --- | --- |
{table}

## Lỗi

{failure_lines}

The runner always requests a final `reset_driver`; passing evidence ends at PWM 0/driver off.
""",
        encoding="utf-8",
    )
    print(report_path.read_text(encoding="utf-8"))
    print(f"Evidence: {ndjson_path}")
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AcceptanceFailure as exc:
        print(f"[NEXUS][ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
