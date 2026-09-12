"""Run the U07 physical telemetry -> UI -> Nemotron -> read-only tool acceptance."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx


class AcceptanceError(RuntimeError):
    """A user-actionable U07 gate failure with no secret or provider body."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def checked_url(value: str, name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise argparse.ArgumentTypeError(f"{name} must use loopback http/https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError(f"{name} must not contain credentials, query or fragment")
    return value.rstrip("/")


def request_json(client: httpx.Client, method: str, path: str, **kwargs) -> dict | list:
    try:
        response = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise AcceptanceError("HTTP_UNAVAILABLE", f"Không kết nối được {path}.") from exc
    if not 200 <= response.status_code < 300:
        raise AcceptanceError(
            "HTTP_REJECTED", f"{path} trả HTTP {response.status_code}; xem cửa sổ Backend.",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise AcceptanceError("HTTP_JSON_INVALID", f"{path} không trả JSON hợp lệ.") from exc


def require_runtime_preflight(
    capabilities: object, snapshot: object, hardware_model: object,
) -> dict:
    if (not isinstance(capabilities, dict) or not isinstance(snapshot, dict)
            or not isinstance(hardware_model, dict)):
        raise AcceptanceError("PREFLIGHT_INVALID", "Backend trả trạng thái U07 không hợp lệ.")
    missing = []
    for field, label in (
        ("live_enabled", "NEXUS_ENABLE_LIVE_MODEL=true"),
        ("live_configured", "ba biến NEXUS_NEBIUS_*"),
        ("serial_reads_enabled", "serial bridge đang bật"),
    ):
        if capabilities.get(field) is not True:
            missing.append(label)
    connection = snapshot.get("connection")
    telemetry = snapshot.get("telemetry")
    if not isinstance(connection, dict) or connection.get("status") != "connected":
        missing.append("ESP32 đang kết nối")
    if not isinstance(telemetry, dict):
        missing.append("telemetry device thật")
    elif capabilities.get("serial_device_id") != telemetry.get("device_id"):
        missing.append("device_id đã được nhận diện và bind động")
    if (isinstance(telemetry, dict)
            and (not isinstance(telemetry.get("quality"), dict)
                 or telemetry["quality"].get("source") != "device")):
        missing.append("telemetry nguồn device, không phải replay/simulator")
    if missing:
        raise AcceptanceError("U07_PREFLIGHT_BLOCKED", "Thiếu: " + "; ".join(missing) + ".")
    if (hardware_model.get("device_id") != telemetry.get("device_id")
            or hardware_model.get("hardware_model_id") != telemetry.get("hardware_model_id")):
        raise AcceptanceError(
            "HARDWARE_MODEL_MISMATCH",
            "Telemetry không khớp hardware model sinh từ profile đang hoạt động.",
        )
    compatibility = snapshot.get("compatibility")
    if (not isinstance(compatibility, dict)
            or compatibility.get("firmware_profile_verified") is not True
            or compatibility.get("sensor_identity_verified") is not True):
        raise AcceptanceError(
            "HARDWARE_PROFILE_NOT_VERIFIED",
            "Firmware/profile hoặc danh tính sensor chưa được xác minh.",
        )
    return telemetry


def wait_for_persisted_device_sample(
    client: httpx.Client, device_id: str, timeout_seconds: float,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/devices/{device_id}/telemetry")
        if response.status_code == 200:
            sample = response.json()
            capabilities = request_json(client, "GET", "/api/diagnosis/capabilities")
            if (sample.get("quality", {}).get("source") == "device"
                    and sample.get("device_id") == device_id
                    and capabilities.get("serial_history_status") == "receiving"):
                return sample
        time.sleep(0.5)
    raise AcceptanceError(
        "SERIAL_HISTORY_TIMEOUT",
        "Backend chưa lưu được telemetry device; kiểm tra bind, COM và firmware read-only.",
    )


def check_frontend(client: httpx.Client, frontend_url: str) -> None:
    try:
        response = client.get(frontend_url + "/dashboard")
    except httpx.HTTPError as exc:
        raise AcceptanceError("FRONTEND_UNAVAILABLE", "Frontend chưa chạy ở cổng 5173.") from exc
    if response.status_code != 200 or 'id="root"' not in response.text:
        raise AcceptanceError("FRONTEND_INVALID", "Dashboard không tải được React shell.")


def check_live_websocket(base_url: str, frontend_url: str, timeout_seconds: float) -> dict:
    try:
        from websockets.sync.client import connect
    except ImportError as exc:
        raise AcceptanceError("WEBSOCKET_CLIENT_MISSING", "Thiếu dependency websockets.") from exc
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    url = f"{scheme}://{parsed.netloc}/api/v1/live/ws"
    try:
        with connect(url, origin=frontend_url, open_timeout=timeout_seconds,
                     close_timeout=2) as socket:
            payload = json.loads(socket.recv(timeout=timeout_seconds))
    except Exception as exc:
        raise AcceptanceError("WEBSOCKET_UNAVAILABLE", "WebSocket realtime không trả snapshot.") from exc
    telemetry = telemetry_from_live_message(payload)
    return telemetry


def telemetry_from_live_message(payload: object) -> dict:
    if (not isinstance(payload, dict) or payload.get("type") != "snapshot"
            or not isinstance(payload.get("data"), dict)):
        raise AcceptanceError("WEBSOCKET_INVALID", "WebSocket không trả snapshot hợp lệ.")
    telemetry = payload["data"].get("telemetry")
    if not isinstance(telemetry, dict) or telemetry.get("quality", {}).get("source") != "device":
        raise AcceptanceError("WEBSOCKET_NOT_DEVICE", "WebSocket không mang telemetry device thật.")
    return telemetry


def validate_live_run(session: object, run_number: int) -> dict:
    if not isinstance(session, dict) or not isinstance(session.get("result"), dict):
        raise AcceptanceError("DIAGNOSIS_INVALID", f"Lần {run_number}: thiếu diagnosis result.")
    result = session["result"]
    plan = result.get("plan")
    observations = result.get("observations")
    runtime = result.get("model_runtime")
    calls = runtime.get("calls") if isinstance(runtime, dict) else None
    if not isinstance(observations, list):
        raise AcceptanceError("DIAGNOSIS_INVALID", f"Lần {run_number}: observations sai.")
    read = next((item for item in observations
                 if isinstance(item, dict)
                 if item.get("tool_name") == "get_telemetry"
                 and item.get("status") == "succeeded"
                 and item.get("source") == "device"), None)
    if result.get("mode") != "live" or result.get("source") != "device":
        raise AcceptanceError("DIAGNOSIS_NOT_LIVE_DEVICE", f"Lần {run_number}: sai mode/source.")
    if result.get("status") not in {"diagnosed", "needs_manual"}:
        raise AcceptanceError("DIAGNOSIS_NOT_COMPLETE", f"Lần {run_number}: model chưa kết luận.")
    if (not isinstance(plan, dict) or not isinstance(plan.get("hypotheses"), list)
            or not plan["hypotheses"]):
        raise AcceptanceError("HYPOTHESIS_MISSING", f"Lần {run_number}: Nemotron chưa tạo hypothesis.")
    if read is None or read.get("data", {}).get("scope") != "serial_read":
        raise AcceptanceError("READ_TOOL_MISSING", f"Lần {run_number}: thiếu get_telemetry thật.")
    events = result.get("events")
    if not isinstance(events, list):
        raise AcceptanceError("DIAGNOSIS_INVALID", f"Lần {run_number}: events sai.")
    executed = [event for event in events if isinstance(event, dict)
                if event.get("event_type") == "action.executed"
                and event.get("related_tool_call_id") == read.get("tool_call_id")]
    if not executed:
        raise AcceptanceError("READ_TOOL_EVENT_MISSING", f"Lần {run_number}: thiếu audit tool.")
    if (not isinstance(runtime, dict) or runtime.get("provider") != "nebius"
            or not isinstance(calls, list) or not calls):
        raise AcceptanceError("MODEL_CALL_EVIDENCE_MISSING", f"Lần {run_number}: thiếu model-call proof.")
    if any(call.get("finish_reason") != "stop" or not call.get("requested_model") for call in calls):
        raise AcceptanceError("MODEL_CALL_EVIDENCE_INVALID", f"Lần {run_number}: model-call chưa hoàn tất.")
    return {
        "run": run_number,
        "session_id": session.get("session_id"),
        "trace_id": result.get("trace_id"),
        "status": result.get("status"),
        "hypotheses": [{
            "id": item.get("id"), "confidence": item.get("confidence"),
            "evidence_ids": item.get("evidence_ids", []),
        } for item in plan["hypotheses"]],
        "read_tool": {"tool_name": "get_telemetry", "tool_call_id": read.get("tool_call_id")},
        "model_runtime": runtime,
        "physical_commands_enabled": result.get("physical_commands_enabled"),
        "physical_operation_verified": result.get("physical_operation_verified"),
    }


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--wait-seconds", type=float, default=20)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/U07/nexus-u07-vertical-slice.json"))
    args = parser.parse_args(argv)
    try:
        args.base_url = checked_url(args.base_url, "base-url")
        args.frontend_url = checked_url(args.frontend_url, "frontend-url")
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    report = {"task": "U07", "started_at": utc_now(), "passed": False, "runs": []}
    try:
        with httpx.Client(base_url=args.base_url, timeout=60) as backend:
            capabilities = request_json(backend, "GET", "/api/diagnosis/capabilities")
            snapshot = request_json(backend, "GET", "/api/v1/live")
            hardware_model = request_json(backend, "GET", "/api/v1/hardware-model")
            telemetry = require_runtime_preflight(capabilities, snapshot, hardware_model)
            device_id = telemetry["device_id"]
            if args.preflight_only:
                report.update(passed=True, preflight_only=True, telemetry={
                    "device_id": telemetry["device_id"],
                    "sample_id": telemetry["sample_id"],
                    "sequence": telemetry["sequence"],
                    "source": telemetry["quality"]["source"],
                })
            else:
                stored = wait_for_persisted_device_sample(
                    backend, device_id, args.wait_seconds,
                )
                with httpx.Client(timeout=10) as browser:
                    check_frontend(browser, args.frontend_url)
                streamed = check_live_websocket(args.base_url, args.frontend_url, args.wait_seconds)
                for run_number in range(1, args.runs + 1):
                    session = request_json(backend, "POST", f"/api/devices/{device_id}/diagnoses",
                                           json={
                                               "mode": "live", "max_steps": 6,
                                               "require_fresh_read": True,
                                               "symptom": (
                                                   "Motor demo needs a current health hypothesis. "
                                                   "Read fresh telemetry exactly once with "
                                                   "get_telemetry. After that successful read, "
                                                   "immediately conclude with diagnosed or "
                                                   "needs_manual; do not request another tool or "
                                                   "any physical write."
                                               ),
                                           })
                    report["runs"].append(validate_live_run(session, run_number))
                report.update(passed=len(report["runs"]) == args.runs,
                              required_runs=args.runs, frontend_dashboard=True,
                              websocket_device_sample=streamed["sample_id"],
                              persisted_device_sample=stored["sample_id"],
                              device_id=device_id,
                              hardware_model_id=hardware_model["hardware_model_id"],
                              physical_commands_enabled=False)
    except AcceptanceError as exc:
        report.update(error_code=exc.code, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - keep provider and local details out of output
        report.update(error_code="U07_RUNNER_FAILED", error=f"Runner lỗi {type(exc).__name__}.")
    report["completed_at"] = utc_now()
    write_report(args.output, report)
    print(json.dumps({
        "task": "U07", "passed": report["passed"],
        "runs": len(report["runs"]), "required_runs": args.runs,
        "error_code": report.get("error_code"), "error": report.get("error"),
        "report": str(args.output),
    }, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
