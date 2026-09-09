"""Durable device, telemetry, session, and audit storage for the local backend."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

MAX_QUERY_RESULTS = 1000


class StoreNotFound(Exception):
    """The requested resource does not exist for this device."""


class StoreConflict(Exception):
    """A request conflicts with registered configuration or persisted data."""


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_QUERY_RESULTS:
        raise ValueError(f"limit must be an integer between 1 and {MAX_QUERY_RESULTS}")
    return value


class SQLiteStore:
    """Serialize connection access and commit telemetry with its audit event atomically.

    Payload contracts are validated by the API. The store additionally enforces
    identity, source, retry, and device-isolation rules at the persistence boundary.
    History is ordered by insertion, because device clocks and sequence counters
    can reset. Collection reads are bounded to at most ``MAX_QUERY_RESULTS``.
    """

    def __init__(self, path: str | Path) -> None:
        database = str(path)
        if database != ":memory:":
            database = str(Path(path).expanduser())
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(database, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        with self._lock, self._connection:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    hardware_model_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    hardware_model_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS telemetry (
                    insertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    sample_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(device_id, sample_id)
                );
                CREATE INDEX IF NOT EXISTS telemetry_device_order
                    ON telemetry(device_id, insertion_id);
                CREATE TABLE IF NOT EXISTS events (
                    insertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    telemetry_id INTEGER NOT NULL UNIQUE REFERENCES telemetry(insertion_id),
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_device_order
                    ON events(device_id, insertion_id);
                CREATE TABLE IF NOT EXISTS sessions (
                    insertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_device_order
                    ON sessions(device_id, insertion_id);
                CREATE TABLE IF NOT EXISTS diagnosis_events (
                    insertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS diagnosis_events_device_order
                    ON diagnosis_events(device_id, insertion_id);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _device_row(self, device_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if row is None:
            raise StoreNotFound("Device not found")
        return row

    @staticmethod
    def _device_dict(row: sqlite3.Row) -> dict:
        return {
            key: row[key]
            for key in (
                "device_id", "hardware_model_id", "display_name", "source", "registered_at"
            )
        }

    def register_device(
        self, hardware_model: dict, display_name: str, source: str
    ) -> dict:
        model_json = _json(hardware_model)
        device_id = hardware_model["device_id"]
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            existing = self._connection.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["hardware_model_json"] != model_json
                    or existing["display_name"] != display_name
                    or existing["source"] != source
                ):
                    raise StoreConflict("Device is already registered with different configuration")
                return self._device_dict(existing)
            self._connection.execute(
                """INSERT INTO devices
                   (device_id, hardware_model_id, display_name, source,
                    registered_at, hardware_model_json) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    device_id, hardware_model["hardware_model_id"], display_name,
                    source, _timestamp(), model_json,
                ),
            )
            return self._device_dict(self._device_row(device_id))

    def get_device(self, device_id: str) -> dict:
        with self._lock:
            return self._device_dict(self._device_row(device_id))

    def list_devices(self) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM devices ORDER BY rowid LIMIT ?", (MAX_QUERY_RESULTS,)
            ).fetchall()
            return [self._device_dict(row) for row in rows]

    def get_hardware_model(self, device_id: str) -> dict:
        with self._lock:
            return json.loads(self._device_row(device_id)["hardware_model_json"])

    def append_telemetry(self, payload: dict) -> tuple[dict, dict, bool]:
        body_json = _json(payload)
        device_id = payload["device_id"]
        sample_id = payload["sample_id"]
        source = payload["quality"]["source"]
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            device = self._device_row(device_id)
            if payload["hardware_model_id"] != device["hardware_model_id"]:
                raise StoreConflict("Telemetry hardware model does not match the registered device")
            if source != device["source"]:
                raise StoreConflict("Telemetry source does not match the registered device")
            existing = self._connection.execute(
                "SELECT * FROM telemetry WHERE device_id = ? AND sample_id = ?",
                (device_id, sample_id),
            ).fetchone()
            if existing is not None:
                if existing["payload_json"] != body_json:
                    raise StoreConflict("Sample ID is already associated with different telemetry")
                event = self._connection.execute(
                    "SELECT payload_json FROM events WHERE telemetry_id = ?",
                    (existing["insertion_id"],),
                ).fetchone()
                if event is None:
                    raise StoreConflict("Persisted telemetry has no matching audit event")
                return json.loads(body_json), json.loads(event["payload_json"]), False

            cursor = self._connection.execute(
                "INSERT INTO telemetry (device_id, sample_id, payload_json) VALUES (?, ?, ?)",
                (device_id, sample_id, body_json),
            )
            event = {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "trace_id": str(uuid4()),
                "device_id": device_id,
                "event_type": "telemetry.received",
                "occurred_at": _timestamp(),
                "source": "backend",
                "severity": "info",
                "summary": f"Telemetry received from {source}.",
                "payload": {"sample_id": sample_id, "source": source},
                "related_tool_call_id": None,
            }
            self._connection.execute(
                """INSERT INTO events (event_id, device_id, telemetry_id, payload_json)
                   VALUES (?, ?, ?, ?)""",
                (event["event_id"], device_id, cursor.lastrowid, _json(event)),
            )
            return json.loads(body_json), event, True

    def latest_telemetry(self, device_id: str) -> dict | None:
        record = self.latest_telemetry_record(device_id)
        return record[1] if record is not None else None

    def latest_telemetry_record(self, device_id: str) -> tuple[int, dict] | None:
        """Return the newest committed sample and its durable receive cursor."""
        with self._lock:
            self._device_row(device_id)
            row = self._connection.execute(
                """SELECT insertion_id, payload_json FROM telemetry WHERE device_id = ?
                   ORDER BY insertion_id DESC LIMIT 1""",
                (device_id,),
            ).fetchone()
            if row is None:
                return None
            return row["insertion_id"], json.loads(row["payload_json"])

    def telemetry_after(
        self, device_id: str, after_cursor: int, limit: int = 100
    ) -> list[tuple[int, dict]]:
        """Read the next bounded batch without skipping intermediate samples."""
        limit = _limit(limit)
        if (
            isinstance(after_cursor, bool)
            or not isinstance(after_cursor, int)
            or after_cursor < 0
        ):
            raise ValueError("after_cursor must be a nonnegative integer")
        with self._lock:
            self._device_row(device_id)
            rows = self._connection.execute(
                """SELECT insertion_id, payload_json FROM telemetry
                   WHERE device_id = ? AND insertion_id > ?
                   ORDER BY insertion_id ASC LIMIT ?""",
                (device_id, after_cursor, limit),
            ).fetchall()
            return [(row["insertion_id"], json.loads(row["payload_json"])) for row in rows]

    def telemetry_history(self, device_id: str, limit: int = 20) -> list[dict]:
        limit = _limit(limit)
        with self._lock:
            self._device_row(device_id)
            rows = self._connection.execute(
                """SELECT payload_json FROM telemetry WHERE device_id = ?
                   ORDER BY insertion_id DESC LIMIT ?""",
                (device_id, limit),
            ).fetchall()
            return [json.loads(row["payload_json"]) for row in reversed(rows)]

    def create_session(self, device_id: str, symptom: str) -> dict:
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            self._device_row(device_id)
            session = {
                "session_id": str(uuid4()),
                "trace_id": str(uuid4()),
                "device_id": device_id,
                "symptom": symptom,
                "status": "created",
                "created_at": _timestamp(),
            }
            self._connection.execute(
                "INSERT INTO sessions (session_id, device_id, payload_json) VALUES (?, ?, ?)",
                (session["session_id"], device_id, _json(session)),
            )
            return session

    def get_session(self, device_id: str, session_id: str) -> dict:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM sessions WHERE device_id = ? AND session_id = ?",
                (device_id, session_id),
            ).fetchone()
            if row is None:
                raise StoreNotFound("Session not found for this device")
            return json.loads(row["payload_json"])

    def session(self, device_id: str, session_id: str) -> dict:
        """Alias for callers that use the shorter session lookup name."""
        return self.get_session(device_id, session_id)

    def finish_diagnosis(self, device_id: str, session_id: str, result: dict) -> dict:
        """Persist one bounded run and its canonical events atomically under its device."""
        from .validation import validate_contract

        if not isinstance(result, dict) or not isinstance(result.get("events"), list):
            raise StoreConflict("A diagnosis result with events is required")
        if len(result["events"]) > 500:
            raise StoreConflict("Too many diagnosis events")
        events = [validate_contract("event", event) for event in result["events"]]
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            session = self.get_session(device_id, session_id)
            if session["status"] != "created":
                raise StoreConflict("Diagnosis session already has a result")
            if result.get("trace_id") != session["trace_id"]:
                raise StoreConflict("Diagnosis trace does not match the session")
            if any(event["device_id"] != device_id or event["trace_id"] != session["trace_id"]
                   for event in events):
                raise StoreConflict("Diagnosis event belongs to another device or trace")
            if len({event["event_id"] for event in events}) != len(events):
                raise StoreConflict("Duplicate diagnosis event IDs")
            session.update(status=result["status"], completed_at=_timestamp(), result=result)
            self._connection.execute(
                "UPDATE sessions SET payload_json = ? WHERE device_id = ? AND session_id = ?",
                (_json(session), device_id, session_id),
            )
            for event in events:
                self._connection.execute(
                    "INSERT INTO diagnosis_events (event_id, device_id, session_id, payload_json) "
                    "VALUES (?, ?, ?, ?)",
                    (event["event_id"], device_id, session_id, _json(event)),
                )
            return json.loads(_json(session))

    def diagnosis_events(self, device_id: str, session_id: str) -> list[dict]:
        with self._lock:
            self.get_session(device_id, session_id)
            rows = self._connection.execute(
                "SELECT payload_json FROM diagnosis_events WHERE device_id = ? "
                "AND session_id = ? ORDER BY insertion_id LIMIT 500", (device_id, session_id),
            ).fetchall()
            return [json.loads(row["payload_json"]) for row in rows]

    def list_sessions(self, device_id: str, limit: int = 50) -> list[dict]:
        limit = _limit(limit)
        with self._lock:
            self._device_row(device_id)
            rows = self._connection.execute(
                """SELECT payload_json FROM sessions WHERE device_id = ?
                   ORDER BY insertion_id DESC LIMIT ?""",
                (device_id, limit),
            ).fetchall()
            return [json.loads(row["payload_json"]) for row in reversed(rows)]

    def list_events(self, device_id: str, limit: int = 100) -> list[dict]:
        limit = _limit(limit)
        with self._lock:
            self._device_row(device_id)
            rows = self._connection.execute(
                """SELECT payload_json FROM events WHERE device_id = ?
                   ORDER BY insertion_id DESC LIMIT ?""",
                (device_id, limit),
            ).fetchall()
            telemetry_events = [json.loads(row["payload_json"]) for row in reversed(rows)]
            diagnosis_rows = self._connection.execute(
                "SELECT payload_json FROM diagnosis_events WHERE device_id = ? "
                "ORDER BY insertion_id DESC LIMIT ?", (device_id, limit),
            ).fetchall()
            if not diagnosis_rows:
                return telemetry_events
            combined = telemetry_events + [
                json.loads(row["payload_json"]) for row in reversed(diagnosis_rows)
            ]
            return sorted(combined, key=lambda event: event["occurred_at"])[-limit:]
