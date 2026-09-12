"""Run the actual bridge, API, policy and SQLite store against an in-memory N03 port."""

import asyncio
import json
import queue
import time
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from test_serial_reads import FIXTURES, responses, sample

from nexus_backend.app import create_app
from nexus_backend.context import build_context
from nexus_backend.hardware_profile import load_hardware_profile, profile_fingerprint
from nexus_backend.policy import PolicyDecision, SafetyPolicy
from nexus_backend.serial_bridge import SerialBridge
from nexus_backend.serial_history import SerialHistory
from nexus_backend.store import SQLiteStore
from nexus_backend.tool_adapter import SerialToolAdapter, ToolExecutionError


def model():
    return json.loads((FIXTURES / "hardware-model.example.json").read_text())


def registered_database(path, source="device"):
    store = SQLiteStore(path)
    store.register_device(model(), "Bound rig", source)
    return store


class SimulatedPort:
    """Only used through a patched serial constructor; never scans or opens USB."""

    def __init__(self, *, malformed=False):
        self.lines = queue.Queue()
        self.requests = []
        self.sequence = 10
        self.malformed = malformed
        self.closed = False
        profile = load_hardware_profile()
        controller = profile["controller"]
        self.emit_raw(
            "[NEXUS][INFO][HARDWARE_PROFILE] "
            f"profile_version={profile['schema_version']} "
            f"profile_id={profile['profile_id']} "
            f"profile_sha256={profile_fingerprint(profile)} "
            f"hardware_model_id={profile['hardware_model_id']} "
            f"controller={controller['board_id']} "
            f"sensor={profile['firmware']['sensor_profile']} "
            f"driver={profile['firmware']['driver_profile']}"
        )
        self.emit(sample(self.sequence))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def emit(self, value):
        self.emit_raw(json.dumps(value))

    def emit_raw(self, value):
        wire = value.encode() + b"\n"
        # Split every message to exercise timeout-delimited partial serial lines.
        self.lines.put(wire[:13])
        self.lines.put(wire[13:])

    def readline(self, size=-1):
        try:
            return self.lines.get(timeout=0.01)
        except queue.Empty:
            return b""

    def write(self, wire):
        request = json.loads(wire)
        self.requests.append(request)
        assert request["command"] == "read_current" and request["arguments"] == {}
        ack, terminal = responses(request)
        self.emit(ack)
        if self.malformed:
            terminal["after"]["current_ma"] = None
        self.emit(terminal)
        self.sequence += 1
        self.emit(sample(self.sequence))
        return len(wire)


