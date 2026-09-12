"""N03 read correlation, lifecycle bounds and persistence without a physical port."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_backend.serial_reads import SerialReadChannel, SerialReadError

FIXTURES = Path(__file__).parents[2] / "nexus-contracts/v1/fixtures"


def sample(sequence=10):
    value = json.loads((FIXTURES / "telemetry.example.json").read_text())
    value.update(sequence=sequence, sample_id=f"firmware-{sequence}", recorded_at=None)
    return value


def responses(request):
    common = {key: request[key] for key in ("protocol_version", "request_id", "command")}
    measured = sample()["measurements"]
    measured.pop("motor_rpm")
    ack = {**common, "response_type": "ack", "accepted": True,
           "duplicate": False, "writes_enabled": False}
    terminal = {**common, "response_type": "result", "completed_at_ms": 1000,
                "elapsed_ms": 2, "hardware_effect": False,
                "result": {"current_ma": measured["current_ma"]},
                "before": deepcopy(measured), "after": deepcopy(measured)}
    return ack, terminal


class Wire:
    def __init__(self):
        self.requests = []

    def write(self, wire):
        self.requests.append(json.loads(wire))
        return len(wire)


def channel():
    value = SerialReadChannel()
    value.connect()
    value.observe(sample())
    return value


async def request(reads, tool_call_id="tool-1", timeout_seconds=0.3):
    task = asyncio.create_task(reads.read(
        device_id=sample()["device_id"], hardware_model_id=sample()["hardware_model_id"],
        tool_call_id=tool_call_id, timeout_seconds=timeout_seconds,
    ))
    await asyncio.sleep(0)
    return task


def test_success_requires_ack_result_then_new_telemetry_and_preserves_call_id():
    async def scenario():
        reads, wire = channel(), Wire()
        pending = await request(reads)
        reads.flush(wire)
        assert wire.requests == [{"protocol_version": "1.0.0", "request_id": "tool-1",
                                  "command": "read_current", "arguments": {}, "timeout_ms": 1000}]
        ack, terminal = responses(wire.requests[0])
        reads.observe(sample(11))  # A sample before the result cannot satisfy the read.
        reads.receive({**ack, "request_id": "other-call"})
        reads.receive(ack)
        reads.receive(terminal)
        reads.observe(sample(11))  # Nor can a repeated sample after it.
        await asyncio.sleep(0)
        assert not pending.done()
        record = reads.observe(sample(12))
        result = await pending
        assert result["sample"] == record["sample"]
        assert result["sample"]["recorded_at"] is None
        assert result["sample"]["sequence"] == 12
        assert result["provenance"]["device_sample_id"] == "firmware-12"
        assert result["device_command"]["request_id"] == "tool-1"
        assert "result" not in result["device_command"]

    asyncio.run(scenario())


@pytest.mark.parametrize("problem", [
    "no_ack", "negative_ack", "duplicate_ack", "cached", "wrong_command", "wrong_version",
    "effect", "nan", "null", "bool_number", "inconsistent_current", "extra_field", "device_error",
])
def test_unsuitable_responses_never_establish_measurements(problem):
    async def scenario():
        reads, wire = channel(), Wire()
        pending = await request(reads)
        reads.flush(wire)
        ack, terminal = responses(wire.requests[0])
        if problem == "negative_ack":
            ack["accepted"] = False
        elif problem == "cached":
            ack["duplicate"] = True
        elif problem == "wrong_command":
            terminal["command"] = "set_pwm"
        elif problem == "wrong_version":
            terminal["protocol_version"] = "2.0.0"
        elif problem == "effect":
            terminal["hardware_effect"] = True
        elif problem in {"nan", "null", "bool_number"}:
            terminal["after"]["current_ma"] = {"nan": float("nan"), "null": None,
                                               "bool_number": True}[problem]
        elif problem == "inconsistent_current":
            terminal["result"]["current_ma"] += 100
        elif problem == "extra_field":
            terminal["private_field"] = "untrusted firmware content"
        elif problem == "device_error":
            terminal = {**terminal, "response_type": "error",
                        "error": {"message": "private device message"}}
        if problem != "no_ack":
            reads.receive(ack)
        if problem == "duplicate_ack":
            reads.receive(ack)
        reads.receive(terminal)
        reads.observe(sample(11))
        with pytest.raises(SerialReadError) as caught:
            await pending
        assert "private" not in str(caught.value)

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["disconnect", "reset", "identity", "model", "source"])
def test_connection_identity_and_reset_changes_cancel_pending_reads(change):
    async def scenario():
        reads, wire = channel(), Wire()
        pending = await request(reads)
        reads.flush(wire)
        ack, terminal = responses(wire.requests[0])
        reads.receive(ack)
        reads.receive(terminal)
        changed = sample(11)
        if change == "disconnect":
            reads.disconnect()
            reads.connect()
        elif change == "reset":
            changed = sample(0)
        elif change == "identity":
            changed["device_id"] = "nexus-different-device"
        elif change == "model":
            changed["hardware_model_id"] = "nexus-different-model"
        else:
            changed["quality"]["source"] = "simulator"
        reads.observe(changed)
        with pytest.raises(SerialReadError):
            await pending

    asyncio.run(scenario())


def test_timeout_and_cancellation_remove_pending_commands_without_reconnect_replay():
    async def scenario():
        reads, wire = channel(), Wire()
        expired = await request(reads, timeout_seconds=0.01)
        with pytest.raises(SerialReadError, match="serial_read_timeout"):
            await expired
        reads.flush(wire)
        cancelled = await request(reads, tool_call_id="tool-2")
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        reads.flush(wire)
        reads.disconnect()
        reads.connect()
        reads.flush(wire)
        assert wire.requests == []

    asyncio.run(scenario())


def test_only_one_read_is_admitted_and_ack_alone_cannot_pass():
    async def scenario():
        reads, wire = channel(), Wire()
        first = await request(reads, timeout_seconds=0.02)
        second = await request(reads, tool_call_id="tool-2")
        with pytest.raises(SerialReadError, match="serial_busy"):
            await second
        reads.flush(wire)
        reads.receive(responses(wire.requests[0])[0])
        reads.observe(sample(11))
        with pytest.raises(SerialReadError, match="serial_read_timeout"):
            await first
        assert len(wire.requests) == 1

    asyncio.run(scenario())


def test_stale_identity_does_not_authorize_a_read(monkeypatch):
    async def scenario():
        reads = channel()
        monkeypatch.setattr("nexus_backend.serial_reads.monotonic", lambda: reads._received + 6)
        with pytest.raises(SerialReadError, match="serial_device_unavailable"):
            await (await request(reads))

    asyncio.run(scenario())


def test_sample_identity_survives_repeated_frame_but_changes_after_reset_or_reconnect():
    reads = channel()
    before = reads.latest(sample()["device_id"], sample()["hardware_model_id"])
    assert reads.observe(sample()) is None
    reads.observe(sample(0))
    after_reset = reads.observe(sample())
    reads.disconnect()
    reads.connect()
    after_reconnect = reads.observe(sample())
    assert len({item["sample"]["sample_id"]
                for item in (before, after_reset, after_reconnect)}) == 3
    assert all(item["sample"]["recorded_at"] is None
               for item in (before, after_reset, after_reconnect))


def test_partial_serial_write_fails_without_repeating_the_command():
    class BrokenWire(Wire):
        def write(self, wire):
            super().write(wire)
            return 1

    async def scenario():
        reads, wire = channel(), BrokenWire()
        pending = await request(reads)
        reads.flush(wire)
        reads.flush(wire)
        with pytest.raises(SerialReadError, match="serial_write_failed"):
            await pending
        assert len(wire.requests) == 1

    asyncio.run(scenario())
