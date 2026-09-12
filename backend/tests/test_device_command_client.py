import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "nexus_device_command.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("nexus_device_command", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
nexus_device_command = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = nexus_device_command
SPEC.loader.exec_module(nexus_device_command)

DeviceCommandError = nexus_device_command.DeviceCommandError
build_request = nexus_device_command.build_request
exchange = nexus_device_command.exchange
parse_response = nexus_device_command.parse_response


class FakeSerial:
    def __init__(self, responses: list[dict | bytes]) -> None:
        self.responses = deque(
            item if isinstance(item, bytes) else json.dumps(item).encode()
            for item in responses
        )
        self.written = b""

    def write(self, data: bytes) -> int:
        self.written += data
        return len(data)

    def readline(self) -> bytes:
        return self.responses.popleft() if self.responses else b"not-json"


def test_build_request_rejects_unsafe_values_before_serial_write() -> None:
    with pytest.raises(DeviceCommandError, match="between 0 and 80"):
        build_request("set_pwm", request_id="tool-1", timeout_ms=1000, pwm_percent=81)
    with pytest.raises(DeviceCommandError, match="exceed duration"):
        build_request(
            "run_motor_test",
            request_id="tool-2",
            timeout_ms=500,
            duration_ms=500,
        )
    with pytest.raises(DeviceCommandError, match="allowlisted"):
        build_request("read_gpio", request_id="tool-3", timeout_ms=1000, pin_id="gpio_0")


def test_exchange_ignores_telemetry_and_correlates_ack_and_result() -> None:
    request = build_request("read_voltage", request_id="tool-4", timeout_ms=1000)
    ack = {
        "protocol_version": "1.0.0",
        "response_type": "ack",
        "request_id": "tool-4",
        "command": "read_voltage",
        "accepted": True,
        "duplicate": False,
        "writes_enabled": False,
    }
    result = {
        "protocol_version": "1.0.0",
        "response_type": "result",
        "request_id": "tool-4",
        "command": "read_voltage",
        "completed_at_ms": 1200,
        "elapsed_ms": 2,
        "hardware_effect": False,
        "result": {"bus_voltage_v": 12.1},
        "before": {
            "bus_voltage_v": 12.1,
            "current_ma": 30.0,
            "power_mw": 363.0,
            "pwm_percent": 0,
            "driver_enabled": False,
        },
        "after": {
            "bus_voltage_v": 12.1,
            "current_ma": 30.0,
            "power_mw": 363.0,
            "pwm_percent": 0,
            "driver_enabled": False,
        },
    }
    device = FakeSerial([b'{"schema_version":"1.0.0"}', ack, result])

    completed = exchange(device, request)

    assert completed.ack == ack
    assert completed.terminal == result
    assert json.loads(device.written) == request


def test_response_parser_ignores_another_request_id() -> None:
    response = {
        "protocol_version": "1.0.0",
        "response_type": "ack",
        "request_id": "another-id",
    }
    assert parse_response(
        json.dumps(response).encode(), request_id="tool-5", command="read_voltage"
    ) is None


def test_response_parser_rejects_malformed_correlated_ack() -> None:
    response = {
        "protocol_version": "1.0.0",
        "response_type": "ack",
        "request_id": "tool-6",
        "command": "read_voltage",
        "accepted": True,
    }

    with pytest.raises(DeviceCommandError, match="invalid ack"):
        parse_response(
            json.dumps(response).encode(), request_id="tool-6", command="read_voltage"
        )
