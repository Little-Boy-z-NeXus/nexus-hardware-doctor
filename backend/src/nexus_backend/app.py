"""Local MVP APIs for device data, diagnosis sessions, and hardware context."""
"""API entry point for the NeXus hardware-doctor MVP."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.websockets import WebSocketDisconnect

from nexus_backend import __version__
from nexus_backend.context import build_context
from nexus_backend.hardware import load_hardware_model
from nexus_backend.store import SQLiteStore, StoreConflict, StoreNotFound
from nexus_backend.validation import ContractValidationError, validate_contract


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


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Create an isolated application; open the database only during lifespan."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = db_path if db_path is not None else os.getenv(
            "NEXUS_DB_PATH", "artifacts/nexus.sqlite3"
        )
        application.state.store = SQLiteStore(database)
        try:
            yield
        finally:
            application.state.store.close()

    application = FastAPI(title="nexus-backend", version=__version__, lifespan=lifespan)
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
        origin = websocket.headers.get("origin")
        scheme = "https" if websocket.url.scheme == "wss" else "http"
        same_origin = f"{scheme}://{websocket.url.netloc}"
        if origin is not None and origin not in [same_origin, *origins]:
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


app = create_app()
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from nexus_backend import __version__
from nexus_backend.serial_bridge import SerialBridge


class LiveHub:
    """Fan the newest bridge snapshot out to browser WebSocket clients."""

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


live_hub = LiveHub()
serial_bridge = SerialBridge()


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop = asyncio.get_running_loop()

    def publish_from_thread(snapshot: dict[str, object]) -> None:
        loop.call_soon_threadsafe(live_hub.publish, snapshot)

    serial_bridge.set_sink(publish_from_thread)
    serial_bridge.start()
    yield
    serial_bridge.stop()
    serial_bridge.set_sink(None)


app = FastAPI(title="nexus-backend", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free process health signal."""
    return {"status": "ok", "service": "nexus-backend", "version": __version__}


@app.get("/api/v1/live")
def live_snapshot() -> dict[str, object]:
    """Return connection, telemetry, diagnostics, logs, and the fixed MVP BOM."""
    return serial_bridge.snapshot()


@app.get("/api/v1/telemetry")
def latest_telemetry() -> dict[str, object]:
    """Return the latest valid device packet without inventing presentation data."""
    telemetry = serial_bridge.snapshot()["telemetry"]
    if telemetry is None:
        raise HTTPException(status_code=404, detail="Chưa nhận được telemetry hợp lệ từ ESP32.")
    return telemetry


@app.get("/api/v1/logs")
def recent_logs(limit: int = 100) -> list[dict[str, object]]:
    """Return recent firmware and bridge lines for debugging without a CLI."""
    safe_limit = max(1, min(limit, 160))
    return serial_bridge.snapshot()["logs"][-safe_limit:]


@app.get("/api/v1/diagnostics")
def diagnostics(active_only: bool = True) -> list[dict[str, object]]:
    """Return human-readable deterministic hardware findings."""
    items = serial_bridge.snapshot()["diagnostics"]
    if active_only:
        return [item for item in items if item["active"]]
    return items


@app.websocket("/api/v1/live/ws")
async def live_websocket(websocket: WebSocket) -> None:
    """Stream complete snapshots so reconnecting UIs always converge."""
    await websocket.accept()
    queue = live_hub.subscribe()
    try:
        await websocket.send_json({"type": "snapshot", "data": serial_bridge.snapshot()})
        while True:
            snapshot = await queue.get()
            await websocket.send_json({"type": "snapshot", "data": snapshot})
    except WebSocketDisconnect:
        pass
    finally:
        live_hub.unsubscribe(queue)
