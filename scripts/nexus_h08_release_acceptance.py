"""Probe a clean packaged NeXus backend and qualify H08 release behavior."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPOSITORY_ROOT / "nexus-contracts/v1/fixtures"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/H08/nexus-h08-release-acceptance.json"
DEVICE_ID = "nexus-h08-release-probe"
FORBIDDEN_FIELDS = {
    "api_key",
    "authorization",
    "credential",
    "prompt",
    "provider_body",
    "secret",
}


class AcceptanceError(RuntimeError):
    """A deterministic H08 acceptance failure."""


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    timeout: float = 5,
) -> tuple[int, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        base_url + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as decode_error:
            raise AcceptanceError("H08_NON_JSON_ERROR_RESPONSE") from decode_error


def request_text(base_url: str, path: str, *, timeout: float = 5) -> tuple[int, str]:
    with urlopen(base_url + path, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def forbidden_field_paths(value: object, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in FORBIDDEN_FIELDS:
                found.append(path)
            found.extend(forbidden_field_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(forbidden_field_paths(item, f"{prefix}[{index}]"))
    return found


def assess_runtime_inputs(
    *,
    health_status: int,
    health: object,
    capabilities_status: int,
    capabilities: object,
    live_status: int,
    live_body: object,
    lab_status: int,
    lab_html: str,
    register_status: int,
    telemetry_status: int,
    telemetry_body: object,
    mock_status: int,
    mock_session: object,
) -> dict:
    if health_status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        raise AcceptanceError("H08_HEALTH_CHECK_FAILED")
    if capabilities_status != 200 or not isinstance(capabilities, dict):
        raise AcceptanceError("H08_CAPABILITIES_FAILED")
    expected_disabled = {
        "live_enabled": False,
        "live_configured": False,
        "physical_commands_enabled": False,
        "serial_reads_enabled": False,
    }
    if any(capabilities.get(key) is not value for key, value in expected_disabled.items()):
        raise AcceptanceError("H08_CLEAN_RUNTIME_NOT_LOCKED_DOWN")
    if forbidden_field_paths(capabilities):
        raise AcceptanceError("H08_CAPABILITY_SECRET_FIELD_EXPOSED")
    if live_status != 503 or live_body != {
        "detail": "Live model access is not enabled and configured"
    }:
        raise AcceptanceError("H08_MODEL_OUTAGE_NOT_CONTROLLED")
    if forbidden_field_paths(live_body):
        raise AcceptanceError("H08_OUTAGE_SECRET_FIELD_EXPOSED")
    normalized_lab = lab_html.lower()
    if lab_status != 200 or "retry" not in normalized_lab or "textcontent" not in normalized_lab:
        raise AcceptanceError("H08_RETRY_UI_MISSING")
    if "innerhtml" in normalized_lab:
        raise AcceptanceError("H08_UNSAFE_MODEL_RENDERING")
    if register_status != 201:
        raise AcceptanceError("H08_DATABASE_NOT_CLEAN")
    if telemetry_status != 201 or not isinstance(telemetry_body, dict):
        raise AcceptanceError("H08_TELEMETRY_INGEST_FAILED")
    if telemetry_body.get("inserted") is not True:
        raise AcceptanceError("H08_TELEMETRY_NOT_INSERTED")
    if mock_status != 200 or not isinstance(mock_session, dict):
        raise AcceptanceError("H08_OFFLINE_FALLBACK_FAILED")
    result = mock_session.get("result")
    if not isinstance(result, dict) or result.get("mode") != "mock":
        raise AcceptanceError("H08_OFFLINE_FALLBACK_INVALID")
    if result.get("physical_commands_enabled") is not False or not result.get("events"):
        raise AcceptanceError("H08_OFFLINE_FALLBACK_UNSAFE")
    if not mock_session.get("session_id") or not mock_session.get("trace_id"):
        raise AcceptanceError("H08_OFFLINE_AUDIT_MISSING")
    return {
        "task_id": "H08",
        "outcome": "PASS",
        "checked_at": datetime.now(UTC).isoformat(),
        "packaged_runtime": {
            "health": "ok",
            "isolated_database": True,
            "serial_reads_enabled": False,
            "physical_commands_enabled": False,
        },
        "model_outage": {
            "http_status": 503,
            "controlled_message": True,
            "secret_fields_exposed": False,
            "retry_ui_available": True,
        },
        "offline_fallback": {
            "mode": "mock",
            "status": result.get("status"),
            "audit_events": len(result["events"]),
        },
        "scope": "H08 MVP reproducibility; local/container release path, not public hosting",
    }


def wait_for_health(base_url: str, timeout_seconds: float) -> tuple[int, object]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            status, payload = request_json(base_url, "/health", timeout=2)
            if status == 200:
                return status, payload
        except (URLError, TimeoutError, ConnectionError):
            pass
        if time.monotonic() >= deadline:
            raise AcceptanceError("H08_STARTUP_TIMEOUT")
        time.sleep(1)


def run_probe(base_url: str, *, startup_timeout: float = 30) -> dict:
    health_status, health = wait_for_health(base_url, startup_timeout)
    capabilities_status, capabilities = request_json(
        base_url, "/api/diagnosis/capabilities"
    )
    hardware_model = json.loads(
        (FIXTURES / "hardware-model.example.json").read_text(encoding="utf-8")
    )
    hardware_model["device_id"] = DEVICE_ID
    register_status, _ = request_json(
        base_url,
        "/api/devices",
        method="POST",
        payload={
            "hardware_model": hardware_model,
            "display_name": "H08 clean release probe",
            "source": "simulator",
        },
    )
    telemetry = json.loads(
        (FIXTURES / "telemetry.example.json").read_text(encoding="utf-8")
    )
    now = datetime.now(UTC)
    telemetry.update(
        device_id=DEVICE_ID,
        sample_id=f"{DEVICE_ID}-{int(now.timestamp() * 1000)}",
        recorded_at=now.isoformat(),
    )
    telemetry["quality"]["source"] = "simulator"
    telemetry_status, telemetry_body = request_json(
        base_url,
        f"/api/devices/{DEVICE_ID}/telemetry",
        method="POST",
        payload=telemetry,
    )
    live_status, live_body = request_json(
        base_url,
        f"/api/devices/{DEVICE_ID}/diagnoses",
        method="POST",
        payload={"mode": "live", "symptom": "The motor is not turning."},
    )
    mock_status, mock_session = request_json(
        base_url,
        f"/api/devices/{DEVICE_ID}/diagnoses",
        method="POST",
        payload={"mode": "mock", "symptom": "The motor is not turning."},
        timeout=35,
    )
    lab_status, lab_html = request_text(base_url, "/doctor-lab")
    return assess_runtime_inputs(
        health_status=health_status,
        health=health,
        capabilities_status=capabilities_status,
        capabilities=capabilities,
        live_status=live_status,
        live_body=live_body,
        lab_status=lab_status,
        lab_html=lab_html,
        register_status=register_status,
        telemetry_status=telemetry_status,
        telemetry_body=telemetry_body,
        mock_status=mock_status,
        mock_session=mock_session,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:18008")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--startup-timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        result = run_probe(args.base_url.rstrip("/"), startup_timeout=args.startup_timeout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (AcceptanceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        code = str(error) if isinstance(error, AcceptanceError) else "H08_PROBE_FAILED"
        print(json.dumps({"task_id": "H08", "outcome": "FAIL", "code": code}))
        return 1
    print(json.dumps({"task_id": "H08", "outcome": "PASS", "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
