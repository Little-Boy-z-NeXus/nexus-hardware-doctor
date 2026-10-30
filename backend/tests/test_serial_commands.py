"""Keyboard motor command leases stay bounded and correlated to one serial owner."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from nexus_backend.app import create_app
from nexus_backend.serial_bridge import SerialBridge
from nexus_backend.serial_commands import SerialCommandChannel, SerialCommandError


class Wire:
    def __init__(self):
        self.requests = []

    def write(self, wire):
        self.requests.append(json.loads(wire))
        return len(wire)


def responses(request, result):
    common = {key: request[key] for key in ("protocol_version", "request_id", "command")}
    return (
        {**common, "response_type": "ack", "accepted": True,
         "duplicate": False, "writes_enabled": True},
        {**common, "response_type": "result", "completed_at_ms": 100,
         "elapsed_ms": 2, "hardware_effect": True, "result": result,
         "before": {}, "after": {}},
    )


def test_drive_motor_is_correlated_and_returns_only_sanitized_fields():
    async def scenario():
        commands, wire = SerialCommandChannel(max_pwm_percent=80), Wire()
        commands.connect()
        arguments = {"direction": "reverse", "pwm_percent": 20, "hold_ms": 700}
        pending = asyncio.create_task(commands.execute("drive_motor", arguments))
        await asyncio.sleep(0)
        commands.flush(wire)
        request = wire.requests[0]
        assert request["command"] == "drive_motor"
        assert request["arguments"] == arguments
        ack, result = responses(request, {**arguments, "driver_enabled": True})
        commands.receive(ack)
        commands.receive(result)
        assert await pending == {"command": "drive_motor", **arguments}

    asyncio.run(scenario())


def test_reset_driver_is_the_only_stop_command():
    async def scenario():
        commands, wire = SerialCommandChannel(max_pwm_percent=80), Wire()
        commands.connect()
        pending = asyncio.create_task(commands.execute("reset_driver", {}))
        await asyncio.sleep(0)
        commands.flush(wire)
        ack, result = responses(wire.requests[0], {"reset": True})
        commands.receive(ack)
        commands.receive(result)
        assert await pending == {"command": "reset_driver", "stopped": True}

    asyncio.run(scenario())


@pytest.mark.parametrize("arguments", [
    {"direction": "left", "pwm_percent": 20, "hold_ms": 700},
    {"direction": "forward", "pwm_percent": 81, "hold_ms": 700},
    {"direction": "forward", "pwm_percent": 20, "hold_ms": 1001},
])
def test_invalid_motion_never_reaches_the_serial_wire(arguments):
    async def scenario():
        commands = SerialCommandChannel(max_pwm_percent=80)
        commands.connect()
        with pytest.raises(SerialCommandError, match="serial_command_invalid"):
            await commands.execute("drive_motor", arguments)

    asyncio.run(scenario())


def test_motor_control_api_maps_keyboard_actions_to_the_allowlist(tmp_path, monkeypatch):
    bridge = SerialBridge(enabled=False, persist_logs=False)
    calls = []

    async def execute(command, arguments, *, timeout_seconds):
        calls.append((command, arguments, timeout_seconds))
        return {"command": command}

    monkeypatch.setattr(bridge.commands, "execute", execute)
    with TestClient(create_app(tmp_path / "motor.sqlite3", bridge=bridge)) as client:
        response = client.post("/api/v1/motor/control", json={
            "action": "forward", "pwm_percent": 20, "hold_ms": 700,
        })
        assert response.status_code == 200
        assert calls[-1] == (
            "drive_motor",
            {"direction": "forward", "pwm_percent": 20, "hold_ms": 700},
            2.0,
        )
        assert client.post("/api/v1/motor/control", json={
            "action": "stop", "pwm_percent": 20, "hold_ms": 700,
        }).status_code == 200
        assert calls[-1][0:2] == ("reset_driver", {})
        assert client.post("/api/v1/motor/control", json={
            "action": "forward", "pwm_percent": 81, "hold_ms": 700,
        }).status_code == 422
