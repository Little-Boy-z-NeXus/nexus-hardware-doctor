"""Integration checks for source isolation, workload limits and persisted run outcomes."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus_backend.app import create_app
from nexus_backend.runtime import RunLimiter

FIXTURES = Path(__file__).parents[2] / "nexus-contracts/v1/fixtures"


def register(client, device_id="nexus-demo-esp32", source="simulator"):
    model = json.loads((FIXTURES / "hardware-model.example.json").read_text())
    model["device_id"] = device_id
    assert client.post("/api/devices", json={
        "hardware_model": model, "source": source, "display_name": "Test rig",
    }).status_code == 201
    sample = json.loads((FIXTURES / "telemetry.example.json").read_text())
    sample.update(device_id=device_id, recorded_at=datetime.now(UTC).isoformat())
    sample["quality"]["source"] = source
    assert client.post(f"/api/devices/{device_id}/telemetry", json=sample).status_code == 201
    return sample


def test_mock_run_is_persisted_and_does_not_change_device_telemetry(tmp_path):
    app = create_app(tmp_path / "nexus.db")
    with TestClient(app) as client:
        original = register(client)
        response = client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "symptom": "The motor is not turning", "mode": "mock",
        })
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["result"]["mode"] == "mock"
        assert session["result"]["physical_commands_enabled"] is False
        assert session["result"]["events"], session
        assert client.get("/api/devices/nexus-demo-esp32/telemetry").json() == original
        register(client, device_id="nexus-other")
        path = f"/api/devices/nexus-demo-esp32/sessions/{session['session_id']}"
        assert client.get(path + "/events").json() == session["result"]["events"]
        assert client.get(path.replace("nexus-demo-esp32", "nexus-other")).status_code == 404
        assert client.get(path.replace("nexus-demo-esp32", "nexus-other") + "/events").status_code == 404
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        assert client.get(path).json() == session
        assert client.get(path + "/events").json() == session["result"]["events"]


def test_simulation_cannot_run_against_real_device(tmp_path):
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        register(client, source="device")
        assert client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "symptom": "motor stopped", "mode": "mock",
        }).status_code == 409
        assert client.get("/api/devices/nexus-demo-esp32/sessions").json() == []


def test_live_mode_requires_configuration_and_explicit_enablement(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_ENABLE_LIVE_MODEL", raising=False)
    monkeypatch.setenv("NEXUS_NEBIUS_API_KEY", "do-not-display-this-key")
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        register(client)
        response = client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "symptom": "motor stopped", "mode": "live",
        })
        assert response.status_code == 503
        assert "do-not-display" not in response.text
        capabilities = client.get("/api/diagnosis/capabilities")
        assert capabilities.json()["live_enabled"] is False
        assert "do-not-display" not in capabilities.text


def test_unexpected_provider_failure_is_saved_without_leaking_payload(tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("secret-api-key and unredacted telemetry")

    monkeypatch.setattr("nexus_backend.orchestrator.run_diagnosis", fail)
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        register(client)
        response = client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "symptom": "motor stopped",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert "secret-api-key" not in response.text
        assert "unredacted" not in response.text
        assert client.get("/api/devices/nexus-demo-esp32/sessions").json()[0]["status"] == "error"


def test_explicit_live_request_calls_configured_planner_with_read_only_tools(tmp_path, monkeypatch):
    from nexus_backend.diagnosis import NebiusPlanner

    calls = []

    class LiveTransportStub:
        async def plan(self, context, observations):
            calls.append(context)
            return {
                "hypotheses": [{"id": "pwm", "label": "PWM requires investigation",
                                "confidence": 0.5,
                                "evidence_ids": [context["telemetry"][-1]["sample_id"]]}],
                "next_tool": None, "confidence": 0.5,
                "user_message": "Inspect the reported PWM and wiring.",
                "stop_condition": "needs_manual",
            }

    monkeypatch.setattr(NebiusPlanner, "from_env", classmethod(lambda cls: LiveTransportStub()))
    for key, value in {
        "NEXUS_ENABLE_LIVE_MODEL": "true", "NEXUS_NEBIUS_API_KEY": "not-a-real-key",
        "NEXUS_NEBIUS_BASE_URL": "https://api.tokenfactory.nebius.com/v1",
        "NEXUS_NVIDIA_MODEL": "test-model",
    }.items():
        monkeypatch.setenv(key, value)
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        sample = register(client, source="device")
        response = client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "mode": "live", "symptom": "motor stopped",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "needs_manual", response.text
        assert response.json()["result"]["mode"] == "live"
        assert len(calls) == 1
        assert set(calls[0]["available_tools"]) == {"get_hardware_graph", "get_telemetry"}
        assert calls[0]["physical_actions_available"] is False
        assert len(calls[0]["hardware_model"]["components"]) == 5
        assert len(calls[0]["hardware_model"]["connections"]) == 18
        assert calls[0]["hardware_model"]["components"][0]["model"] == (
            "GOOUUU Tech ESP32-S3-N16R8"
        )
        assert client.get("/api/devices/nexus-demo-esp32/telemetry").json() == sample


def test_run_admission_is_bounded_and_recoverable(tmp_path):
    app = create_app(tmp_path / "nexus.db")
    with TestClient(app) as client:
        register(client)
        app.state.run_limiter = RunLimiter(per_minute=1)
        route = "/api/devices/nexus-demo-esp32/diagnoses"
        assert client.post(route, json={"symptom": "motor stopped"}).status_code == 200
        denied = client.post(route, json={"symptom": "motor stopped"})
        assert denied.status_code == 429 and denied.headers["retry-after"] == "60"
        assert len(client.get("/api/devices/nexus-demo-esp32/sessions").json()) == 1


def test_store_rejects_cross_trace_events_and_repeated_completion(tmp_path):
    from nexus_backend.store import StoreConflict

    app = create_app(tmp_path / "nexus.db")
    with TestClient(app) as client:
        register(client)
        session = app.state.store.create_session("nexus-demo-esp32", "test")
        event = {
            "schema_version": "1.0.0", "event_id": "test-event", "trace_id": "wrong-trace",
            "device_id": "nexus-demo-esp32", "event_type": "diagnosis.proposed",
            "occurred_at": datetime.now(UTC).isoformat(), "source": "backend",
            "severity": "info", "summary": "Test result", "payload": {},
            "related_tool_call_id": None,
        }
        result = {"status": "needs_manual", "trace_id": session["trace_id"], "events": [event]}
        with pytest.raises(StoreConflict):
            app.state.store.finish_diagnosis(session["device_id"], session["session_id"], result)
        assert app.state.store.get_session(session["device_id"], session["session_id"]) == session
        assert app.state.store.diagnosis_events(session["device_id"], session["session_id"]) == []
        event["trace_id"] = session["trace_id"]
        completed = app.state.store.finish_diagnosis(
            session["device_id"], session["session_id"], result,
        )
        with pytest.raises(StoreConflict):
            app.state.store.finish_diagnosis(session["device_id"], session["session_id"], result)
        assert app.state.store.get_session(session["device_id"], session["session_id"]) == completed


@pytest.mark.parametrize("steps", [0, 9, True, "2"])
def test_invalid_step_limits_are_rejected(tmp_path, steps):
    with TestClient(create_app(tmp_path / "nexus.db")) as client:
        assert client.post("/api/devices/nexus-demo-esp32/diagnoses", json={
            "symptom": "motor stopped", "max_steps": steps,
        }).status_code == 422
