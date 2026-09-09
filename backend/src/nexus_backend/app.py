"""Local MVP APIs for device data, diagnosis sessions, and hardware context."""

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
