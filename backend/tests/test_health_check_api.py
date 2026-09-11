import json
from pathlib import Path

from fastapi.testclient import TestClient

from nexus_backend.app import create_app

MODEL = (
    Path(__file__).resolve().parents[2]
    / "nexus-contracts/v1/fixtures/hardware-model.example.json"
)


def hardware_model() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def test_health_check_endpoint_detects_five_volt_gpio_without_hardware(tmp_path) -> None:
    body = {
        "hardware_model": hardware_model(),
        "profile": {
            "pin_profiles": [
                {"component_id": "dc_motor", "pin_id": "encoder_a",
                 "direction": "output", "nominal_voltage_v": 5.0},
                {"component_id": "esp32", "pin_id": "gpio_16",
                 "direction": "input", "max_voltage_v": 3.3},
            ],
            "connection_readings": [
                {"connection_id": "motor_encoder_a_to_esp32", "voltage_v": 5.0},
            ],
        },
    }
    with TestClient(create_app(tmp_path / "n04.sqlite3")) as client:
        response = client.post("/api/v1/health-check", json=body)
    assert response.status_code == 200
    assert response.json()["findings"][0]["rule_id"] == "VOLTAGE_LIMIT_EXCEEDED"


def test_health_check_endpoint_rejects_unknown_profile_fields(tmp_path) -> None:
    body = {"hardware_model": hardware_model(), "profile": {"secret_rule": []}}
    with TestClient(create_app(tmp_path / "n04-invalid.sqlite3")) as client:
        response = client.post("/api/v1/health-check", json=body)
    assert response.status_code == 422
