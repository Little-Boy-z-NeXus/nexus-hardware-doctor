"""Bounded observe/plan/policy/execute/verify diagnosis orchestration."""

from __future__ import annotations

import asyncio
import json
import math
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from nexus_backend.hardware import load_hardware_model
from nexus_backend.policy import READ_TOOLS, WRITE_TOOLS, SafetyPolicy
from nexus_backend.tool_adapter import LocalToolAdapter
from nexus_backend.validation import validate_contract


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _event(device_id: str, trace_id: str, event_type: str, summary: str, *,
           payload: dict, source: str = "orchestrator", tool_call_id: str | None = None,
           severity: str = "info") -> dict:
    return validate_contract("event", {
        "schema_version": "1.0.0", "event_id": str(uuid4()), "trace_id": trace_id,
        "device_id": device_id, "event_type": event_type, "occurred_at": _now(),
        "source": source, "severity": severity, "summary": summary,
        "payload": payload, "related_tool_call_id": tool_call_id,
    })


def _context(context: dict, mode: str) -> dict:
    copied = deepcopy(context)
    model = load_hardware_model(copied["hardware_model"])
    if (copied["device_id"] != model["device_id"]
            or copied["hardware_model_id"] != model["hardware_model_id"]):
        raise ValueError("Context identity does not match its hardware model")
    samples = copied.get("telemetry", [])
    if not isinstance(samples, list) or len(samples) > 100:
        raise ValueError("Context must contain at most 100 telemetry samples")
    for sample in samples:
        validate_contract("telemetry", sample)
        if (sample["device_id"] != copied["device_id"]
                or sample["hardware_model_id"] != copied["hardware_model_id"]):
            raise ValueError("Context contains telemetry from another device or model")
        if mode == "mock" and sample["quality"]["source"] != "simulator":
            raise ValueError("Mock diagnoses require explicitly simulated telemetry")
    copied["available_tools"] = sorted(READ_TOOLS | WRITE_TOOLS) if mode == "mock" else (
        sorted(READ_TOOLS)
    )
    copied["execution_mode"] = mode
    copied["physical_actions_available"] = False
    copied["simulation_limits"] = {"max_bus_voltage_v": 14.0, "physical_rating": False}
    return copied


def _seed_observations(values: list[dict] | None, context: dict, mode: str,
                       trace_id: str) -> list[dict]:
    if values is None:
        return []
    if mode != "mock" or not isinstance(values, list) or len(values) > 20:
        raise ValueError("Seed observations are limited to 20 explicit simulation fixtures")
    identities = {sample["sample_id"] for sample in context["telemetry"]}
    observations = []
    for value in values:
        item = deepcopy(value)
        if (not isinstance(item, dict) or item.get("device_id") != context["device_id"]
                or item.get("source") != "simulator"
                or item.get("status") not in {"succeeded", "failed"}
                or not isinstance(item.get("data"), dict)
                or not isinstance(item.get("evidence_id"), str)
                or not 1 <= len(item["evidence_id"]) <= 128
                or item["evidence_id"] in identities):
            raise ValueError("Invalid, duplicated or cross-device simulation evidence")
        identities.add(item["evidence_id"])
        item["data"] = _check_result_data(item["data"], context, mode, trace_id)
        item["provenance"] = "supplied_simulation_fixture"
        # The canonical event payload validator also bounds and checks this open JSON object.
        _event(context["device_id"], trace_id, "diagnosis.proposed", "Validate simulation fixture",
               payload=item)
        observations.append(item)
    return observations


def _evidence_valid(plan: dict, context: dict, observations: list[dict]) -> bool:
    measurements = {sample["sample_id"] for sample in context["telemetry"]}
    failed = set()
    for observation in observations:
        if observation["status"] == "succeeded":
            measurements.add(observation["evidence_id"])
            # Nested canonical samples can also be directly cited by sample ID.
            for key in ("sample", "before", "after", "during"):
                sample = observation.get("data", {}).get(key)
                if isinstance(sample, dict) and sample.get("sample_id"):
                    measurements.add(sample["sample_id"])
        else:
            failed.add(observation["evidence_id"])
    cited = []
    for hypothesis in plan["hypotheses"]:
        evidence = hypothesis["evidence_ids"]
        allowed = measurements
        if hypothesis["id"] == "tool_error" and plan["stop_condition"] != "diagnosed":
            allowed = measurements | failed
        if any(identifier not in allowed for identifier in evidence):
            return False
        cited.extend(evidence)
    if plan["stop_condition"] == "diagnosed":
        strongest = max(plan["hypotheses"], key=lambda hypothesis: hypothesis["confidence"])
        return bool(cited) and bool(strongest["evidence_ids"]) and strongest["id"] != "tool_error"
    return True


