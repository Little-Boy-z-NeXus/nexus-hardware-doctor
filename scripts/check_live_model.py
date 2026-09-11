"""Opt-in live NVIDIA diagnosis with one synthetic, read-only tool cycle."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from nexus_backend.diagnosis import PROMPT_VERSION, NebiusPlanner
from nexus_backend.evaluation import assess_plan, case_inputs, load_cases
from nexus_backend.orchestrator import run_diagnosis
from nexus_backend.provider import NebiusProvider, ProviderConfig
from nexus_backend.tool_adapter import LocalToolAdapter


async def check(planner: NebiusPlanner) -> dict:
    # This fixture has zero PWM. Its label/expected answer is never sent to the model.
    context, _ = case_inputs(load_cases()[3], recorded_at=datetime.now(UTC).isoformat())
    context["symptom"] = (
        "The motor does not turn. Fetch the latest telemetry with get_telemetry before "
        "diagnosing; no telemetry is included in this initial planning snapshot."
    )
    adapter = LocalToolAdapter(context, mode="real")
    planning = copy.deepcopy(context)
    planning["telemetry"] = []
    result = await run_diagnosis(planning, planner, mode="real", adapter=adapter,
                                 max_steps=4, timeout_seconds=60)
    assessment = assess_plan(result.get("plan"), planning,
                             result.get("observations", []), no_write=True)
    observed = any(item["tool_name"] == "get_telemetry" and item["status"] == "succeeded"
                   for item in result["observations"])
    passed = (observed and assessment["valid"] and "pwm" in assessment["top2"]
              and result["status"] in {"diagnosed", "needs_manual"})
    return {
        "recorded_at": datetime.now(UTC).isoformat(), "prompt_version": PROMPT_VERSION,
        "model": planner.provider.config.model, "measurement_source": "simulator",
        "scope": "live_model_read_only_orchestration", "passed": passed,
        "completion": planner.provider.last_completion, "assessment": assessment,
        "result": result, "physical_acceptance_complete": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow bounded billed model calls")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/h05-live-orchestration.json"))
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; this check calls the configured model")
    try:
        environ = dict(os.environ)
        if args.env_file:
            if not args.env_file.is_file():
                raise FileNotFoundError
            environ = {**dotenv_values(args.env_file, interpolate=False), **environ}
        provider = NebiusProvider(ProviderConfig.from_env(environ))
        report = asyncio.run(check(NebiusPlanner(provider)))
        provider.reject_secret_echo(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception as error:  # noqa: BLE001 - never print raw request/provider details
        print(json.dumps({"error_type": type(error).__name__, "passed": False}))
        return 2
    print(json.dumps({"passed": report["passed"], "status": report["result"]["status"],
                      "steps": report["result"]["steps"], "report": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
