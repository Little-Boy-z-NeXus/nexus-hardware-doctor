"""The opt-in smoke check uses actual orchestration and mocked model HTTP."""

import asyncio
import json
import runpy
from pathlib import Path

import httpx
import pytest

from nexus_backend.diagnosis import NebiusPlanner
from nexus_backend.provider import NebiusProvider, ProviderConfig

SCRIPT = runpy.run_path(str(Path(__file__).parents[2] / "scripts/check_live_model.py"))


def test_smoke_requires_model_selected_read_and_evidence_bound_diagnosis():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][1]["content"])["untrusted_diagnostic_data"]
        calls.append(data)
        evidence = [] if not data["observations"] else [
            data["observations"][-1]["data"]["sample"]["sample_id"]
        ]
        plan = {
            "hypotheses": [{"id": "pwm", "label": "Zero PWM", "confidence": 0.9,
                            "evidence_ids": evidence}],
            "next_tool": None if evidence else {"tool_name": "get_telemetry", "arguments": {}},
            "confidence": 0.9, "user_message": "Synthetic PWM fault; physical state unverified.",
            "stop_condition": "needs_manual" if evidence else "continue",
        }
        return httpx.Response(200, json={"model": "nvidia/test", "choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps(plan)},
        }]})

    provider = NebiusProvider(
        ProviderConfig("https://api.tokenfactory.nebius.com/v1", "fake-secret", "nvidia/test"),
        transport=httpx.MockTransport(handler),
    )
    report = asyncio.run(SCRIPT["check"](NebiusPlanner(provider)))
    assert report["passed"]
    assert report["result"]["steps"] == 1
    assert report["physical_acceptance_complete"] is False
    assert report["measurement_source"] == "simulator"
    assert len(calls) == 2 and calls[0]["telemetry"] == []
    assert calls[1]["observations"][0]["source"] == "simulator"


def test_smoke_cli_requires_opt_in_and_fails_closed_without_configuration(monkeypatch, capsys):
    with pytest.raises(SystemExit) as caught:
        SCRIPT["main"]([])
    assert caught.value.code == 2
    for key in ("NEXUS_NEBIUS_BASE_URL", "NEXUS_NVIDIA_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NEXUS_NEBIUS_API_KEY", "never-print-this")
    assert SCRIPT["main"](["--live"]) == 2
    assert "never-print-this" not in capsys.readouterr().out
