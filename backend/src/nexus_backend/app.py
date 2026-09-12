"""Local MVP APIs for device data, diagnosis sessions, and hardware context."""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.websockets import WebSocketDisconnect

from nexus_backend import __version__
from nexus_backend.context import build_context
from nexus_backend.hardware import load_hardware_model
from nexus_backend.health_check import run_health_check
from nexus_backend.runtime import RunLimiter, configure_logging, log_run
from nexus_backend.serial_bridge import SerialBridge
from nexus_backend.store import SQLiteStore, StoreConflict, StoreNotFound
from nexus_backend.validation import ContractValidationError, validate_contract


class LiveHub:
    """Fan out a single application's snapshots on its own event loop."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=2)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, snapshot: dict[str, object]) -> None:
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(snapshot)


def _allowed_websocket_origin(websocket: WebSocket, origins: list[str]) -> bool:
    origin = websocket.headers.get("origin")
    scheme = "https" if websocket.url.scheme == "wss" else "http"
    same_origin = f"{scheme}://{websocket.url.netloc}"
    return origin is None or origin in [same_origin, *origins]


class APIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def valid_text(cls, value):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as error:
                raise ValueError("Text must be valid UTF-8") from error
        return value


class RegisterDevice(APIRequest):
    hardware_model: dict = Field(description="Complete frozen hardware-model v1 document.")
    display_name: str = Field(min_length=1, max_length=120)
    source: Literal["device", "simulator", "replay"]


class NewSession(APIRequest):
    symptom: str = Field(min_length=1, max_length=2000)

    @field_validator("symptom")
    @classmethod
    def nonblank_symptom(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A symptom is required")
        return value


class ContextRequest(NewSession):
    max_samples: int = Field(default=10, ge=1, le=20, strict=True)


class DiagnosisRequest(NewSession):
    mode: Literal["mock", "live"] = "mock"
    max_steps: int = Field(default=6, ge=1, le=8, strict=True)
    require_fresh_read: bool = Field(default=False, strict=True)


class HealthCheckRequest(APIRequest):
    hardware_model: dict = Field(description="Complete frozen hardware-model v1 document.")
    profile: dict = Field(default_factory=dict, description="Optional declared electrical evidence.")


def create_app(
    db_path: str | Path | None = None, *, serial_enabled: bool | None = False,
    bridge: SerialBridge | None = None, serial_device_id: str | None = None,
) -> FastAPI:
    """Create isolated state; factory calls disable hardware access unless requested.

    The exported server app passes None to preserve environment-controlled serial
    startup. Tests can supply a disabled/instrumented bridge without accessing USB.
    """
    serial_bridge = bridge if bridge is not None else SerialBridge(enabled=serial_enabled)
    live_hub = LiveHub()
    bound_device_id = serial_device_id
    if bound_device_id is None and serial_enabled is None:
        bound_device_id = os.getenv("NEXUS_SERIAL_DEVICE_ID", "").strip() or None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging()
        database = db_path if db_path is not None else os.getenv(
            "NEXUS_DB_PATH", "artifacts/nexus.sqlite3"
        )
        application.state.store = SQLiteStore(database)
        application.state.run_limiter = RunLimiter()
        application.state.serial_history = None
        loop = asyncio.get_running_loop()
        publishing = True

        def publish_from_thread(snapshot: dict[str, object]) -> None:
            if publishing:
                loop.call_soon_threadsafe(live_hub.publish, snapshot)

        try:
            if bound_device_id is not None:
                from nexus_backend.serial_history import SerialHistory

                history = SerialHistory(application.state.store, bound_device_id)
                application.state.serial_history = history
                serial_bridge.set_sample_sink(history.ingest)
            serial_bridge.set_sink(publish_from_thread)
            serial_bridge.start()
            yield
        finally:
            publishing = False
            # Detach first so a bridge finishing a read cannot publish after shutdown.
            try:
                serial_bridge.set_sink(None)
                serial_bridge.set_sample_sink(None)
            finally:
                try:
                    await asyncio.to_thread(serial_bridge.stop)
                finally:
                    application.state.store.close()

    application = FastAPI(title="nexus-backend", version=__version__, lifespan=lifespan)
    application.state.serial_bridge = serial_bridge
    application.state.live_hub = live_hub
    origins = [
        value.strip() for value in os.getenv(
            "NEXUS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",") if value.strip()
    ]
    application.add_middleware(
        CORSMiddleware, allow_origins=origins,
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )

    @application.exception_handler(StoreNotFound)
    async def not_found(_request: Request, error: StoreNotFound):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @application.exception_handler(StoreConflict)
    async def conflict(_request: Request, error: StoreConflict):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(ContractValidationError)
    async def invalid_contract(_request: Request, error: ContractValidationError):
        return JSONResponse(status_code=422, content={"detail": error.errors})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError):
        # Do not echo raw input; malformed Unicode must still produce a valid response.
        detail = [{
            "loc": [
                part.encode("utf-8", errors="replace").decode("utf-8")
                if isinstance(part, str) else part for part in item["loc"]
            ],
            "msg": item["msg"].encode("utf-8", errors="replace").decode("utf-8"),
            "type": item["type"],
        } for item in error.errors()[:20]]
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.get("/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "nexus-backend", "version": __version__}

    @application.get("/monitor", response_class=HTMLResponse, include_in_schema=False)
    def monitor() -> str:
        return files("nexus_backend").joinpath("static/monitor.html").read_text("utf-8")

    @application.get("/doctor-lab", response_class=HTMLResponse, include_in_schema=False)
    def doctor_lab() -> str:
        return files("nexus_backend").joinpath("static/doctor-lab.html").read_text("utf-8")

    @application.get("/api/diagnosis/capabilities", tags=["Diagnosis"])
    def diagnosis_capabilities() -> dict:
        history = getattr(application.state, "serial_history", None)
        return {
            "mock_available": True,
            "live_enabled": os.getenv("NEXUS_ENABLE_LIVE_MODEL", "false").lower() == "true",
            "live_configured": all(os.getenv(key, "").strip() for key in (
                "NEXUS_NEBIUS_BASE_URL", "NEXUS_NEBIUS_API_KEY", "NEXUS_NVIDIA_MODEL",
            )),
            "physical_commands_enabled": False,
            "serial_reads_enabled": history is not None,
            "serial_device_id": bound_device_id,
            "serial_history_status": history.status if history is not None else "disabled",
        }

    @application.post("/api/devices/{device_id}/diagnoses", tags=["Diagnosis"])
    async def diagnose(device_id: str, body: DiagnosisRequest, request: Request) -> dict:
        from nexus_backend.diagnosis import MockPlanner, NebiusPlanner
        from nexus_backend.orchestrator import run_diagnosis
        from nexus_backend.provider import ProviderError

        store = request.app.state.store
        device = store.get_device(device_id)
        if body.mode == "mock" and device["source"] != "simulator":
            raise HTTPException(409, "Simulation requires a device registered as simulator")
        if body.mode == "live":
            capability = diagnosis_capabilities()
            if not capability["live_enabled"] or not capability["live_configured"]:
                raise HTTPException(503, "Live model access is not enabled and configured")
            try:
                planner = NebiusPlanner.from_env()
            except (ValueError, RuntimeError, ProviderError):
                raise HTTPException(503, "Live model configuration is invalid") from None
        else:
            planner = MockPlanner()
        context = build_context(store.get_hardware_model(device_id),
                                store.telemetry_history(device_id, 10), body.symptom)
        adapter = None
        history = request.app.state.serial_history
        if (body.mode == "live" and device["source"] == "device"
                and history is not None and history.device_id == device_id):
            from nexus_backend.tool_adapter import SerialToolAdapter

            adapter = SerialToolAdapter(context, reads=serial_bridge.reads, history=history)
        run_context = context
        if body.require_fresh_read:
            if body.mode != "live" or adapter is None:
                raise HTTPException(
                    409,
                    "A fresh read requires live mode and a source=device serial binding",
                )
            run_context = deepcopy(context)
            run_context["telemetry"] = []
        denied = request.app.state.run_limiter.acquire()
        if denied:
            raise HTTPException(429 if denied == "rate_limited" else 503,
                                "Diagnosis request limit reached; retry shortly",
                                headers={"Retry-After": "60" if denied == "rate_limited" else "5"})
        started = time.monotonic()
        session = None
        try:
            session = store.create_session(device_id, body.symptom)
            try:
                result = await asyncio.wait_for(run_diagnosis(
                    run_context, planner, mode="mock" if body.mode == "mock" else "real",
                    adapter=adapter,
                    max_steps=body.max_steps,
                    timeout_seconds=25, trace_id=session["trace_id"],
                ), timeout=30)
            except Exception:  # noqa: BLE001 - contain external provider failures without payload leaks
                # Provider exceptions can contain request URLs/bodies. Return and log no raw error.
                result = {
                    "trace_id": session["trace_id"], "mode": body.mode,
                    "status": "error", "plan": None, "steps": 0, "observations": [],
                    "events": [{
                        "schema_version": "1.0.0", "event_id": str(uuid4()),
                        "trace_id": session["trace_id"], "device_id": device_id,
                        "event_type": "diagnosis.proposed",
                        "occurred_at": datetime.now(UTC).isoformat(), "source": "backend",
                        "severity": "error", "summary": "Diagnosis failed; retry is available",
                        "payload": {"stage": "failed", "mode": body.mode},
                        "related_tool_call_id": None,
                    }],
                    "user_message": "Diagnosis is unavailable. Check configuration and retry.",
                }
            result["mode"] = body.mode
            result["physical_commands_enabled"] = False
            finished = store.finish_diagnosis(device_id, session["session_id"], result)
            calls = result.get("model_runtime", {}).get("calls", [])
            model = None
            if calls:
                model = calls[-1].get("response_model") or calls[-1].get("requested_model")
            log_run(trace_id=session["trace_id"], mode=body.mode, status=result["status"],
                    steps=result.get("steps", 0), elapsed_ms=int((time.monotonic()-started)*1000),
                    model_calls=len(calls), model=model)
            return finished
        finally:
            request.app.state.run_limiter.release()

    @application.get("/api/devices/{device_id}/sessions/{session_id}/events", tags=["Diagnosis"])
    def diagnosis_events(device_id: str, session_id: str, request: Request) -> list[dict]:
        return request.app.state.store.diagnosis_events(device_id, session_id)

    @application.get("/api/v1/live", tags=["Live hardware"])
    def live_snapshot() -> dict[str, object]:
        """Read the serial bridge without replacing persistent per-device APIs."""
        return serial_bridge.snapshot()

    @application.get("/api/v1/hardware-profile", tags=["Live hardware"])
    def active_hardware_profile() -> dict:
        """Expose the validated machine-readable BOM selected by this backend."""
        return deepcopy(serial_bridge.hardware_profile)

    @application.get("/api/v1/telemetry", tags=["Live hardware"])
    def live_telemetry() -> dict[str, object]:
        telemetry = serial_bridge.snapshot()["telemetry"]
        if telemetry is None:
            raise HTTPException(404, "Chưa nhận được telemetry hợp lệ từ ESP32.")
        return telemetry

    @application.get("/api/v1/logs", tags=["Live hardware"])
    def recent_logs(limit: int = 100) -> list[dict[str, object]]:
        return serial_bridge.snapshot()["logs"][-max(1, min(limit, 160)):]

    @application.get("/api/v1/diagnostics", tags=["Live hardware"])
    def live_diagnostics(active_only: bool = True) -> list[dict[str, object]]:
        items = serial_bridge.snapshot()["diagnostics"]
        return [item for item in items if item["active"]] if active_only else items

    @application.websocket("/api/v1/live/ws")
    async def live_websocket(websocket: WebSocket) -> None:
        if not _allowed_websocket_origin(websocket, origins):
            await websocket.close(code=1008, reason="Origin is not allowed")
            return
        await websocket.accept()
        queue = live_hub.subscribe()

        async def receive_disconnect() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return

        disconnected = asyncio.create_task(receive_disconnect())
        next_snapshot = None
        try:
            await websocket.send_json({"type": "snapshot", "data": serial_bridge.snapshot()})
            while True:
                next_snapshot = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {disconnected, next_snapshot}, return_when=asyncio.FIRST_COMPLETED,
                )
                if disconnected in done:
                    break
                await websocket.send_json({"type": "snapshot", "data": next_snapshot.result()})
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            live_hub.unsubscribe(queue)
            disconnected.cancel()
            if next_snapshot is not None:
                next_snapshot.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.gather(
                    disconnected, *([next_snapshot] if next_snapshot is not None else []),
                    return_exceptions=True,
                )

    @application.post("/api/devices", status_code=201, tags=["Devices"])
    def register(body: RegisterDevice, request: Request) -> dict:
        model = load_hardware_model(body.hardware_model)
        return request.app.state.store.register_device(model, body.display_name, body.source)

    @application.get("/api/devices", tags=["Devices"])
    def devices(request: Request) -> list[dict]:
        return request.app.state.store.list_devices()

    @application.get("/api/devices/{device_id}", tags=["Devices"])
    def device(device_id: str, request: Request) -> dict:
        return request.app.state.store.get_device(device_id)

    @application.get("/api/devices/{device_id}/hardware-model", tags=["Hardware"])
    def hardware_model(device_id: str, request: Request) -> dict:
        return request.app.state.store.get_hardware_model(device_id)

    @application.post("/api/v1/health-check", tags=["Hardware"])
    def health_check(body: HealthCheckRequest) -> dict:
        """Run deterministic pre-power rules without accessing a physical board."""
        try:
            return run_health_check(body.hardware_model, body.profile)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.post("/api/devices/{device_id}/telemetry", status_code=201, tags=["Telemetry"])
    def ingest(device_id: str, sample: dict, request: Request, response: Response) -> dict:
        validated = validate_contract("telemetry", sample)
        if validated["device_id"] != device_id:
            raise HTTPException(409, "Telemetry device_id does not match the URL")
        stored, event, inserted = request.app.state.store.append_telemetry(validated)
        response.status_code = 201 if inserted else 200
        return {"sample": stored, "event_id": event["event_id"], "inserted": inserted}

    @application.get("/api/devices/{device_id}/telemetry", tags=["Telemetry"])
    def latest(device_id: str, request: Request) -> dict:
        sample = request.app.state.store.latest_telemetry(device_id)
        if sample is None:
            raise HTTPException(404, "No telemetry has been received for this device")
        return sample

    @application.get("/api/devices/{device_id}/telemetry/history", tags=["Telemetry"])
    def history(
        device_id: str, request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 20,
    ) -> list[dict]:
        return request.app.state.store.telemetry_history(device_id, limit)

    @application.post("/api/devices/{device_id}/sessions", status_code=201, tags=["Sessions"])
    def new_session(device_id: str, body: NewSession, request: Request) -> dict:
        # Session creation stores the symptom; it does not claim a model diagnosis.
        return request.app.state.store.create_session(device_id, body.symptom)

    @application.get("/api/devices/{device_id}/sessions", tags=["Sessions"])
    def sessions(
        device_id: str, request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[dict]:
        return request.app.state.store.list_sessions(device_id, limit)

    @application.get("/api/devices/{device_id}/sessions/{session_id}", tags=["Sessions"])
    def session(device_id: str, session_id: str, request: Request) -> dict:
        return request.app.state.store.get_session(device_id, session_id)

    @application.get("/api/devices/{device_id}/events", tags=["Audit"])
    def events(
        device_id: str, request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> list[dict]:
        return request.app.state.store.list_events(device_id, limit)

    @application.post("/api/devices/{device_id}/context", tags=["Hardware"])
    def context(device_id: str, body: ContextRequest, request: Request) -> dict:
        store = request.app.state.store
        return build_context(
            store.get_hardware_model(device_id),
            store.telemetry_history(device_id, body.max_samples),
            body.symptom, max_samples=body.max_samples,
        )

    @application.websocket("/api/devices/{device_id}/telemetry/stream")
    async def stream(websocket: WebSocket, device_id: str) -> None:
        """Send the latest sample, then every persisted sample in receive order."""
        if not _allowed_websocket_origin(websocket, origins):
            await websocket.close(code=1008, reason="Origin is not allowed")
            return
        store = websocket.app.state.store
        try:
            store.get_device(device_id)
        except StoreNotFound:
            await websocket.close(code=1008, reason="Unknown device")
            return
        await websocket.accept()
        try:
            record = store.latest_telemetry_record(device_id)
            cursor = 0
            if record is not None:
                cursor, sample = record
                await websocket.send_json({"type": "telemetry", "sample": sample})
            last_send = asyncio.get_running_loop().time()
            while True:
                # Receive lets a disconnected browser release resources immediately.
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=0.25)
                    if message["type"] == "websocket.disconnect":
                        break
                except TimeoutError:
                    pass
                records = store.telemetry_after(device_id, cursor, limit=100)
                for next_cursor, sample in records:
                    await websocket.send_json({"type": "telemetry", "sample": sample})
                    cursor = next_cursor
                    last_send = asyncio.get_running_loop().time()
                if asyncio.get_running_loop().time() - last_send >= 15:
                    await websocket.send_json({"type": "heartbeat"})
                    last_send = asyncio.get_running_loop().time()
        except WebSocketDisconnect:
            pass

    return application


app = create_app(serial_enabled=None)
