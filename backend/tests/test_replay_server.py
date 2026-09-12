import json
import threading

import pytest

from nexus_backend.replay_server import (
    ReplayError,
    load_replay,
    publish_replay,
    sanitize_for_replay,
)
from nexus_backend.serial_bridge import EXPECTED_HARDWARE_MODEL_ID, SerialBridge


def sample(sequence=1):
    return {
        "schema_version": "1.0.0",
        "device_id": "nexus-private-device",
        "hardware_model_id": EXPECTED_HARDWARE_MODEL_ID,
        "sample_id": f"private-{sequence}",
        "recorded_at": None,
        "sequence": sequence,
        "measurements": {
            "bus_voltage_v": 12.1,
            "current_ma": 30.0,
            "power_mw": 363.0,
            "pwm_percent": 0,
            "driver_enabled": False,
            "motor_rpm": None,
        },
        "quality": {"signal_quality_percent": 100.0, "source": "device"},
    }


def test_loader_accepts_direct_and_u05_serial_records(tmp_path) -> None:
    path = tmp_path / "replay.ndjson"
    path.write_text(
        json.dumps(sample()) + "\n"
        + json.dumps({"kind": "serial", "value": json.dumps(sample(2))}) + "\n"
        + json.dumps({"kind": "serial", "value": "not-json"}) + "\n",
        encoding="utf-8",
    )
    assert [item["sequence"] for item in load_replay(path)] == [1, 2]


def test_loader_rejects_missing_or_empty_inputs(tmp_path) -> None:
    with pytest.raises(ReplayError, match="does not exist"):
        load_replay(tmp_path / "missing.ndjson")
    empty = tmp_path / "empty.ndjson"
    empty.write_text(json.dumps({"kind": "serial", "value": "log only"}), encoding="utf-8")
    with pytest.raises(ReplayError, match="no valid"):
        load_replay(empty)


def test_replay_is_explicitly_sanitized_and_reaches_live_snapshot() -> None:
    value = sanitize_for_replay(sample(), boot_id="boot", sequence=7)
    assert value["device_id"] == "nexus-replay-esp32"
    assert value["sample_id"] == "nexus-replay-esp32-boot-7"
    assert value["quality"]["source"] == "replay"
    assert value["recorded_at"].endswith("Z")

    bridge = SerialBridge(enabled=False, persist_logs=False)
    stop = threading.Event()
    assert publish_replay(bridge, [sample()], interval=0.1, repeat=False, stop=stop) == 1
    snapshot = bridge.snapshot()
    assert snapshot["connection"]["port"] == "telemetry-replay"
    assert snapshot["telemetry"]["quality"]["source"] == "replay"
    assert snapshot["logs"][-1]["source"] == "replay"


def test_serial_bridge_rejects_unknown_log_provenance() -> None:
    bridge = SerialBridge(enabled=False, persist_logs=False)
    with pytest.raises(ValueError, match="firmware or replay"):
        bridge.ingest_line(json.dumps(sample()), source="network")
