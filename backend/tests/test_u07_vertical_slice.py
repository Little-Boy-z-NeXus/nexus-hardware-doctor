"""U07 acceptance rejects replay, missing model proof, and non-device tool results."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "nexus_u07_vertical_slice.py"
SPEC = importlib.util.spec_from_file_location("nexus_u07_vertical_slice", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
u07 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u07)


def snapshot(source="device"):
    return {
        "connection": {"status": "connected", "port": "COM8"},
        "telemetry": {
            "device_id": u07.DEVICE_ID, "hardware_model_id": u07.MODEL_ID,
            "sample_id": "sample-1", "sequence": 1, "quality": {"source": source},
        },
    }


def capabilities(**changed):
    value = {
        "live_enabled": True, "live_configured": True, "serial_reads_enabled": True,
        "serial_device_id": u07.DEVICE_ID, "serial_history_status": "receiving",
    }
    value.update(changed)
    return value


def successful_session():
    return {"session_id": "session-1", "result": {
        "trace_id": "trace-1", "mode": "live", "source": "device",
        "status": "needs_manual", "physical_commands_enabled": False,
        "physical_operation_verified": False,
        "plan": {"hypotheses": [{
            "id": "pwm", "confidence": 0.8, "evidence_ids": ["serial-sample"],
        }]},
        "observations": [{
            "tool_name": "get_telemetry", "tool_call_id": "tool-1", "status": "succeeded",
            "source": "device", "data": {"scope": "serial_read"},
        }],
        "events": [{"event_type": "action.executed", "related_tool_call_id": "tool-1"}],
        "model_runtime": {"provider": "nebius", "calls": [{
            "requested_model": "nvidia/Nemotron-test", "response_id": "chatcmpl-1",
            "finish_reason": "stop", "usage": {"total_tokens": 15},
        }]},
    }}


def test_preflight_accepts_only_bound_physical_device() -> None:
    telemetry = u07.require_runtime_preflight(capabilities(), snapshot())
    assert telemetry["quality"]["source"] == "device"
    with pytest.raises(u07.AcceptanceError, match="replay/simulator"):
        u07.require_runtime_preflight(capabilities(), snapshot("replay"))
    with pytest.raises(u07.AcceptanceError, match="NEXUS_ENABLE_LIVE_MODEL"):
        u07.require_runtime_preflight(capabilities(live_enabled=False), snapshot())


def test_live_run_requires_model_hypothesis_serial_read_and_audit() -> None:
    evidence = u07.validate_live_run(successful_session(), 1)
    assert evidence["hypotheses"][0]["id"] == "pwm"
    assert evidence["read_tool"]["tool_name"] == "get_telemetry"
    assert evidence["model_runtime"]["calls"][0]["response_id"] == "chatcmpl-1"

    missing = successful_session()
    missing["result"]["model_runtime"]["calls"] = []
    with pytest.raises(u07.AcceptanceError, match="model-call proof"):
        u07.validate_live_run(missing, 2)

    replay = successful_session()
    replay["result"]["observations"][0]["source"] = "replay"
    with pytest.raises(u07.AcceptanceError, match="get_telemetry"):
        u07.validate_live_run(replay, 3)


def test_live_websocket_requires_snapshot_envelope_with_device_telemetry() -> None:
    telemetry = u07.telemetry_from_live_message({"type": "snapshot", "data": snapshot()})
    assert telemetry["sample_id"] == "sample-1"

    with pytest.raises(u07.AcceptanceError, match="snapshot hợp lệ"):
        u07.telemetry_from_live_message(snapshot())
    with pytest.raises(u07.AcceptanceError, match="device thật"):
        u07.telemetry_from_live_message({"type": "snapshot", "data": snapshot("replay")})
