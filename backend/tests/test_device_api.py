"""H02/H03 acceptance against real API routes, SQLite, and WebSockets."""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_backend.app import create_app
from nexus_backend.validation import validate_contract

FIXTURES = Path(__file__).resolve().parents[2] / "nexus-contracts/v1/fixtures"


def model(device_id="nexus-demo-esp32"):
    document = json.loads((FIXTURES / "hardware-model.example.json").read_text())
    document["device_id"] = device_id
    return document


def sample(device_id="nexus-demo-esp32", sequence=1):
    document = json.loads((FIXTURES / "telemetry.example.json").read_text())
    document.update(device_id=device_id, sample_id=f"{device_id}-{sequence}", sequence=sequence)
    document["quality"]["source"] = "simulator"
    return document


def register(client, device_id="nexus-demo-esp32"):
    return client.post("/api/devices", json={
        "hardware_model": model(device_id), "display_name": "Simulated rig", "source": "simulator",
    })


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as connection:
        yield connection


def test_registration_telemetry_session_and_context_survive_restart(tmp_path):
    database = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(database)) as client:
        assert register(client).status_code == 201
        session = client.post("/api/devices/nexus-demo-esp32/sessions", json={
            "symptom": "Motor is not moving",
        })
        assert session.status_code == 201
        saved_session = session.json()
        assert saved_session["status"] == "created"
        for index in range(3):
            response = client.post("/api/devices/nexus-demo-esp32/telemetry", json=sample(sequence=index))
            assert response.status_code == 201
    with TestClient(create_app(database)) as client:
        assert len(client.get("/api/devices").json()) == 1
        assert client.get("/api/devices/nexus-demo-esp32/hardware-model").json() == model()
        assert client.get("/api/devices/nexus-demo-esp32/telemetry").json() == sample(sequence=2)
        assert client.get(
            f"/api/devices/nexus-demo-esp32/sessions/{saved_session['session_id']}"
        ).json() == saved_session
        context = client.post("/api/devices/nexus-demo-esp32/context", json={
            "symptom": "Motor is not moving", "max_samples": 2,
        })
        assert context.status_code == 200
        assert context.json()["available_tools"] == ["get_hardware_graph", "get_telemetry"]
        assert len(context.json()["telemetry"]) == 2
        assert context.json()["missing_metadata"]
        events = client.get("/api/devices/nexus-demo-esp32/events").json()
        telemetry_events = [event for event in events if event["event_type"] == "telemetry.received"]
        assert len(telemetry_events) == 3
        for event in telemetry_events:
            validate_contract("event", event)


