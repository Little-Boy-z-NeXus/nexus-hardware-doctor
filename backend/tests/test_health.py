from fastapi.testclient import TestClient

from nexus_backend.app import app, create_app

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
    assert payload["hardware"]["hardware_model_id"] == "nexus-s3-ina226-l298n-motor-rig-v1"
    assert payload["hardware"]["controller"] == "GOOUUU Tech ESP32-S3-N16R8"
    assert payload["hardware"]["sensor"] == "INA226 with R100 0.1 ohm shunt"
    assert payload["hardware"]["driver"] == "L298N dual H-bridge module"


def test_active_hardware_profile_is_available_to_ui_and_agents() -> None:
    response = client.get("/api/v1/hardware-profile")

    assert response.status_code == 200
    profile = response.json()
    assert profile["profile_id"] == (
        "nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1"
    )
    assert profile["controller"]["family"] == "esp32"
    assert profile["firmware"]["pins"]["i2c_sda"] == 1
    assert profile["connections"][0]["from"]["component_id"] == "esp32"


def test_active_hardware_model_is_generated_from_profile() -> None:
    local_app = create_app(serial_device_id="nexus-runtime-device")
    with TestClient(local_app) as local_client:
        response = local_client.get("/api/v1/hardware-model")

    assert response.status_code == 200
    model = response.json()
    profile = client.get("/api/v1/hardware-profile").json()
    assert model["device_id"] == "nexus-runtime-device"
    assert model["hardware_model_id"] == profile["hardware_model_id"]
    assert len(model["components"]) == len(profile["components"])
    assert len(model["connections"]) == len(profile["connections"])


def test_telemetry_endpoint_does_not_invent_data_before_first_packet() -> None:
    response = client.get("/api/v1/telemetry")

    assert response.status_code == 404
    assert "telemetry" in response.json()["detail"]
