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
