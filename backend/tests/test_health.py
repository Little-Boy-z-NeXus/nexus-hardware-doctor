from fastapi.testclient import TestClient

from nexus_backend.app import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "nexus-backend"
    assert response.json()["status"] == "ok"
