"""Send one correlated NeXus device command over USB serial."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import serial
from serial.tools import list_ports

PROTOCOL_VERSION = "1.0.0"
REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
COMMANDS = {
    "read_voltage",
    "read_current",
    "read_gpio",
    "enable_driver",
    "set_pwm",
    "run_motor_test",
    "reset_driver",
    "recalibrate_sensor",
}
WRITE_COMMANDS = {"enable_driver", "set_pwm", "run_motor_test"}
GPIO_ALLOWLIST = {"gpio_12", "gpio_13", "gpio_14", "gpio_16", "gpio_17"}


class SerialLike(Protocol):
    def write(self, data: bytes) -> int: ...

    def readline(self) -> bytes: ...


class DeviceCommandError(RuntimeError):
    """The device protocol rejected, timed out, or returned an invalid response."""


@dataclass(frozen=True)
class CommandExchange:
    request: dict[str, object]
    ack: dict[str, object]
    terminal: dict[str, object]


def command_arguments(
    command: str,
    *,
    pwm_percent: int | None = None,
    duration_ms: int | None = None,
    pin_id: str | None = None,
    enabled: bool | None = None,
) -> dict[str, object]:
    if command not in COMMANDS:
        raise DeviceCommandError(f"Unknown command: {command}")
    if command == "read_gpio":
        if pin_id not in GPIO_ALLOWLIST:
            raise DeviceCommandError("read_gpio requires an allowlisted --pin-id")
        return {"pin_id": pin_id}
    if command == "enable_driver":
        if enabled is None:
            raise DeviceCommandError("enable_driver requires --enabled or --disabled")
        return {"enabled": enabled}
    if command == "set_pwm":
        if type(pwm_percent) is not int or not 0 <= pwm_percent <= 80:
            raise DeviceCommandError("set_pwm requires --pwm-percent between 0 and 80")
        return {"pwm_percent": pwm_percent}
    if command == "run_motor_test":
        if type(duration_ms) is not int or not 100 <= duration_ms <= 3000:
            raise DeviceCommandError("run_motor_test requires --duration-ms between 100 and 3000")
        arguments: dict[str, object] = {"duration_ms": duration_ms}
        if pwm_percent is not None:
            if type(pwm_percent) is not int or not 1 <= pwm_percent <= 80:
                raise DeviceCommandError("motor-test --pwm-percent must be between 1 and 80")
            arguments["pwm_percent"] = pwm_percent
        return arguments
    return {}


def build_request(
    command: str,
    *,
    request_id: str,
    timeout_ms: int,
    **argument_options: object,
) -> dict[str, object]:
    if not REQUEST_ID.fullmatch(request_id):
        raise DeviceCommandError("request_id must contain 1..64 safe ASCII characters")
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 5000:
        raise DeviceCommandError("timeout_ms must be between 100 and 5000")
    arguments = command_arguments(command, **argument_options)
    duration = arguments.get("duration_ms")
    if isinstance(duration, int) and timeout_ms < duration + 100:
        raise DeviceCommandError("timeout_ms must exceed duration_ms by at least 100")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "command": command,
        "arguments": arguments,
        "timeout_ms": timeout_ms,
    }


def _valid_snapshot(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "bus_voltage_v",
        "current_ma",
        "power_mw",
        "pwm_percent",
        "driver_enabled",
    }:
        return False
    nullable_numbers = (value["bus_voltage_v"], value["current_ma"], value["power_mw"])
    return (
        all(item is None or type(item) in {int, float} for item in nullable_numbers)
        and type(value["pwm_percent"]) is int
        and 0 <= value["pwm_percent"] <= 80
        and type(value["driver_enabled"]) is bool
    )


def _validate_response_shape(payload: dict[str, object]) -> None:
    response_type = payload["response_type"]
    common = {"protocol_version", "response_type", "request_id", "command"}
    if response_type == "ack":
        expected = common | {"accepted", "duplicate", "writes_enabled"}
        valid = set(payload) == expected and all(
            type(payload[field]) is bool
            for field in ("accepted", "duplicate", "writes_enabled")
        )
    elif response_type == "result":
        expected = common | {
            "completed_at_ms",
            "elapsed_ms",
            "hardware_effect",
            "result",
            "before",
            "after",
        }
        valid = (
            set(payload) == expected
            and type(payload["completed_at_ms"]) is int
            and type(payload["elapsed_ms"]) is int
            and type(payload["hardware_effect"]) is bool
            and isinstance(payload["result"], dict)
            and _valid_snapshot(payload["before"])
            and _valid_snapshot(payload["after"])
        )
    else:
        expected = common | {"completed_at_ms", "error"}
        error = payload.get("error")
        valid = (
            set(payload) == expected
            and type(payload["completed_at_ms"]) is int
            and isinstance(error, dict)
            and set(error) == {"code", "message", "hardware_effect"}
            and isinstance(error["code"], str)
            and bool(error["code"])
            and isinstance(error["message"], str)
            and bool(error["message"])
            and type(error["hardware_effect"]) is bool
        )
    if not valid:
        raise DeviceCommandError(f"Device returned an invalid {response_type} envelope")


def parse_response(
    line: bytes, *, request_id: str, command: str
) -> dict[str, object] | None:
    try:
        payload = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
        return None
    if payload.get("request_id") != request_id:
        return None
    if payload.get("response_type") not in {"ack", "result", "error"}:
        raise DeviceCommandError("Device returned an unknown response_type")
    if payload.get("command") != command:
        raise DeviceCommandError("Device response command does not match the request")
    _validate_response_shape(payload)
    return payload


def exchange(device: SerialLike, request: dict[str, object]) -> CommandExchange:
    wire = json.dumps(request, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
    device.write(wire)
    deadline = time.monotonic() + int(request["timeout_ms"]) / 1000 + 1
    ack: dict[str, object] | None = None
    terminal: dict[str, object] | None = None
    while time.monotonic() < deadline:
        payload = parse_response(
            device.readline(),
            request_id=str(request["request_id"]),
            command=str(request["command"]),
        )
        if payload is None:
            continue
        if payload["response_type"] == "ack":
            ack = payload
        else:
            terminal = payload
            break
    if ack is None:
        raise DeviceCommandError("Timed out waiting for correlated ACK")
    if terminal is None:
        raise DeviceCommandError("Timed out waiting for correlated result/error")
    return CommandExchange(request=request, ack=ack, terminal=terminal)


def detect_port() -> str | None:
    ports = list(list_ports.comports())
    for item in ports:
        if item.vid == 0x303A and item.pid == 0x1001:
            return item.device
    for item in ports:
        description = (item.description or "").lower()
        if "ch343" in description or "usb serial" in description:
            return item.device
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--port")
    parser.add_argument("--request-id", default=f"manual-{uuid4()}")
    parser.add_argument("--timeout-ms", type=int, default=4000)
    parser.add_argument("--pwm-percent", type=int)
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--pin-id")
    enabled = parser.add_mutually_exclusive_group()
    enabled.add_argument("--enabled", dest="enabled", action="store_true")
    enabled.add_argument("--disabled", dest="enabled", action="store_false")
    parser.set_defaults(enabled=None)
    parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="Required for enable_driver, set_pwm and run_motor_test.",
    )
    parser.add_argument(
        "--verify-duplicate",
        action="store_true",
        help="Resend the identical request and require duplicate:true plus the cached terminal response.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command in WRITE_COMMANDS and not args.confirm_write:
        raise DeviceCommandError("Physical writes require --confirm-write")
    request = build_request(
        args.command,
        request_id=args.request_id,
        timeout_ms=args.timeout_ms,
        pwm_percent=args.pwm_percent,
        duration_ms=args.duration_ms,
        pin_id=args.pin_id,
        enabled=args.enabled,
    )
    port = args.port or detect_port()
    if not port:
        raise DeviceCommandError("No GOOUUU ESP32-S3 serial port was found")

    with serial.Serial(port, 115_200, timeout=0.25) as device:
        time.sleep(0.5)
        first = exchange(device, request)
        print(json.dumps({"ack": first.ack, "terminal": first.terminal}, indent=2))
        if args.verify_duplicate:
            repeated = exchange(device, request)
            if repeated.ack.get("duplicate") is not True:
                raise DeviceCommandError("Repeated request was not marked duplicate")
            if repeated.terminal != first.terminal:
                raise DeviceCommandError("Repeated request did not return the cached terminal response")
            print("Idempotency check: PASS", file=sys.stderr)
    return 0 if first.terminal["response_type"] == "result" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeviceCommandError as exc:
        print(f"[NEXUS][ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
