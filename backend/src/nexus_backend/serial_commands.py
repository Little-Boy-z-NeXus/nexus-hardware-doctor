"""Safe motor commands multiplexed through the bridge's single serial owner."""

from __future__ import annotations

import asyncio
import json
import math
import threading
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4


class SerialCommandError(RuntimeError):
    """Stable public error codes; firmware-provided messages never cross the API."""


@dataclass
class PendingCommand:
    request: dict
    deadline: float
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future
    sent: bool = False
    acknowledged: bool = False


class SerialCommandChannel:
    """One in-flight allowlisted command with no reconnect replay."""

    def __init__(self, *, max_pwm_percent: int) -> None:
        self.max_pwm_percent = max_pwm_percent
        self._lock = threading.RLock()
        self._connected = False
        self._pending: PendingCommand | None = None

    def connect(self) -> None:
        with self._lock:
            self.disconnect()
            self._connected = True

    def disconnect(self) -> None:
        with self._lock:
            self._fail("serial_disconnected")
            self._connected = False

    async def execute(
        self, command: str, arguments: dict, *, timeout_seconds: float = 2.0
    ) -> dict:
        if command not in {"drive_motor", "reset_driver"}:
            raise SerialCommandError("serial_command_not_allowed")
        if command == "reset_driver":
            if arguments != {}:
                raise SerialCommandError("serial_command_invalid")
        else:
            if set(arguments) != {"direction", "pwm_percent", "hold_ms"}:
                raise SerialCommandError("serial_command_invalid")
            if arguments["direction"] not in {"forward", "reverse"}:
                raise SerialCommandError("serial_command_invalid")
            if (type(arguments["pwm_percent"]) is not int
                    or not 1 <= arguments["pwm_percent"] <= self.max_pwm_percent):
                raise SerialCommandError("serial_command_invalid")
            if (type(arguments["hold_ms"]) is not int
                    or not 200 <= arguments["hold_ms"] <= 1000):
                raise SerialCommandError("serial_command_invalid")
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 5):
            raise SerialCommandError("serial_timeout_invalid")

        loop = asyncio.get_running_loop()
        request_id = f"ui-{uuid4().hex}"
        request = {
            "protocol_version": "1.0.0",
            "request_id": request_id,
            "command": command,
            "arguments": arguments,
            "timeout_ms": min(1500, int(timeout_seconds * 1000)),
        }
        with self._lock:
            if not self._connected:
                raise SerialCommandError("serial_device_unavailable")
            if self._pending is not None:
                raise SerialCommandError("serial_busy")
            pending = PendingCommand(
                request=request, deadline=monotonic() + timeout_seconds,
                loop=loop, future=loop.create_future(),
            )
            self._pending = pending
        try:
            return await asyncio.wait_for(pending.future, timeout_seconds)
        except TimeoutError:
            raise SerialCommandError("serial_command_timeout") from None
        finally:
            with self._lock:
                if self._pending is pending:
                    self._pending = None

    def flush(self, device) -> None:
        """Write only from the worker that owns the serial port."""
        with self._lock:
            pending = self._pending
            if pending is None or pending.sent:
                return
            if pending.future.done() or monotonic() >= pending.deadline:
                self._fail("serial_command_timeout")
                return
            wire = json.dumps(pending.request, separators=(",", ":")).encode() + b"\n"
            try:
                if device.write(wire) != len(wire):
                    raise OSError("partial write")
            except (OSError, RuntimeError):
                self._fail("serial_write_failed")
                return
            pending.sent = True

    def receive(self, payload: object) -> None:
        with self._lock:
            pending = self._pending
            if (pending is None or not pending.sent or not isinstance(payload, dict)
                    or payload.get("request_id") != pending.request["request_id"]):
                return
            if (payload.get("protocol_version") != "1.0.0"
                    or payload.get("command") != pending.request["command"]):
                self._fail("serial_response_invalid")
                return
            response_type = payload.get("response_type")
            if response_type == "ack":
                if (pending.acknowledged or payload.get("accepted") is not True
                        or payload.get("duplicate") is not False):
                    self._fail("serial_response_invalid")
                else:
                    pending.acknowledged = True
                return
            if response_type == "error":
                self._fail("serial_device_error")
                return
            if response_type != "result" or not pending.acknowledged:
                self._fail("serial_response_invalid")
                return
            result = payload.get("result")
            if not isinstance(result, dict):
                self._fail("serial_response_invalid")
                return
            command = pending.request["command"]
            if command == "reset_driver":
                if result.get("reset") is not True:
                    self._fail("serial_response_invalid")
                    return
                sanitized = {"command": command, "stopped": True}
            else:
                args = pending.request["arguments"]
                if (result.get("direction") != args["direction"]
                        or result.get("pwm_percent") != args["pwm_percent"]
                        or result.get("hold_ms") != args["hold_ms"]
                        or result.get("driver_enabled") is not True):
                    self._fail("serial_response_invalid")
                    return
                sanitized = {
                    "command": command,
                    "direction": args["direction"],
                    "pwm_percent": args["pwm_percent"],
                    "hold_ms": args["hold_ms"],
                }
            self._complete(result=sanitized)

    def _fail(self, code: str) -> None:
        self._complete(error=SerialCommandError(code))

    def _complete(self, *, result: dict | None = None, error: Exception | None = None) -> None:
        pending = self._pending
        if pending is None:
            return
        self._pending = None

        def deliver() -> None:
            if not pending.future.done():
                if error is not None:
                    pending.future.set_exception(error)
                else:
                    pending.future.set_result(result)

        if not pending.loop.is_closed():
            pending.loop.call_soon_threadsafe(deliver)
