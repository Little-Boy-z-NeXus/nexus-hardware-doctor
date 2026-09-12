"""Serve sanitized telemetry replay through the same realtime API used by the frontend."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from pydantic import ValidationError

from nexus_backend.app import create_app
from nexus_backend.contracts import TelemetrySample
from nexus_backend.serial_bridge import EXPECTED_HARDWARE_MODEL_ID, SerialBridge


def default_replay_path() -> Path:
    packaged = Path(__file__).with_name("fixtures") / "telemetry-replay.example.ndjson"
    if packaged.is_file():
        return packaged
    return (
        Path(__file__).resolve().parents[3]
        / "nexus-contracts"
        / "v1"
        / "fixtures"
        / "telemetry-replay.example.ndjson"
    )


class ReplayError(RuntimeError):
    """A replay input is absent, malformed, or contains no usable telemetry."""


def _payload(record: object) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    if record.get("schema_version") == "1.0.0" and "measurements" in record:
        return deepcopy(record)
    if record.get("kind") != "serial" or not isinstance(record.get("value"), str):
        return None
    try:
        nested = json.loads(record["value"])
    except json.JSONDecodeError:
        return None
    return deepcopy(nested) if isinstance(nested, dict) else None


def load_replay(path: Path) -> list[dict[str, Any]]:
    """Extract valid telemetry from direct NDJSON or ignored U05 serial evidence."""
    if not path.is_file():
        raise ReplayError(f"Replay file does not exist: {path}")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ReplayError("Replay file exceeds the 50 MB local safety limit")
    samples: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReplayError(f"Invalid JSON on replay line {line_number}") from exc
        candidate = _payload(record)
        if candidate is None:
            continue
        try:
            checked = TelemetrySample.model_validate(candidate).model_dump(mode="json")
        except ValidationError:
            continue
        measurements = checked["measurements"]
        if not all(
            type(measurements[key]) in {int, float} and math.isfinite(measurements[key])
            for key in ("bus_voltage_v", "current_ma", "power_mw")
        ):
            continue
        if checked["hardware_model_id"] != EXPECTED_HARDWARE_MODEL_ID:
            continue
        samples.append(checked)
        if len(samples) >= 10_000:
            break
    if not samples:
        raise ReplayError("Replay contains no valid MVP telemetry frames")
    return samples


def sanitize_for_replay(sample: dict[str, Any], *, boot_id: str, sequence: int) -> dict[str, Any]:
    """Make replay provenance explicit and remove original device/session identifiers."""
    value = deepcopy(sample)
    value.update(
        device_id="nexus-replay-esp32",
        hardware_model_id=EXPECTED_HARDWARE_MODEL_ID,
        sample_id=f"nexus-replay-esp32-{boot_id}-{sequence}",
        sequence=sequence,
        recorded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    value["quality"]["source"] = "replay"
    return TelemetrySample.model_validate(value).model_dump(mode="json")


def publish_replay(bridge: SerialBridge, samples: Iterable[dict[str, Any]], *, interval: float,
                   repeat: bool = True, stop: threading.Event | None = None) -> int:
    """Publish a bounded source list until stopped, preserving the live API shape."""
    source = list(samples)
    if not source:
        raise ReplayError("At least one telemetry frame is required")
    stop_event = stop or threading.Event()
    boot_id = uuid4().hex[:12]
    sequence = 0
    while not stop_event.is_set():
        for sample in source:
            if stop_event.is_set():
                return sequence
            replay = sanitize_for_replay(sample, boot_id=boot_id, sequence=sequence)
            bridge.ingest_line(
                json.dumps(replay, separators=(",", ":"), ensure_ascii=True),
                port="telemetry-replay",
                source="replay",
            )
            sequence += 1
            if stop_event.wait(interval):
                return sequence
        if not repeat:
            return sequence
    return sequence


def interval_argument(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be numeric") from exc
    if not math.isfinite(result) or not 0.1 <= result <= 60:
        raise argparse.ArgumentTypeError("interval must be between 0.1 and 60 seconds")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=default_replay_path())
    parser.add_argument("--interval", type=interval_argument, default=1.0)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8000, choices=range(1024, 65536))
    args = parser.parse_args(argv)
    try:
        samples = load_replay(args.input)
    except (OSError, ReplayError) as exc:
        print(f"[NEXUS][ERROR][REPLAY_INPUT_INVALID] {exc}")
        return 1

    bridge = SerialBridge(enabled=False, persist_logs=False)
    app = create_app("artifacts/nexus-replay.sqlite3", bridge=bridge, serial_enabled=False)
    stop = threading.Event()

    def worker() -> None:
        time.sleep(1.0)
        publish_replay(bridge, samples, interval=args.interval, stop=stop)

    thread = threading.Thread(target=worker, name="nexus-telemetry-replay", daemon=True)
    thread.start()
    print(
        f"[NEXUS][REPLAY] {len(samples)} sanitized frames -> "
        f"http://{args.host}:{args.port}/api/v1/live/ws"
    )
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        stop.set()
        thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
