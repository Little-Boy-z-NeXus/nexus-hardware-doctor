"""Check an installed backend's actual startup and merged API surface."""

import json
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def read_json(base_url: str, path: str):
    with urlopen(base_url + path, timeout=2) as response:
        return json.load(response)


def main() -> None:
    base_url = sys.argv[1].rstrip("/")
    deadline = time.monotonic() + 30
    while True:
        try:
            health = read_json(base_url, "/health")
            break
        except (URLError, TimeoutError, ConnectionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    assert health["status"] == "ok"
    assert isinstance(read_json(base_url, "/api/devices"), list)
    snapshot = read_json(base_url, "/api/v1/live")
    assert "connection" in snapshot and "telemetry" in snapshot
    profile = read_json(base_url, "/api/v1/hardware-profile")
    assert profile["profile_id"].startswith("nexus-profile-")
    assert profile["controller"]["family"] == "esp32"
    capabilities = read_json(base_url, "/api/diagnosis/capabilities")
    assert capabilities["physical_commands_enabled"] is False
    paths = read_json(base_url, "/openapi.json")["paths"]
    assert "post" in paths["/api/devices/{device_id}/diagnoses"]
    assert "get" in paths["/api/v1/telemetry"]
    assert "get" in paths["/api/v1/hardware-profile"]
    with urlopen(base_url + "/doctor-lab", timeout=2) as response:
        assert response.status == 200
    print("Installed backend startup, device API, live API and diagnosis routes: PASS")


if __name__ == "__main__":
    main()
