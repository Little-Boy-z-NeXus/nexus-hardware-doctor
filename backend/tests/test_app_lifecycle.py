"""Merged API families share a lifecycle without sharing state or touching USB."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_backend.app import create_app
from nexus_backend.serial_bridge import SerialBridge

FIXTURES = Path(__file__).resolve().parents[2] / "nexus-contracts/v1/fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.example.json").read_text())


class TrackingBridge(SerialBridge):
    def __init__(self, *, fail_start=False, fail_stop=False):
        super().__init__(enabled=False, persist_logs=False)
        self.starts = 0
        self.stops = 0
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.previous_sink = None

    def set_sink(self, sink):
        if sink is not None:
            self.previous_sink = sink
        super().set_sink(sink)

    def start(self):
        self.starts += 1
        if self.fail_start:
            raise RuntimeError("bridge startup failed")

    def stop(self):
        self.stops += 1
        super().stop()
        if self.fail_stop:
            raise RuntimeError("bridge shutdown failed")


def test_single_app_serves_both_api_families_and_retains_device_data(tmp_path):
    bridge = TrackingBridge()
    app = create_app(tmp_path / "persistent.sqlite3", bridge=bridge)
    with TestClient(app) as client:
        assert bridge.starts == 1
        model = fixture("hardware-model")
        registered = client.post("/api/devices", json={
            "hardware_model": model, "display_name": "Stored simulator", "source": "simulator",
        })
        assert registered.status_code == 201
        sample = fixture("telemetry")
        sample["quality"]["source"] = "simulator"
        path = f"/api/devices/{model['device_id']}"
        assert client.post(path + "/telemetry", json=sample).status_code == 201
        assert client.post(path + "/sessions", json={"symptom": "Check current"}).status_code == 201
        assert client.get("/api/v1/telemetry").status_code == 404
        bridge.ingest_line(json.dumps(fixture("telemetry")))
        assert client.get("/api/v1/live").json()["telemetry"]["quality"]["source"] == "device"
        assert client.get(path + "/telemetry").json()["quality"]["source"] == "simulator"
        assert client.get("/monitor").status_code == 200
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/devices" in paths and "/api/v1/live" in paths
        assert len([route for route in app.routes if getattr(route, "path", None) == "/health"]) == 1
        response = client.options("/api/devices", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        })
        assert response.status_code == 200
    assert bridge.stops == 1 and bridge._sink is None
    with pytest.raises(sqlite3.ProgrammingError):
        app.state.store.list_devices()
    with TestClient(create_app(tmp_path / "persistent.sqlite3")) as restarted:
        assert restarted.get(path + "/telemetry").json() == sample
        assert len(restarted.get(path + "/sessions").json()) == 1


def test_factory_is_hardware_inert_by_default_even_when_environment_enables_serial(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("NEXUS_SERIAL_ENABLED", "true")

    def unexpected_port_scan(*args, **kwargs):
        raise AssertionError("Test applications must not access serial hardware")

    monkeypatch.setattr(SerialBridge, "_detect_port", unexpected_port_scan)
    app = create_app(tmp_path / "safe.sqlite3")
    assert app.state.serial_bridge.enabled is False
    with TestClient(app) as client:
        assert client.get("/api/v1/live").json()["connection"]["status"] == "disabled"
        assert app.state.serial_bridge._thread is None


def test_apps_do_not_share_bridge_snapshots_or_websocket_hubs(tmp_path):
    one = create_app(tmp_path / "one.sqlite3", bridge=TrackingBridge())
    two = create_app(tmp_path / "two.sqlite3", bridge=TrackingBridge())
    assert one.state.live_hub is not two.state.live_hub
    assert one.state.serial_bridge is not two.state.serial_bridge
    with TestClient(one) as first, TestClient(two) as second:
        one.state.serial_bridge.ingest_line(json.dumps(fixture("telemetry")))
        assert first.get("/api/v1/telemetry").status_code == 200
        assert second.get("/api/v1/telemetry").status_code == 404
        assert second.get("/api/v1/logs").json() == []
        assert first.get("/api/devices").json() == second.get("/api/devices").json() == []


@pytest.mark.parametrize("failure", ["startup", "shutdown", "application"])
def test_bridge_and_database_cleanup_survives_lifecycle_errors(tmp_path, failure):
    bridge = TrackingBridge(fail_start=failure == "startup", fail_stop=failure == "shutdown")
    app = create_app(tmp_path / "cleanup.sqlite3", bridge=bridge)
    with pytest.raises(RuntimeError), TestClient(app):
        if failure == "application":
            raise RuntimeError("application body failed")
    assert bridge.starts == bridge.stops == 1
    assert bridge._sink is None
    with pytest.raises(sqlite3.ProgrammingError):
        app.state.store.list_devices()
    # A previously captured worker callback becomes inert after the loop closes.
    bridge.previous_sink(bridge.snapshot())


def test_live_websocket_streams_then_releases_idle_subscriber_on_disconnect(tmp_path):
    bridge = TrackingBridge()
    app = create_app(tmp_path / "websocket.sqlite3", bridge=bridge)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/live/ws") as socket:
            assert socket.receive_json()["data"]["telemetry"] is None
            sample = fixture("telemetry")
            bridge.ingest_line(json.dumps(sample))
            assert socket.receive_json()["data"]["telemetry"] == sample
            assert len(app.state.live_hub._subscribers) == 1
        assert not app.state.live_hub._subscribers
        # Reconnect delivers the current snapshot even without another serial line.
        with client.websocket_connect("/api/v1/live/ws") as socket:
            assert socket.receive_json()["data"]["telemetry"] == sample
        assert not app.state.live_hub._subscribers


def test_live_websocket_uses_the_existing_origin_policy(tmp_path):
    app = create_app(tmp_path / "origin.sqlite3")
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as caught, client.websocket_connect(
            "/api/v1/live/ws", headers={"Origin": "https://other.test"},
        ):
            pass
        assert caught.value.code == 1008
        with client.websocket_connect("/api/v1/live/ws", headers={"Origin": "http://localhost:5173"}) as socket:
            assert socket.receive_json()["type"] == "snapshot"


def test_live_log_bounds_and_diagnostic_filters_preserved(tmp_path):
    bridge = TrackingBridge()
    app = create_app(tmp_path / "live.sqlite3", bridge=bridge)
    with TestClient(app) as client:
        bridge.ingest_line("INA219_I2C_NO_ACK")
        assert client.get("/api/v1/diagnostics").json()[0]["active"] is True
        bridge.ingest_line(json.dumps(fixture("telemetry")))
        assert client.get("/api/v1/diagnostics").json() == []
        assert client.get("/api/v1/diagnostics?active_only=false").json()[0]["active"] is False
        assert len(client.get("/api/v1/logs?limit=1").json()) == 1
        assert len(client.get("/api/v1/logs?limit=-10").json()) == 1
