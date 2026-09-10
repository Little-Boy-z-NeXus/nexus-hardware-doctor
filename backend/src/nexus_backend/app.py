"""API entry point for the NeXus hardware-doctor MVP."""

from __future__ import annotations

import asyncio
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