def _check_result_data(data: object, context: dict, mode: str, trace_id: str,
                       tool_name: str | None = None) -> dict:
    if not isinstance(data, dict):
        raise TypeError("Tool result must be a JSON object")
    required = {"get_telemetry": "sample", "get_hardware_graph": "hardware_model"}
    if tool_name in required and data.get(required[tool_name]) is None:
        raise ValueError("The read tool did not return its required observation")
    _event(context["device_id"], trace_id, "action.executed", "Validate tool result", payload=data)
    for key in ("sample", "before", "after", "during"):
        sample = data.get(key)
        if sample is not None:
            validate_contract("telemetry", sample)
            if (sample["device_id"] != context["device_id"]
                    or sample["hardware_model_id"] != context["hardware_model_id"]
                    or (mode == "mock" and sample["quality"]["source"] != "simulator")):
                raise ValueError("Tool result identity or source does not match the diagnosis")
    if data.get("hardware_model") is not None:
        model = load_hardware_model(data["hardware_model"])
        if (model["device_id"] != context["device_id"]
                or model["hardware_model_id"] != context["hardware_model_id"]):
            raise ValueError("Tool returned another device's hardware graph")
    return deepcopy(data)


async def run_diagnosis(context: dict, planner, *, mode: str = "mock", max_steps: int = 6,
                        timeout_seconds: float = 30, trace_id: str | None = None,
                        max_retries: int = 1, adapter: LocalToolAdapter | None = None,
                        policy: SafetyPolicy | None = None,
                        initial_observations: list[dict] | None = None) -> dict:
    """Diagnose with bounded local tools; a result never verifies physical operation.

    An injected adapter and initial fixture observations support offline evaluation.
    HTTP routes do not expose these injection points. No real-mode write is ever
    delegated, including when a caller supplies a custom adapter.
    """
    from nexus_backend.diagnosis import validate_plan

    if mode not in {"mock", "real"}:
        raise ValueError("mode must be mock or real")
    if type(max_steps) is not int or not 1 <= max_steps <= 20:
        raise ValueError("max_steps must be an integer between 1 and 20")
    if type(max_retries) is not int or not 0 <= max_retries <= 2:
        raise ValueError("max_retries must be an integer between 0 and 2")
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120):
        raise ValueError("timeout_seconds must be positive and no more than 120")
    if trace_id is not None and (not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 128):
        raise ValueError("trace_id must contain 1-128 characters")
    identity = trace_id or str(uuid4())
    task_context = _context(context, mode)
    device_id = task_context["device_id"]
    safety = policy or SafetyPolicy()
    task_context["simulation_limits"]["max_bus_voltage_v"] = safety.simulation_max_voltage_v
    executor = adapter or LocalToolAdapter(task_context, mode=mode, policy=safety)
    if (executor.mode != mode or executor.context["device_id"] != device_id
            or executor.context["hardware_model_id"] != task_context["hardware_model_id"]):
        raise ValueError("Tool adapter must match the diagnosis mode, device and model")
    observations = _seed_observations(initial_observations, task_context, mode, identity)
    events = []
    steps = 0
    plan = None
    verified_changes = 0
    attempted_writes = 0
    requests = {}
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    def finish(status: str, reason: str) -> dict:
        return {"status": status, "plan": plan, "observations": observations, "events": events,
                "steps": steps, "trace_id": identity, "device_id": device_id, "mode": mode,
                "source": "simulator" if mode == "mock" else "context_snapshot",
                "summary": reason, "verified_simulated_changes": verified_changes,
                "physical_operation_verified": False,
                "limitations": ["No physical device commands were executed",
                                "Simulated state changes do not establish motor movement"]}

    async def bounded(awaitable):
        remaining = max(0, deadline - asyncio.get_running_loop().time())
        return await asyncio.wait_for(awaitable, timeout=remaining)

    for _ in range(max_steps + 1):
        for retry in range(max_retries + 1):
            try:
                raw_plan = await bounded(planner.plan(deepcopy(task_context), deepcopy(observations)))
                break
            except TimeoutError:
                return finish("timeout", "Diagnosis reached its time limit")
            except Exception:  # noqa: BLE001 - provider boundary fails closed without leaking details
                if retry == max_retries:
                    return finish("planner_failed", "The planner failed after bounded retries")
        try:
            candidate = validate_plan(raw_plan)
            if not _evidence_valid(candidate, task_context, observations):
                return finish("invalid_plan", "The plan cites absent or unsuitable evidence")
            plan = candidate
        except (ValueError, TypeError, KeyError):
            return finish("invalid_plan", "The planner returned an invalid structured plan")
        events.append(_event(device_id, identity, "diagnosis.proposed", "Structured diagnosis proposed",
                             payload={"plan": plan, "mode": mode}))
        stop = plan["stop_condition"]
        tool = plan["next_tool"]
        if stop != "continue":
            if tool is not None:
                return finish("invalid_plan", "A stopped plan cannot request a tool")
            if stop == "diagnosed" and attempted_writes > verified_changes:
                return finish("needs_manual", "An attempted change has no successful verification")
            return finish(stop, "Diagnosis prepared from recorded evidence; physical operation "
                          "remains unverified" if stop == "diagnosed" else
                          "Diagnosis requires more evidence or manual inspection")
        if tool is None:
            return finish("invalid_plan", "A continuing plan must request one tool")
        if steps >= max_steps:
            return finish("max_steps", "Diagnosis reached its action limit")
        name, arguments = tool["tool_name"], tool["arguments"]
        signature = json.dumps(tool, sort_keys=True, separators=(",", ":"))
        requests[signature] = requests.get(signature, 0) + 1
        if requests[signature] > 2:
            return finish("loop_detected", "The planner repeated an unchanged action request")
        steps += 1
        tool_id = str(uuid4())
        call = validate_contract("tool", {
            "schema_version": "1.0.0", "tool_call_id": tool_id, "trace_id": identity,
            "device_id": device_id, "tool_name": name, "arguments": arguments,
            "requested_by": "orchestrator", "requested_at": _now(),
            "requires_verification": name in WRITE_TOOLS,
        })
        before = executor.latest_sample()
        decision = safety.evaluate(name, arguments, context=task_context, sample=before, mode=mode)
        observation = {"evidence_id": f"obs-{uuid4()}", "tool_call_id": tool_id,
                       "tool_name": name, "arguments": deepcopy(arguments), "device_id": device_id,
                       "recorded_at": _now(), "source": "simulator" if mode == "mock" else (
                           before["quality"]["source"] if before else "declared_configuration"),
                       "status": "blocked", "data": {}}
        events.append(_event(device_id, identity,
                             "action.approved" if decision.allowed else "action.rejected",
                             decision.reason, source="safety_policy", tool_call_id=tool_id,
                             payload={"tool_call": call, "decision": decision.to_dict()},
                             severity="info" if decision.allowed else "warning"))
        if not decision.allowed:
            observation["error"] = decision.reason
            observations.append(observation)
            return finish("needs_manual" if decision.classification == "manual_required" else
                          "blocked", decision.reason)
        if name in WRITE_TOOLS:
            attempted_writes += 1
        data = None
        failure = None
        timed_out = False
        for retry in range((max_retries if name in READ_TOOLS else 0) + 1):
            try:
                data = _check_result_data(await bounded(executor.execute(name, deepcopy(arguments))),
                                          task_context, mode, identity, name)
                break
            except TimeoutError:
                failure = "Tool execution reached the diagnosis time limit"
                timed_out = True
                break
            except Exception:  # noqa: BLE001 - a failed adapter must never establish an action result
                failure = "Tool execution failed; no successful measurement was established"
        if data is None:
            observation.update(status="failed", error=failure)
            observations.append(observation)
            events.append(_event(device_id, identity, "action.rejected", failure, source="tool",
                                 tool_call_id=tool_id, severity="error", payload={"mode": mode}))
            if name in WRITE_TOOLS:
                events.append(_event(device_id, identity, "verification.failed",
                                     "The failed action has no verified result", source="verify",
                                     tool_call_id=tool_id, severity="warning",
                                     payload={"scope": "simulation",
                                              "physical_operation_verified": False}))
                return finish("needs_manual", "The attempted change could not be verified")
            if timed_out:
                return finish("timeout", "Diagnosis reached its time limit")
            continue
        observation.update(status="succeeded", data=data, recorded_at=_now())
        events.append(_event(device_id, identity, "action.executed", "Local tool returned an observation",
                             source="tool", tool_call_id=tool_id,
                             payload={"mode": mode, "evidence_id": observation["evidence_id"],
                                      "physical_operation_verified": False}))
        if name in WRITE_TOOLS:
            verification = safety.verify(name, arguments, context=task_context, before=before,
                                         after=data.get("after"), during=data.get("during"))
            observation["verification"] = verification
            events.append(_event(device_id, identity, "verification.passed" if verification["passed"]
                                 else "verification.failed", verification["reason"], source="verify",
                                 tool_call_id=tool_id, payload=verification,
                                 severity="info" if verification["passed"] else "warning"))
            if verification["passed"]:
                verified_changes += 1
            else:
                observations.append(observation)
                return finish("needs_manual", "Telemetry did not verify the simulated change")
        observations.append(observation)
    return finish("max_steps", "Diagnosis reached its action limit")
