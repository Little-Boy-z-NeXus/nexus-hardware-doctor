"""Bounded N03 reads multiplexed through the bridge's sole serial connection.

Only read_current is sent: N03 returns its measured current and full snapshots.
A successful tool read additionally requires the next canonical telemetry frame.
Command snapshots have no device identity, sequence or UTC time; they are never
promoted to fabricated telemetry. Device clocks and firmware sequence stay intact.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from nexus_backend.validation import validate_contract


class SerialReadError(RuntimeError):
    """Fixed public failure codes; never carries firmware text or raw responses."""


@dataclass
class PendingRead:
    request: dict
    device_id: str
    hardware_model_id: str
    connection_id: str
    deadline: float
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future
    sent: bool = False
    acknowledged: bool = False
    terminal: dict | None = None


def _snapshot_valid(value: object) -> bool:
    fields = {"bus_voltage_v", "current_ma", "power_mw", "pwm_percent", "driver_enabled"}
    return (
        isinstance(value, dict) and value.keys() == fields
        and all(type(value[key]) in (int, float) and math.isfinite(value[key])
                for key in ("bus_voltage_v", "current_ma", "power_mw"))
        and value["bus_voltage_v"] >= 0
        and type(value["pwm_percent"]) is int and 0 <= value["pwm_percent"] <= 80
        and type(value["driver_enabled"]) is bool
    )


def _checked_response(payload: dict) -> dict:
    """Validate the exact read_current subset of the existing N03 wire contract."""
    common = {"protocol_version", "response_type", "request_id", "command"}
    kind = payload.get("response_type")
    if payload.get("protocol_version") != "1.0.0" or payload.get("command") != "read_current":
        raise SerialReadError("serial_response_invalid")
    if kind == "ack":
        if (payload.keys() != common | {"accepted", "duplicate", "writes_enabled"}
                or any(type(payload[field]) is not bool
                       for field in ("accepted", "duplicate", "writes_enabled"))):
            raise SerialReadError("serial_response_invalid")
        if not payload["accepted"] or payload["duplicate"]:
            raise SerialReadError("serial_read_not_fresh")
        return {"response_type": kind}
    if kind == "error":
        # Do not expose device-supplied error messages to the planner or API.
        raise SerialReadError("serial_device_error")
    fields = common | {"completed_at_ms", "elapsed_ms", "hardware_effect",
                       "result", "before", "after"}
    if (kind != "result" or payload.keys() != fields
            or payload["hardware_effect"] is not False
            or any(type(payload[key]) is not int or not 0 <= payload[key] <= 2**53
                   for key in ("completed_at_ms", "elapsed_ms"))
            or not _snapshot_valid(payload["before"])
            or not _snapshot_valid(payload["after"])
            or not isinstance(payload["result"], dict)
            or payload["result"].keys() != {"current_ma"}
            or type(payload["result"]["current_ma"]) not in (int, float)
            or payload["result"]["current_ma"] != payload["before"]["current_ma"]):
        raise SerialReadError("serial_response_invalid")
    return {key: deepcopy(payload[key]) for key in (
        "request_id", "command", "completed_at_ms", "elapsed_ms", "before", "after",
    )}


class SerialReadChannel:
    """One outstanding read, no reconnect replay, no hardware write vocabulary."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connection_id: str | None = None
        self._latest: dict | None = None
        self._raw: dict | None = None
        self._received = 0.0
        self._pending: PendingRead | None = None

    def connect(self) -> None:
        with self._lock:
            self.disconnect()
            self._connection_id = uuid4().hex

    def disconnect(self) -> None:
        with self._lock:
            self._fail("serial_disconnected")
            self._connection_id = None
            self._latest = self._raw = None
            self._received = 0.0

    def invalidate(self) -> None:
        """Unknown identity or a reset invalidates any in-flight measurement."""
        with self._lock:
            self._fail("serial_identity_changed")
            self._latest = self._raw = None
            self._received = 0.0
            if self._connection_id is not None:
                self._connection_id = uuid4().hex

    def observe(self, raw: dict) -> dict | None:
        checked = validate_contract("telemetry", raw)
        with self._lock:
            if self._connection_id is None:
                return None
            if checked["quality"]["source"] != "device":
                self.invalidate()
                return None
            if self._raw is not None:
                if checked == self._raw:
                    return None  # A repeated frame cannot establish freshness.
                if (checked["device_id"] != self._raw["device_id"]
                        or checked["hardware_model_id"] != self._raw["hardware_model_id"]
                        or checked["sequence"] <= self._raw["sequence"]):
                    self.invalidate()
            self._raw = checked
            sample = deepcopy(checked)
            # Firmware sample IDs repeat after reboot. Namespace by connection/reset
            # without replacing the missing device time with host receipt time.
            digest = hashlib.sha256(checked["sample_id"].encode()).hexdigest()[:24]
            sample["sample_id"] = f"serial-{self._connection_id}-{digest}"
            record = {"sample": sample, "provenance": {
                "transport": "serial", "connection_id": self._connection_id,
                "device_sample_id": checked["sample_id"],
                "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }}
            self._latest = record
            self._received = monotonic()
            pending = self._pending
            if pending is not None and pending.terminal is not None:
                if (pending.device_id != sample["device_id"]
                        or pending.hardware_model_id != sample["hardware_model_id"]
                        or pending.connection_id != self._connection_id):
                    self._fail("serial_identity_changed")
                elif monotonic() >= pending.deadline:
                    self._fail("serial_read_timeout")
                else:
                    result = deepcopy(record)
                    result["device_command"] = pending.terminal
                    self._complete(result=result)
            return deepcopy(record)

    def latest(self, device_id: str, hardware_model_id: str) -> dict | None:
        with self._lock:
            if (self._latest is None or monotonic() - self._received > 5
                    or self._latest["sample"]["device_id"] != device_id
                    or self._latest["sample"]["hardware_model_id"] != hardware_model_id):
                return None
            return deepcopy(self._latest)

    async def read(self, *, device_id: str, hardware_model_id: str,
                   tool_call_id: str, timeout_seconds: float = 3.0) -> dict:
        if (not isinstance(tool_call_id, str)
                or re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", tool_call_id) is None):
            raise SerialReadError("serial_request_invalid")
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 5):
            raise SerialReadError("serial_timeout_invalid")
        loop = asyncio.get_running_loop()
        with self._lock:
            if self.latest(device_id, hardware_model_id) is None:
                raise SerialReadError("serial_device_unavailable")
            if self._pending is not None:
                raise SerialReadError("serial_busy")
            pending = PendingRead(
                request={"protocol_version": "1.0.0", "request_id": tool_call_id,
                         "command": "read_current", "arguments": {}, "timeout_ms": 1000},
                device_id=device_id, hardware_model_id=hardware_model_id,
                connection_id=self._connection_id, deadline=monotonic() + timeout_seconds,
                loop=loop, future=loop.create_future(),
            )
            self._pending = pending
        try:
            return await asyncio.wait_for(pending.future, timeout_seconds)
        except TimeoutError:
            raise SerialReadError("serial_read_timeout") from None
        finally:
            with self._lock:
                if self._pending is pending:
                    self._pending = None

    def flush(self, device) -> None:
        """Called only by the serial owner's worker; never opens a second port."""
        with self._lock:
            pending = self._pending
            if pending is None or pending.sent:
                return
            if (pending.future.done() or monotonic() >= pending.deadline
                    or pending.connection_id != self._connection_id):
                self._fail("serial_read_timeout")
                return
            pending.sent = True
            wire = json.dumps(pending.request, separators=(",", ":")).encode() + b"\n"
            try:
                if device.write(wire) != len(wire):
                    raise OSError("partial write")
            except (OSError, RuntimeError):
                self._fail("serial_write_failed")

    def receive(self, payload: object) -> None:
        with self._lock:
            pending = self._pending
            if (pending is None or not pending.sent or not isinstance(payload, dict)
                    or payload.get("request_id") != pending.request["request_id"]):
                return
            try:
                checked = _checked_response(payload)
                if monotonic() >= pending.deadline:
                    raise SerialReadError("serial_read_timeout")
                if checked.get("response_type") == "ack":
                    if pending.acknowledged:
                        raise SerialReadError("serial_response_invalid")
                    pending.acknowledged = True
                else:
                    if not pending.acknowledged or pending.terminal is not None:
                        raise SerialReadError("serial_response_invalid")
                    pending.terminal = checked
            except SerialReadError as exc:
                self._fail(str(exc))

    def _fail(self, code: str) -> None:
        self._complete(error=SerialReadError(code))

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
