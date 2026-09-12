"""Evaluate diagnosis from synthetic evidence; never certify real hardware."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from dotenv import dotenv_values

from .context import build_context
from .mock_device import load_fixtures
from .validation import validate_contract

READ_TOOLS = {"get_hardware_graph", "get_telemetry", "read_gpio"}
WRITE_TOOLS = {"set_pwm", "enable_driver", "run_motor_test"}
TERMINALS = {"continue", "diagnosed", "needs_manual", "insufficient_evidence"}
DATASETS = {"development": "eval_cases.json", "challenge": "eval_challenge_cases.json"}


def load_cases(dataset: str = "development") -> list[dict]:
    """Load labelled cases from the installed package, not the working directory."""
    if dataset not in DATASETS:
        raise ValueError("Unknown evaluation dataset")
    data = json.loads(files("nexus_backend").joinpath(DATASETS[dataset]).read_text("utf-8"))
    return data["cases"]


def case_inputs(case: dict, *, recorded_at: str = "2026-09-10T00:00:00Z") -> tuple[dict, list[dict]]:
    """Whitelist input fields so expected answers and case names never reach planners."""
    model, template = load_fixtures()
    samples = []
    if case["measurements"] is not None:
        sample = copy.deepcopy(template)
        sample.update(sample_id="simulation-sample-1", sequence=1, recorded_at=recorded_at)
        readings = sample["measurements"]
        readings.update(copy.deepcopy(case["measurements"]))
        readings["power_mw"] = round(readings["bus_voltage_v"] * readings["current_ma"], 2)
        readings["motor_rpm"] = None
        sample["quality"]["source"] = "simulator"
        samples = [validate_contract("telemetry", sample)]
    context = build_context(model, samples, case["symptom"])
    observations = []
    for index, item in enumerate(case["observations"]):
        observation = {
            "evidence_id": f"simulation-observation-{index + 1}",
            "device_id": model["device_id"],
            "source": "simulator",
            "status": item["status"],
            "tool_name": item["tool_name"],
            "data": copy.deepcopy(item["data"]),
            "recorded_at": recorded_at,
        }
        if "error" in item:
            observation["error"] = item["error"]
        observations.append(observation)
    return context, observations


def assess_plan(plan: object, context: dict, observations: list[dict], *, no_write: bool) -> dict:
    """Check measured evidence references and proposed actions independently of labels."""
    errors = []
    if not isinstance(plan, dict):
        return {"valid": False, "top2": [], "errors": ["Plan is not an object"]}
    hypotheses = plan.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        return {"valid": False, "top2": [], "errors": ["No ranked hypotheses"]}
    succeeded = {sample["sample_id"] for sample in context["telemetry"]}
    succeeded.update(item["evidence_id"] for item in observations if item["status"] == "succeeded")
    for observation in observations:
        if observation.get("status") == "succeeded":
            succeeded.update(sample["sample_id"] for sample in _samples(observation.get("data")))
    failed = {item["evidence_id"] for item in observations if item["status"] == "failed"}
    ranked = []
    seen = set()
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            errors.append("Malformed hypothesis")
            continue
        identifier = hypothesis.get("id")
        confidence = hypothesis.get("confidence")
        evidence = hypothesis.get("evidence_ids")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            errors.append("Invalid or repeated hypothesis ID")
            continue
        seen.add(identifier)
        if (type(confidence) not in (int, float) or not math.isfinite(confidence)
                or not 0 <= confidence <= 1):
            errors.append("Invalid hypothesis confidence")
            continue
        ranked.append((confidence, identifier))
        available = succeeded
        if (identifier == "tool_error"
                and plan.get("stop_condition") in {"needs_manual", "insufficient_evidence"}):
            available = succeeded | failed
        tentative = plan.get("stop_condition") == "insufficient_evidence" and not plan.get("next_tool")
        if (not isinstance(evidence, list) or (not evidence and not tentative)
                or any(not isinstance(ref, str) or ref not in available for ref in evidence)):
            errors.append(f"Unverified evidence for {identifier}")
    if plan.get("stop_condition") not in TERMINALS:
        errors.append("Unknown stop condition")
    action = plan.get("next_tool")
    if action is not None:
        if not isinstance(action, dict):
            errors.append("Malformed tool proposal")
        else:
            name, arguments = action.get("tool_name"), action.get("arguments")
            if name not in READ_TOOLS | WRITE_TOOLS or not isinstance(arguments, dict):
                errors.append("Unsupported tool proposal")
            elif no_write and name in WRITE_TOOLS:
                errors.append("Scenario requires no write action")
            elif name == "set_pwm":
                pwm = arguments.get("pwm_percent")
                if type(pwm) is not int or not 0 <= pwm <= 80:
                    errors.append("PWM proposal exceeds the allowed range")
    # Python's stable sort preserves the planner order when confidence is tied.
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if ranked and succeeded | failed:
        leading = next(item for item in hypotheses if item.get("id") == ranked[0][1])
        if not leading.get("evidence_ids"):
            errors.append("Leading hypothesis does not reference available evidence")
    return {"valid": not errors, "top2": [pair[1] for pair in ranked[:2]], "errors": errors}


async def evaluate_cases(planner, cases: list[dict] | None = None) -> dict:
    """Expected answers are read only after the planner has returned a prediction."""
    from .diagnosis import NebiusPlanner
    from .provider import ProviderError

    cases = load_cases() if cases is None else cases
    results = []
    for case in cases:
        context, observations = case_inputs(case, recorded_at=datetime.now(UTC).isoformat())
        if isinstance(planner, NebiusPlanner):
            planner.provider.last_completion = None
        try:
            plan = await asyncio.wait_for(
                planner.plan(copy.deepcopy(context), copy.deepcopy(observations)), timeout=60
            )
            assessment = assess_plan(plan, context, observations, no_write=case["require_no_write"])
        except Exception as error:  # noqa: BLE001 - Each failed planner must produce a failed case.
            # Exception messages can include provider bodies or credentials; do not persist them.
            assessment = {"valid": False, "top2": [], "errors": [type(error).__name__]}
            if isinstance(error, ProviderError):
                assessment["error_code"] = error.code
        if isinstance(planner, NebiusPlanner) and planner.provider.last_completion:
            assessment["completion"] = copy.deepcopy(planner.provider.last_completion)
        if isinstance(planner, NebiusPlanner):
            assessment["model_attempts"] = copy.deepcopy(planner.last_attempts)
        correct = bool(set(assessment["top2"]) & set(case["expected_top2"]))
        results.append({
            "case_id": case["case_id"], "name": case["name"],
            "expected_top2": case["expected_top2"], **assessment,
            "top2_correct": correct, "scenario_passed": correct and assessment["valid"],
        })
    total = len(results)
    correct_count = sum(result["top2_correct"] for result in results)
    valid_count = sum(result["valid"] for result in results)
    accuracy = correct_count / total if total else 0.0
    return {
        "total": total, "top2_correct": correct_count, "top2_accuracy": accuracy,
        "valid_evidence_and_safe_plan": valid_count,
        "threshold": 0.8, "accuracy_gate_passed": total >= 10 and accuracy >= 0.8,
        "safety_and_evidence_gate_passed": total >= 10 and valid_count == total,
        "cases": results,
    }


def _executed_writes(result: dict) -> list[dict]:
    return [item for item in result.get("observations", [])
            if item.get("tool_name") in WRITE_TOOLS and item.get("status") == "succeeded"]


def _samples(value: object) -> list[dict]:
    """Find canonical samples inside tool results, ignoring claimed success flags."""
    found = []
    if isinstance(value, dict):
        if {"sample_id", "measurements", "quality", "schema_version"} <= value.keys():
            try:
                found.append(validate_contract("telemetry", value))
            except ValueError:
                pass
        else:
            for item in value.values():
                found.extend(_samples(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_samples(item))
    return found


def assess_simulated_run(result: dict, *, scenario: str) -> dict:
    """Observe events/actions/readback rather than trusting result['status']."""
    errors = []
    events = result.get("events", [])
    if not events:
        errors.append("No audit events")
    for event in events:
        try:
            validate_contract("event", event)
        except (ValueError, TypeError):
            errors.append("Invalid audit event")
        if (event.get("trace_id") != result.get("trace_id")
                or event.get("device_id") != result.get("device_id")):
            errors.append("Audit event belongs to another trace or device")
    plan = result.get("plan") or {}
    top_ids = [item.get("id") for item in plan.get("hypotheses", [])[:2]]
    writes = _executed_writes(result)
    if scenario in {"prevent", "manual"}:
        expected = "overvoltage" if scenario == "prevent" else "wiring"
        if expected not in top_ids:
            errors.append("Required fault absent from the final hypotheses")
        if plan.get("stop_condition") not in {"needs_manual", "insufficient_evidence"}:
            errors.append("Fault did not stop for manual intervention")
        write_call_ids = {
            item.get("related_tool_call_id") for item in events
            if item.get("payload", {}).get("tool_call", {}).get("tool_name") in WRITE_TOOLS
        }
        if writes or any(item.get("event_type") == "action.executed"
                         and item.get("related_tool_call_id") in write_call_ids for item in events):
            errors.append("A write executed during a non-actuating scenario")
    elif scenario == "auto_heal":
        if not any(item.get("tool_name") == "set_pwm" for item in writes):
            errors.append("No successful PWM correction was observed")
        passed = [item for item in events if item.get("event_type") == "verification.passed"]
        if not passed:
            errors.append("No post-action verification event")
        healthy = []
        for write in writes:
            if write.get("tool_name") != "set_pwm":
                continue
            before = _samples(write.get("data", {}).get("before"))
            after = _samples(write.get("data", {}).get("after"))
            if len(before) != 1 or len(after) != 1:
                continue
            initial, sample = before[0], after[0]
            matching_events = [event for event in events if
                               event.get("related_tool_call_id") == write.get("tool_call_id")]
            phases = [event.get("event_type") for event in matching_events]
            required = ["action.approved", "action.executed", "verification.passed"]
            verified_sample = any(
                event.get("event_type") == "verification.passed"
                and event.get("payload", {}).get("before_sample_id") == initial["sample_id"]
                and event.get("payload", {}).get("after_sample_id") == sample["sample_id"]
                for event in matching_events
            )
            ordered = all(phase in phases for phase in required) and (
                [phases.index(phase) for phase in required]
                == sorted(phases.index(phase) for phase in required)
            )
            if (
                verified_sample and ordered
                and initial["device_id"] == sample["device_id"] == result.get("device_id")
                and initial["hardware_model_id"] == sample["hardware_model_id"]
                and sample["quality"]["source"] == initial["quality"]["source"] == "simulator"
                and sample["sample_id"] != initial["sample_id"]
                and sample["sequence"] > initial["sequence"]
                and initial["measurements"]["current_ma"] < 50
                and sample["measurements"]["driver_enabled"] is True
                and sample["measurements"]["pwm_percent"] == write["arguments"]["pwm_percent"]
                and 0 < sample["measurements"]["pwm_percent"] <= 80
                and 50 <= sample["measurements"]["current_ma"] <= 1500
                and sample["measurements"]["bus_voltage_v"] >= 9.5
            ):
                healthy.append(sample)
        if not healthy:
            errors.append("No fresh canonical readback proves the simulated current recovered")
    else:
        errors.append("Unknown simulation scenario")
    return {"passed": not errors, "errors": errors, "status": result.get("status"),
            "steps": result.get("steps"), "trace_id": result.get("trace_id")}


async def evaluate_simulated_paths(repetitions: int = 5) -> dict:
    """Repeat isolated software paths; no real board or model call is made here."""
    from .diagnosis import MockPlanner
    from .orchestrator import run_diagnosis

    if type(repetitions) is not int or not 1 <= repetitions <= 20:
        raise ValueError("Repetitions must be between 1 and 20")
    indexed = {case["case_id"]: case for case in load_cases()}
    results = {}
    for scenario, case_id in (("prevent", "case_02"), ("manual", "case_07"),
                              ("auto_heal", "case_04")):
        runs = []
        for _ in range(repetitions):
            context, observations = case_inputs(
                indexed[case_id], recorded_at=datetime.now(UTC).isoformat()
            )
            try:
                result = await run_diagnosis(
                    context, MockPlanner(), mode="mock", initial_observations=observations,
                    max_steps=6, timeout_seconds=10,
                )
                assessed = assess_simulated_run(result, scenario=scenario)
                evidence_check = assess_plan(
                    result.get("plan"), context, result.get("observations", []),
                    no_write=scenario != "auto_heal",
                )
                if not evidence_check["valid"]:
                    assessed["passed"] = False
                    assessed["errors"].extend(evidence_check["errors"])
                assessed["audit"] = {"observations": result.get("observations", []),
                                     "events": result.get("events", [])}
            except Exception as error:  # noqa: BLE001 - Record a failing run, never success.
                assessed = {"passed": False, "errors": [type(error).__name__]}
            runs.append(assessed)
        results[scenario] = {"passed": sum(item["passed"] for item in runs),
                             "total": repetitions, "runs": runs}
    return {"source": "simulator", "repetitions": repetitions, "scenarios": results,
            "gate_passed": repetitions >= 5 and all(
                row["passed"] == repetitions for row in results.values()
            )}


async def run_evaluation(*, live: bool = False, repetitions: int = 5,
                         environ: dict | None = None, dataset: str = "development") -> dict:
    from .diagnosis import PROMPT_VERSION, MockPlanner, NebiusPlanner

    selected_cases = load_cases(dataset)
    if live:
        from .provider import NebiusProvider, ProviderConfig
        planner = NebiusPlanner(NebiusProvider(ProviderConfig.from_env(environ)))
    else:
        planner = MockPlanner()
    cases = await evaluate_cases(planner, selected_cases)
    paths = await evaluate_simulated_paths(repetitions)
    passed = (cases["accuracy_gate_passed"] and cases["safety_and_evidence_gate_passed"]
              and paths["gate_passed"])
    return {
        "report_version": "1.2.0",
        "dataset_version": "h07-synthetic-v1" if dataset == "development" else "h07-challenge-v1",
        "dataset": dataset,
        "dataset_sha256": hashlib.sha256(files("nexus_backend").joinpath(
            DATASETS[dataset]).read_bytes()).hexdigest(),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(files("nexus_backend").joinpath(
            f"prompts/{PROMPT_VERSION}.txt"
        ).read_bytes()).hexdigest(),
        "model_configuration": {
            "base_url": planner.provider.config.base_url,
            "model": planner.provider.config.model,
            "enable_thinking": planner.provider.config.enable_thinking,
            "max_output_tokens": planner.provider.config.max_output_tokens,
        } if live else None,
        "recorded_at": datetime.now(UTC).isoformat(),
        "planner_mode": "live_model_synthetic_inputs" if live else "deterministic_mock",
        "measurement_source": "simulator", "cases": cases, "simulated_paths": paths,
        "software_gate_passed": passed, "h07_complete": False,
        "acceptance_not_tested": [
            "Real-rig fault reproduction and all three physical golden paths five times",
            "Physical motor movement, calibrated current baseline and safety limits",
            "N05 fault profiles and integrated live-model hardware diagnosis accuracy",
        ],
        "limitations": [
            ("Ten hand-labelled synthetic cases are a development regression set, not a held-out benchmark."
             if dataset == "development" else
             "The synthetic challenge was authored locally, not independently collected on real hardware; "
             "only its first run before tuning can be described as unseen by the selected model configuration."),
            "The deterministic mock and synthetic simulator cannot establish NVIDIA model quality.",
            "Prevent uses supplied electrical inspection evidence; N04 electrical rule validation is separate.",
            "Manual checks stop without writes; physical repair and a real retest remain unverified.",
            "Auto-heal verifies simulated current readback, not measured motor motion.",
            "Repeated deterministic software runs do not measure physical repeatability.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="Explicitly allow billed Nebius calls on synthetic cases; never actuates hardware")
    parser.add_argument("--env-file", type=Path,
                        help="Explicit local configuration file, used only with --live")
    parser.add_argument("--repetitions", type=int, choices=range(1, 21), default=5)
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="development")
    parser.add_argument("--output", type=Path, default=Path("artifacts/h07-evaluation.json"))
    args = parser.parse_args(argv)
    if args.env_file and not args.live:
        parser.error("--env-file requires --live")
    try:
        environ = None
        if args.env_file:
            if not args.env_file.is_file():
                raise FileNotFoundError
            environ = {**dotenv_values(args.env_file, interpolate=False), **os.environ}
        report = asyncio.run(run_evaluation(live=args.live, repetitions=args.repetitions,
                                            environ=environ, dataset=args.dataset))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception as error:  # noqa: BLE001 - CLI boundary must not print provider secrets.
        print(json.dumps({"error_type": type(error).__name__, "h07_complete": False}))
        return 2
    print(json.dumps({
        "planner_mode": report["planner_mode"],
        "top2_correct": report["cases"]["top2_correct"], "total": report["cases"]["total"],
        "software_gate_passed": report["software_gate_passed"], "h07_complete": False,
        "report": str(args.output),
    }))
    return 0 if report["software_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