def wait_until(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Simulated serial bridge did not reach the expected state")
        time.sleep(0.005)


def configured_app(tmp_path, monkeypatch, *, source="device", malformed=False, bind=True):
    database = tmp_path / "nexus.sqlite3"
    if bind:
        registered_database(database, source).close()
    port = SimulatedPort(malformed=malformed)
    opens = []

    def open_port(*args, **kwargs):
        opens.append((args, kwargs))
        return port

    monkeypatch.setattr("nexus_backend.serial_bridge.serial.Serial", open_port)
    bridge = SerialBridge(enabled=True, configured_port="IN_MEMORY_TEST_PORT", persist_logs=False)
    app = create_app(database, bridge=bridge,
                     serial_device_id=model()["device_id"] if bind else None)
    return app, bridge, port, opens


def test_serial_history_is_explicit_source_bound_and_durable(tmp_path, monkeypatch):
    app, bridge, port, opens = configured_app(tmp_path, monkeypatch)
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        stored = client.get(path + "/telemetry").json()
        assert stored["recorded_at"] is None and stored["sequence"] == 10
        assert stored["sample_id"].startswith("serial-")
        assert stored["measurements"] == sample()["measurements"]
        audit = client.get(path + "/events").json()
        assert audit[0]["payload"]["provenance"]["device_sample_id"] == "firmware-10"
        assert audit[0]["payload"]["provenance"]["received_at"]
        port.emit(sample(0))  # Firmware reboot with reused IDs must not overwrite history.
        port.emit(sample(10))
        wait_until(lambda: len(app.state.store.telemetry_history(model()["device_id"])) == 3)
        history = app.state.store.telemetry_history(model()["device_id"])
        assert len({item["sample_id"] for item in history}) == 3
        assert client.get("/api/diagnosis/capabilities").json()["serial_history_status"] == "receiving"
        with client.websocket_connect(path + "/telemetry/stream") as socket:
            # The persistent H02 WebSocket also sees serial-origin measurements.
            message = socket.receive_json()
            assert stored["device_id"] in json.dumps(message)
    assert len(opens) == 1 and port.closed
    assert bridge._sample_sink is None
    with TestClient(create_app(tmp_path / "nexus.sqlite3")) as restarted:
        assert restarted.get(path + "/telemetry").json() == history[-1]
        assert len(restarted.get(path + "/events").json()) == 3


def test_serial_frames_cannot_change_a_registered_simulator(tmp_path, monkeypatch):
    app, bridge, port, _ = configured_app(tmp_path, monkeypatch, source="simulator")
    with TestClient(app) as client:
        wait_until(lambda: bridge.snapshot()["telemetry"] is not None)
        path = f"/api/devices/{model()['device_id']}"
        assert client.get(path + "/telemetry").status_code == 404
        assert client.get(path).json()["source"] == "simulator"
        assert not port.requests
        status = client.get("/api/diagnosis/capabilities").json()["serial_history_status"]
        assert status == "serial_history_rejected"


def test_profile_verified_serial_device_is_discovered_and_registered(tmp_path, monkeypatch):
    app, bridge, _port, _ = configured_app(tmp_path, monkeypatch, bind=False)
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        device = client.get(path).json()
        capability = client.get("/api/diagnosis/capabilities").json()
        assert device["source"] == "device"
        assert device["hardware_model_id"] == load_hardware_profile()["hardware_model_id"]
        assert capability["serial_device_id"] == model()["device_id"]
        assert capability["serial_history_status"] == "receiving"
        assert bridge.snapshot()["compatibility"]["firmware_profile_verified"] is True


class ReadThenStop:
    def __init__(self, next_action=None):
        self.next_action = next_action
        self.inputs = []

    async def plan(self, context, observations):
        self.inputs.append(deepcopy((context, observations)))
        tool = {"tool_name": "get_telemetry", "arguments": {}} if not observations else self.next_action
        evidence = ([observations[-1]["evidence_id"]] if observations else
                    [context["telemetry"][-1]["sample_id"]] if context["telemetry"] else [])
        return {"hypotheses": [{"id": "pwm", "label": "PWM needs inspection", "confidence": 0.6,
                                "evidence_ids": evidence}],
                "next_tool": tool, "confidence": 0.6, "user_message": "Check PWM measurements",
                "stop_condition": "continue" if tool else "needs_manual"}


def live_stub(monkeypatch, planner):
    monkeypatch.setenv("NEXUS_ENABLE_LIVE_MODEL", "true")
    for key in ("NEXUS_NEBIUS_BASE_URL", "NEXUS_NEBIUS_API_KEY", "NEXUS_NVIDIA_MODEL"):
        monkeypatch.setenv(key, "unit-test-only")
    monkeypatch.setattr("nexus_backend.diagnosis.NebiusPlanner.from_env", lambda: planner)


@pytest.mark.parametrize("next_action", [
    None, {"tool_name": "set_pwm", "arguments": {"pwm_percent": 20}},
    {"tool_name": "enable_driver", "arguments": {"enabled": True}},
    {"tool_name": "run_motor_test", "arguments": {"duration_ms": 500}},
    {"tool_name": "read_gpio", "arguments": {"pin_id": "gpio_16"}},
])
def test_api_uses_one_shared_port_and_correlates_policy_read_measurement_and_history(
    tmp_path, monkeypatch, next_action,
):
    app, _bridge, port, opens = configured_app(tmp_path, monkeypatch)
    planner = ReadThenStop(next_action)
    live_stub(monkeypatch, planner)
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        response = client.post(path + "/diagnoses", json={"symptom": "Motor stopped", "mode": "live"})
        assert response.status_code == 200, response.text
        session = response.json()
        result = session["result"]
        assert result["status"] == ("blocked" if next_action and next_action["tool_name"] == "read_gpio"
                                    else "needs_manual")
        observation = result["observations"][0]
        assert observation["status"] == "succeeded"
        assert observation["source"] == "device"
        assert result["source"] == "device"
        assert result["physical_commands_enabled"] is False
        assert result["physical_operation_verified"] is False
        assert len(port.requests) == 1
        assert port.requests[0]["request_id"] == observation["tool_call_id"]
        assert observation["data"]["device_command"]["request_id"] == observation["tool_call_id"]
        assert observation["data"]["sample"] == client.get(path + "/telemetry").json()
        assert observation["data"]["sample"] == planner.inputs[1][0]["telemetry"][-1]
        assert observation["data"]["sample"]["recorded_at"] is None
        read_events = [event for event in result["events"]
                       if event["related_tool_call_id"] == observation["tool_call_id"]]
        assert [event["event_type"] for event in read_events] == ["action.approved", "action.executed"]
        if next_action:
            assert result["events"][-1]["event_type"] == "action.rejected"
        session_path = path + f"/sessions/{session['session_id']}"
        assert client.get(session_path + "/events").json() == result["events"]
    assert len(opens) == 1 and port.closed
    with TestClient(create_app(tmp_path / "nexus.sqlite3")) as client:
        assert client.get(session_path).json() == session


def test_u07_requires_a_fresh_serial_read_before_live_hypothesis(tmp_path, monkeypatch):
    app, _bridge, port, _opens = configured_app(tmp_path, monkeypatch)
    planner = ReadThenStop()
    planner.source = "nebius"
    planner.last_attempts = []
    original_plan = planner.plan

    async def plan_with_runtime(context, observations):
        result = await original_plan(context, observations)
        planner.last_attempts = [{
            "requested_model": "nvidia/test-nemotron",
            "response_model": "nvidia/test-nemotron",
            "response_id": f"chatcmpl-{len(planner.inputs)}",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "private": "must-not-be-persisted",
        }]
        return result

    planner.plan = plan_with_runtime
    live_stub(monkeypatch, planner)
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        response = client.post(path + "/diagnoses", json={
            "symptom": "Read fresh telemetry before diagnosing", "mode": "live",
            "require_fresh_read": True,
        })
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert planner.inputs[0][0]["telemetry"] == []
        assert result["source"] == "device"
        assert result["observations"][0]["tool_name"] == "get_telemetry"
        assert result["observations"][0]["status"] == "succeeded"
        assert len(port.requests) == 1
        assert [item["response_id"] for item in result["model_runtime"]["calls"]] == [
            "chatcmpl-1", "chatcmpl-2",
        ]
        assert "private" not in json.dumps(result["model_runtime"])


def test_fresh_read_gate_accepts_a_discovered_profile_verified_device(
    tmp_path, monkeypatch,
):
    app, _bridge, _port, _opens = configured_app(tmp_path, monkeypatch, bind=False)
    live_stub(monkeypatch, ReadThenStop())
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        response = client.post(path + "/diagnoses", json={
            "symptom": "Read fresh telemetry", "mode": "live", "require_fresh_read": True,
        })
        assert response.status_code == 200, response.text
        assert response.json()["result"]["observations"][0]["source"] == "device"


def test_history_failure_is_not_a_successful_tool_measurement(tmp_path):
    store = registered_database(tmp_path / "nexus.sqlite3", source="simulator")
    history = SerialHistory(store, model()["device_id"])
    from test_serial_reads import channel

    reads = channel()
    record = reads.latest(model()["device_id"], model()["hardware_model_id"])
    with pytest.raises(ToolExecutionError):
        history.persist(record)
    assert store.telemetry_history(model()["device_id"]) == []
    assert history.status == "serial_history_rejected"
    store.close()


def test_invalid_device_results_follow_bounded_recovery_without_a_success_claim(tmp_path, monkeypatch):
    class Recover(ReadThenStop):
        async def plan(self, context, observations):
            value = await super().plan(context, observations)
            if observations:
                value["hypotheses"][0].update(id="tool_error", label="Read failed")
            return value

    app, _bridge, port, _opens = configured_app(tmp_path, monkeypatch, malformed=True)
    live_stub(monkeypatch, Recover())
    path = f"/api/devices/{model()['device_id']}"
    with TestClient(app) as client:
        wait_until(lambda: client.get(path + "/telemetry").status_code == 200)
        response = client.post(path + "/diagnoses", json={"symptom": "Read failed", "mode": "live"})
        result = response.json()["result"]
        assert result["status"] == "needs_manual"
        assert len(port.requests) == 2  # One original read and one bounded retry.
        assert len({item["request_id"] for item in port.requests}) == 1
        assert result["observations"][0]["status"] == "failed"
        assert result["observations"][0]["data"] == {}
        assert all(event["event_type"] not in {"action.executed", "verification.passed"}
                   for event in result["events"])
        assert "No physical device commands were executed" not in result["limitations"]


def test_serial_registration_is_never_inferred_from_firmware_frames(tmp_path):
    from test_serial_reads import channel

    store = SQLiteStore(tmp_path / "empty.sqlite3")
    history = SerialHistory(store, model()["device_id"])
    record = channel().latest(model()["device_id"], model()["hardware_model_id"])
    history.ingest(record)
    assert history.status == "serial_history_rejected"
    assert store.list_devices() == []
    store.close()


def test_adapter_rejects_writes_even_with_a_permissive_injected_policy(tmp_path):
    class Permissive(SafetyPolicy):
        def evaluate(self, *args, **kwargs):
            return PolicyDecision("auto_safe", True, "test injection", False)

    class NoTransport:
        async def read(self, **kwargs):
            raise AssertionError("Rejected action must not reach serial transport")

    store = registered_database(tmp_path / "nexus.sqlite3")
    adapter = SerialToolAdapter(build_context(model(), [sample()], "Check motor"),
                                reads=NoTransport(), history=SerialHistory(store, model()["device_id"]),
                                policy=Permissive())
    for name, arguments in [("set_pwm", {"pwm_percent": 20}),
                            ("enable_driver", {"enabled": True}),
                            ("run_motor_test", {"duration_ms": 500})]:
        with pytest.raises(ToolExecutionError):
            asyncio.run(adapter.execute(name, arguments))
    store.close()
