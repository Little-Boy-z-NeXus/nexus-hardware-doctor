"""Restore safe firmware and prove fresh MVP telemetry within the N08 three-minute gate."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import serial
from nexus_device_command import detect_port

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "N08"
EXPECTED_MODEL = "nexus-s3-ina226-l298n-motor-rig-v1"


def valid_recovery_sample(value: object) -> bool:
    if not isinstance(value, dict) or value.get("hardware_model_id") != EXPECTED_MODEL:
        return False
    measurements = value.get("measurements")
    if not isinstance(measurements, dict):
        return False
    bus = measurements.get("bus_voltage_v")
    current = measurements.get("current_ma")
    return (
        type(bus) in {int, float}
        and type(current) in {int, float}
        and math.isfinite(float(bus))
        and math.isfinite(float(current))
        and 9.5 <= float(bus) <= 13.0
        and abs(float(current)) <= 1500.0
        and measurements.get("pwm_percent") == 0
        and measurements.get("driver_enabled") is False
        and value.get("quality", {}).get("source") == "device"
    )


def wait_for_telemetry(port: str, timeout_seconds: float = 20) -> dict:
    deadline = time.monotonic() + timeout_seconds
    with serial.Serial(port, 115_200, timeout=0.25, dsrdtr=False, rtscts=False) as device:
        device.dtr = False
        device.rts = False
        while time.monotonic() < deadline:
            raw = device.readline().decode("utf-8", errors="replace").strip()
            if not raw.startswith("{"):
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if valid_recovery_sample(value):
                return value
    raise RuntimeError("No safe, valid INA226 telemetry arrived after firmware restore")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--port")
    parser.add_argument("--limit-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    operator = args.operator.strip()
    if not 1 <= len(operator) <= 80:
        print("[NEXUS][ERROR] Operator name must contain 1..80 characters")
        return 1
    if not 30 <= args.limit_seconds <= 180:
        print("[NEXUS][ERROR] Recovery limit must be 30..180 seconds")
        return 1
    started = time.monotonic()
    started_at = datetime.now(UTC).isoformat()
    command = [
        "pio", "run", "--project-dir", "firmware", "--environment",
        "nexus-goouuu-esp32-s3-n16r8", "--target", "upload",
    ]
    if args.port:
        command.extend(["--upload-port", args.port])
    result = subprocess.run(command, cwd=ROOT, check=False)
    sample = None
    error = None
    if result.returncode == 0:
        try:
            port = args.port or detect_port()
            if not port:
                raise RuntimeError("GOOUUU ESP32-S3 COM port was not found after upload")
            sample = wait_for_telemetry(port)
        except (OSError, RuntimeError, serial.SerialException) as exc:
            error = str(exc)
    else:
        error = f"PlatformIO upload returned {result.returncode}"
    elapsed = time.monotonic() - started
    passed = error is None and elapsed < args.limit_seconds
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    report = {
        "schema_version": "1.0.0",
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "operator": operator,
        "elapsed_seconds": round(elapsed, 3),
        "limit_seconds": args.limit_seconds,
        "outcome": "PASS" if passed else "FAIL",
        "firmware_environment": "nexus-goouuu-esp32-s3-n16r8",
        "writes_enabled": False,
        "telemetry": sample,
        "error": error if error is not None else (
            f"Recovery took {elapsed:.1f}s, exceeding the limit" if not passed else None
        ),
    }
    path = EVIDENCE / f"recovery-drill-{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[NEXUS][{'PASS' if passed else 'FAIL'}] recovery={elapsed:.1f}s "
        f"limit={args.limit_seconds}s evidence={path}"
    )
    if error:
        print(f"[NEXUS][ERROR] {error}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