def test_exact_retries_do_not_duplicate_samples_or_audit(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 201
    url = "/api/devices/nexus-demo-esp32/telemetry"
    first = client.post(url, json=sample())
    second = client.post(url, json=sample())
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
    assert second.json()["inserted"] is False
    changed = sample()
    changed["measurements"]["current_ma"] += 1
    assert client.post(url, json=changed).status_code == 409
    assert len(client.get(url + "/history").json()) == 1
    assert len(client.get("/api/devices/nexus-demo-esp32/events").json()) == 1


def test_devices_cannot_mix_samples_sessions_or_context(client):
    register(client)
    register(client, "nexus-second")
    assert client.post("/api/devices/nexus-second/telemetry", json=sample()).status_code == 409
    wrong_model = sample()
    wrong_model["hardware_model_id"] = "nexus-wrong"
    assert client.post(
        "/api/devices/nexus-demo-esp32/telemetry", json=wrong_model
    ).status_code == 409
    wrong_source = sample()
    wrong_source["quality"]["source"] = "device"
    assert client.post(
        "/api/devices/nexus-demo-esp32/telemetry", json=wrong_source
    ).status_code == 409
    session = client.post("/api/devices/nexus-demo-esp32/sessions", json={
        "symptom": "Motor stopped",
    }).json()
    assert client.get(f"/api/devices/nexus-second/sessions/{session['session_id']}").status_code == 404
    assert client.get("/api/devices/nexus-second/sessions").json() == []
    assert client.get("/api/devices/nexus-second/events").json() == []
    assert client.post("/api/devices/nexus-second/context", json={
        "symptom": "No data",
    }).json()["telemetry"] == []


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version="2.0.0"),
    lambda value: value.update(sequence="1"),
    lambda value: value.update(unknown="field"),
    lambda value: value["measurements"].update(pwm_percent=101),
    lambda value: value.update(recorded_at="not-a-time"),
    lambda value: value["measurements"].pop("motor_rpm"),
])
def test_invalid_raw_telemetry_is_rejected_without_persistence(client, mutation):
    register(client)
    payload = sample()
    mutation(payload)
    response = client.post("/api/devices/nexus-demo-esp32/telemetry", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"][0]["path"], str)
    assert client.get("/api/devices/nexus-demo-esp32/telemetry/history").json() == []


def test_registration_rejects_dangling_graph_and_unknown_device(client):
    payload = model()
    payload["connections"][0]["to_pin"] = "missing"
    response = client.post("/api/devices", json={
        "hardware_model": payload, "display_name": "Rig", "source": "simulator",
    })
    assert response.status_code == 422
    assert client.get("/api/devices").json() == []
    assert client.get("/api/devices/nexus-unknown/telemetry/history").status_code == 404
    assert client.post("/api/devices/nexus-unknown/sessions", json={
        "symptom": "No device",
    }).status_code == 404


def test_websocket_snapshot_new_samples_isolation_and_reconnect(client):
    register(client)
    register(client, "nexus-second")
    url = "/api/devices/nexus-demo-esp32/telemetry"
    assert client.post(url, json=sample()).status_code == 201
    with client.websocket_connect(url + "/stream") as websocket:
        assert websocket.receive_json() == {"type": "telemetry", "sample": sample()}
        client.post("/api/devices/nexus-second/telemetry", json=sample("nexus-second"))
        for index in (2, 3, 4):
            client.post(url, json=sample(sequence=index))
        for index in (2, 3, 4):
            assert websocket.receive_json() == {"type": "telemetry", "sample": sample(sequence=index)}
    with client.websocket_connect(url + "/stream") as websocket:
        assert websocket.receive_json()["sample"] == sample(sequence=4)


def test_empty_stream_receives_first_sample_and_sequence_reset(client):
    register(client)
    url = "/api/devices/nexus-demo-esp32/telemetry"
    with client.websocket_connect(url + "/stream") as websocket:
        client.post(url, json=sample(sequence=99))
        assert websocket.receive_json()["sample"]["sequence"] == 99
        rebooted = copy.deepcopy(sample(sequence=0))
        rebooted["sample_id"] = "new-boot-0"
        client.post(url, json=rebooted)
        assert websocket.receive_json()["sample"] == rebooted


def test_stream_rejects_unknown_device_and_untrusted_browser_origin(client):
    with (
        pytest.raises(WebSocketDisconnect) as missing,
        client.websocket_connect("/api/devices/nexus-unknown/telemetry/stream"),
    ):
        pass
    assert missing.value.code == 1008
    register(client)
    with (
        pytest.raises(WebSocketDisconnect) as foreign,
        client.websocket_connect(
            "/api/devices/nexus-demo-esp32/telemetry/stream",
            headers={"origin": "https://unrelated.example"},
        ),
    ):
        pass
    assert foreign.value.code == 1008


def test_query_bounds_empty_symptom_and_monitor(client):
    register(client)
    for endpoint in ["telemetry/history", "sessions", "events"]:
        assert client.get(f"/api/devices/nexus-demo-esp32/{endpoint}?limit=0").status_code == 422
        assert client.get(f"/api/devices/nexus-demo-esp32/{endpoint}?limit=10000").status_code == 422
    assert client.post("/api/devices/nexus-demo-esp32/context", json={
        "symptom": "   ",
    }).status_code == 422
    assert client.post("/api/devices/nexus-demo-esp32/context", json={
        "symptom": "Stopped", "max_samples": 21,
    }).status_code == 422
    assert client.get("/api/devices/nexus-demo-esp32/telemetry").status_code == 404
    assert client.get("/monitor").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/devices/{device_id}/context" in paths
    assert "/api/devices/{device_id}/telemetry" in paths


@pytest.mark.parametrize("field", ["hardware_model", "display_name"])
def test_invalid_unicode_is_rejected_before_registration(client, field):
    payload = {"hardware_model": model(), "display_name": "Rig", "source": "simulator"}
    if field == "hardware_model":
        payload[field]["name"] = "\ud800"
    else:
        payload[field] = "\ud800"
    response = client.post(
        "/api/devices", content=json.dumps(payload), headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert client.get("/api/devices").json() == []
