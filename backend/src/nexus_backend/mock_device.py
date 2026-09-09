"""Send explicitly simulated v1 telemetry to a running NeXus backend."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
from pydantic import ValidationError

from nexus_backend.contracts import HardwareModel, TelemetrySample


def fixture_directory() -> Path:
    """Support both a wheel installation and an editable repository checkout."""
    packaged = Path(__file__).parent / "fixtures"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[3] / "nexus-contracts" / "v1" / "fixtures"


def load_fixtures(directory: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = directory if directory is not None else fixture_directory()
    model = json.loads((directory / "hardware-model.example.json").read_text(encoding="utf-8"))
    telemetry = json.loads((directory / "telemetry.example.json").read_text(encoding="utf-8"))
    HardwareModel.model_validate(model)
    TelemetrySample.model_validate(telemetry)
    return model, telemetry


def make_sample(
    template: dict[str, Any],
    model: dict[str, Any],
    *,
    boot_id: str,
    sequence: int,
) -> dict[str, Any]:
    """Vary fixture readings reproducibly; never imply physical measurements."""
    sample = copy.deepcopy(template)
    sample.update(
        device_id=model["device_id"],
        hardware_model_id=model["hardware_model_id"],
        sample_id=f"{model['device_id']}-{boot_id}-{sequence}",
        recorded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        sequence=sequence,
    )
    sample["quality"]["source"] = "simulator"
    measurements = sample["measurements"]
    offset = (sequence % 9) - 4
    measurements["bus_voltage_v"] = round(max(0, measurements["bus_voltage_v"] + offset * 0.01), 2)
    measurements["current_ma"] = round(measurements["current_ma"] + offset * 3, 2)
    measurements["power_mw"] = round(
        measurements["bus_voltage_v"] * measurements["current_ma"], 2
    )
    # The fixed demo rig has no RPM sensor. A fixture must not invent observed motion.
    measurements["motor_rpm"] = None
    TelemetrySample.model_validate(sample)
    return sample


def run_simulator(
    client: httpx.Client,
    model: dict[str, Any],
    template: dict[str, Any],
    *,
    count: int,
    interval: float,
) -> int:
    """Register once, then publish a bounded stream; any rejected request stops it."""
    response = client.post(
        "/api/devices",
        json={"hardware_model": model, "display_name": "NeXus simulated rig", "source": "simulator"},
    )
    response.raise_for_status()
    boot_id = uuid4().hex
    endpoint = f"/api/devices/{quote(model['device_id'], safe='')}/telemetry"
    for sequence in range(count):
        sample = make_sample(template, model, boot_id=boot_id, sequence=sequence)
        response = client.post(endpoint, json=sample)
        response.raise_for_status()
        if sequence + 1 < count:
            time.sleep(interval)
    return count


def interval_argument(value: str) -> float:
    try:
        interval = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be a number") from exc
    if not math.isfinite(interval) or not 0.1 <= interval <= 60:
        raise argparse.ArgumentTypeError("interval must be between 0.1 and 60 seconds")
    return interval


def count_argument(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    if not 1 <= count <= 10_000:
        raise argparse.ArgumentTypeError("count must be between 1 and 10000")
    return count


def base_url_argument(value: str) -> str:
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError("base URL must be a valid HTTP(S) URL") from exc
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise argparse.ArgumentTypeError(
            "base URL must be an HTTP(S) origin without credentials, path, query or fragment"
        )
    return value.rstrip("/")


def device_id_argument(value: str) -> str:
    if not re.fullmatch(r"nexus-[a-z0-9-]{1,100}", value):
        raise argparse.ArgumentTypeError(
            "device ID must begin nexus- and contain 1–100 lowercase letters, digits or hyphens"
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=base_url_argument, default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=interval_argument, default=1.0, help="seconds (0.1–60)")
    parser.add_argument("--count", type=count_argument, default=30, help="samples (1–10000)")
    parser.add_argument("--device-id", type=device_id_argument)
    parser.add_argument(
        "--fixtures", type=Path,
        help="directory with hardware-model.example.json and telemetry.example.json",
    )
    args = parser.parse_args(argv)
    try:
        model, template = load_fixtures(args.fixtures)
        if args.device_id is not None:
            model["device_id"] = args.device_id
        print(f"SIMULATOR: publishing {args.count} samples for {model['device_id']}.", flush=True)
        with httpx.Client(base_url=args.base_url, timeout=10.0, follow_redirects=False) as client:
            sent = run_simulator(client, model, template, count=args.count, interval=args.interval)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Simulator fixture error: {type(exc).__name__}; check fixture files.", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"Simulator stopped: API returned HTTP {exc.response.status_code} "
            f"for {exc.request.method} {exc.request.url.path}.",
            file=sys.stderr,
        )
        return 1
    except httpx.RequestError:
        print("Simulator stopped: cannot reach the API; check server and base URL.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.", file=sys.stderr)
        return 130
    print(f"Published {sent} simulated samples. Open {args.base_url}/monitor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
