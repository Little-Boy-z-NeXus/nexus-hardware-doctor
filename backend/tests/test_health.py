from fastapi.testclient import TestClient

from nexus_backend.app import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "nexus-backend",
        "version": "0.1.0",
    }


def test_openapi_describes_health_contract() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"] == {"title": "nexus-backend", "version": "0.1.0"}
    assert "get" in document["paths"]["/health"]


def test_live_snapshot_exposes_fixed_mvp_hardware() -> None:
    response = client.get("/api/v1/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hardware"]["hardware_model_id"] == "nexus-s3-l298n-motor-rig-v1"
    assert payload["hardware"]["controller"] == "GOOUUU Tech ESP32-S3-N16R8"
    assert payload["hardware"]["sensor"] == "INA219"
    assert payload["hardware"]["driver"] == "L298N"


def test_telemetry_endpoint_does_not_invent_data_before_first_packet() -> None:
    response = client.get("/api/v1/telemetry")

    assert response.status_code == 404
    assert "telemetry" in response.json()["detail"]
