"""Exercise actual policy, sandbox changes, evidence binding and bounded failure paths."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from nexus_backend.context import build_context
from nexus_backend.mock_device import load_fixtures
from nexus_backend.orchestrator import run_diagnosis
from nexus_backend.tool_adapter import LocalToolAdapter, ToolExecutionError
from nexus_backend.validation import validate_contract


@pytest.fixture
def context():
    model, sample = load_fixtures()
    sample["quality"]["source"] = "simulator"
    sample["recorded_at"] = datetime.now(UTC).isoformat()
    sample["measurements"].update(pwm_percent=0, driver_enabled=True, current_ma=0, motor_rpm=None)
    return build_context(model, [sample], "Motor does not move")


def proposal(tool=None, *, stop="continue", evidence=None, hypothesis="zero_pwm"):
    return {"hypotheses": [{"id": hypothesis, "label": "Observed condition", "confidence": 0.9,
                             "evidence_ids": evidence or []}],
            "next_tool": tool, "confidence": 0.9, "user_message": "Review observed state.",
            "stop_condition": stop}


class SequencePlanner:
    def __init__(self, plans):
        self.plans = plans
        self.calls = 0

    async def plan(self, context, observations):
        entry = self.plans[min(self.calls, len(self.plans) - 1)]
        self.calls += 1
        return entry(context, observations) if callable(entry) else deepcopy(entry)


def run(context, planner, **kwargs):
    return asyncio.run(run_diagnosis(context, planner, **kwargs))


def write_then_diagnose():
    return SequencePlanner([
        proposal({"tool_name": "set_pwm", "arguments": {"pwm_percent": 40}}),
        lambda c, obs: proposal(stop="diagnosed", evidence=[obs[-1]["evidence_id"]],
                                hypothesis="normal"),
    ])


def test_simulated_change_is_verified_and_does_not_mutate_input_or_other_adapter(context):
    original = deepcopy(context)
    other = LocalToolAdapter(context)
    result = run(context, write_then_diagnose(), trace_id="trace-session-123")
    assert result["status"] == "diagnosed" and result["steps"] == 1
    assert result["trace_id"] == "trace-session-123"
    assert result["verified_simulated_changes"] == 1
    assert result["physical_operation_verified"] is False
    assert context == original and other.latest_sample() == original["telemetry"][-1]
    observation = result["observations"][0]
    assert observation["data"]["after"]["measurements"]["pwm_percent"] == 40
    assert observation["data"]["after"]["measurements"]["current_ma"] > 0
    assert observation["data"]["after"]["measurements"]["motor_rpm"] is None
    assert observation["verification"]["passed"] is True
    ids = set()
    for event in result["events"]:
        validate_contract("event", event)
        assert event["trace_id"] == result["trace_id"] and event["device_id"] == context["device_id"]
        assert event["event_id"] not in ids
        ids.add(event["event_id"])
    verified = [e for e in result["events"] if e["event_type"] == "verification.passed"]
    assert verified[0]["related_tool_call_id"] == observation["tool_call_id"]


def test_physical_writes_never_reach_an_adapter_even_with_simulated_input(context):
    class SpyAdapter(LocalToolAdapter):
        async def execute(self, name, args):
            raise AssertionError("Policy must block this before execution")

    result = run(context, write_then_diagnose(), mode="real",
                 adapter=SpyAdapter(context, mode="real"))
    assert result["status"] == "needs_manual" and result["verified_simulated_changes"] == 0
    assert result["observations"][0]["status"] == "blocked"


def test_stale_context_cannot_drive_even_a_simulated_action(context):
    context["telemetry"][-1]["recorded_at"] = (datetime.now(UTC) - timedelta(seconds=20)).isoformat()
    result = run(context, write_then_diagnose())
    assert result["status"] == "blocked"
    assert not any(e["event_type"] == "action.executed" for e in result["events"])


@pytest.mark.parametrize("evidence", [[], ["invented-sample"], ["obs-from-other-device"]])
def test_provider_cannot_claim_diagnosed_without_bound_evidence(context, evidence):
    result = run(context, SequencePlanner([proposal(stop="diagnosed", evidence=evidence)]))
    assert result["status"] == "invalid_plan"


def test_initial_sample_evidence_can_support_diagnosis_without_claiming_repair(context):
    plan = proposal(stop="diagnosed", evidence=[context["telemetry"][-1]["sample_id"]])
    result = run(context, SequencePlanner([plan]))
    assert result["status"] == "diagnosed" and result["verified_simulated_changes"] == 0
    assert result["physical_operation_verified"] is False


def test_lower_ranked_evidence_cannot_validate_an_unsupported_top_diagnosis(context):
    plan = proposal(stop="diagnosed")
    plan["hypotheses"].append({"id": "other", "label": "A supported weaker condition",
                               "confidence": 0.2,
                               "evidence_ids": [context["telemetry"][-1]["sample_id"]]})
    assert run(context, SequencePlanner([plan]))["status"] == "invalid_plan"


def test_repeated_read_requests_stop_at_loop_or_action_budget(context):
    repeated = proposal({"tool_name": "get_telemetry", "arguments": {}})
    result = run(context, SequencePlanner([repeated]), max_steps=6)
    assert result["status"] == "loop_detected" and result["steps"] == 2
    bounded = run(context, SequencePlanner([repeated]), max_steps=1)
    assert bounded["status"] == "max_steps" and bounded["steps"] == 1


def test_planner_and_tool_timeout_are_bounded(context):
    class SlowPlanner:
        async def plan(self, context, observations):
            await asyncio.sleep(10)

    assert run(context, SlowPlanner(), timeout_seconds=0.01)["status"] == "timeout"

    class SlowAdapter(LocalToolAdapter):
        async def execute(self, name, args):
            await asyncio.sleep(10)

    planner = SequencePlanner([proposal({"tool_name": "get_telemetry", "arguments": {}})])
    result = run(context, planner, adapter=SlowAdapter(context), timeout_seconds=0.01)
    assert result["status"] == "timeout"
    assert result["observations"][0]["status"] == "failed"


def test_read_failure_can_recover_into_manual_tool_error_without_false_measurement(context):
    class BrokenAdapter(LocalToolAdapter):
        calls = 0

        async def execute(self, name, args):
            self.calls += 1
            raise ToolExecutionError("Fixture transport error")

    adapter = BrokenAdapter(context)
    planner = SequencePlanner([
        proposal({"tool_name": "get_telemetry", "arguments": {}}),
        lambda c, obs: proposal(stop="needs_manual", evidence=[obs[-1]["evidence_id"]],
                                hypothesis="tool_error"),
    ])
    result = run(context, planner, adapter=adapter)
    assert result["status"] == "needs_manual" and adapter.calls == 2
    assert result["observations"][0]["status"] == "failed"
    assert result["verified_simulated_changes"] == 0


def test_read_acknowledgement_without_data_is_a_failed_observation(context):
    class EmptyReadAdapter(LocalToolAdapter):
        async def execute(self, name, args):
            return {"acknowledged": True}

    planner = SequencePlanner([
        proposal({"tool_name": "get_telemetry", "arguments": {}}),
        lambda c, obs: proposal(stop="diagnosed", evidence=[obs[-1]["evidence_id"]]),
    ])
    result = run(context, planner, adapter=EmptyReadAdapter(context))
    assert result["status"] == "invalid_plan"
    assert result["observations"][0]["status"] == "failed"


@pytest.mark.parametrize("case", ["missing_after", "unchanged", "wrong_device", "stale_after"])
def test_successful_ack_without_valid_after_evidence_never_passes_verification(context, case):
    class FalseAckAdapter(LocalToolAdapter):
        async def execute(self, name, args):
            if case == "missing_after":
                return {"acknowledged": True}
            if case == "unchanged":
                after = self._snapshot(pwm=0, enabled=True)
                return {"after": after, "sample": after}
            data = await super().execute(name, args)
            if case == "wrong_device":
                data["after"]["device_id"] = "nexus-other"
            else:
                data["after"]["recorded_at"] = (
                    datetime.now(UTC) - timedelta(seconds=20)
                ).isoformat()
            return data

    result = run(context, write_then_diagnose(), adapter=FalseAckAdapter(context))
    assert result["status"] == "needs_manual" and result["verified_simulated_changes"] == 0
    assert any(e["event_type"] == "verification.failed" for e in result["events"])
    assert not any(e["event_type"] == "verification.passed" for e in result["events"])


def test_bounded_motor_test_observes_active_state_then_stops_simulator(context):
    planner = SequencePlanner([
        proposal({"tool_name": "run_motor_test", "arguments": {"duration_ms": 500,
                                                                  "pwm_percent": 30}}),
        lambda c, obs: proposal(stop="diagnosed", evidence=[obs[-1]["evidence_id"]]),
    ])
    result = run(context, planner)
    assert result["verified_simulated_changes"] == 1
    data = result["observations"][0]["data"]
    assert data["during"]["measurements"]["pwm_percent"] == 30
    assert data["after"]["measurements"]["pwm_percent"] == 0
    assert data["after"]["measurements"]["driver_enabled"] is False


def test_cross_device_context_and_seed_or_non_simulator_mock_are_rejected(context):
    other = deepcopy(context)
    other["telemetry"][-1]["device_id"] = "nexus-other"
    with pytest.raises(ValueError):
        run(other, write_then_diagnose())
    seed = {"device_id": "nexus-other", "evidence_id": "inspection-1", "source": "simulator",
            "status": "succeeded", "data": {"motor_output_connected": False}}
    with pytest.raises(ValueError):
        run(context, write_then_diagnose(), initial_observations=[seed])
    context["telemetry"][-1]["quality"]["source"] = "device"
    with pytest.raises(ValueError):
        run(context, write_then_diagnose())


def test_explicit_simulation_inspection_supports_manual_diagnosis_only_in_mock_mode(context):
    seed = {"device_id": context["device_id"], "evidence_id": "inspection-1", "source": "simulator",
            "status": "succeeded", "data": {"motor_output_connected": False}}
    planner = SequencePlanner([proposal(stop="needs_manual", evidence=["inspection-1"])])
    result = run(context, planner, initial_observations=[seed])
    assert result["status"] == "needs_manual" and result["steps"] == 0
    assert result["observations"][0]["provenance"] == "supplied_simulation_fixture"
    with pytest.raises(ValueError):
        run(context, planner, mode="real", initial_observations=[seed])


def test_simulation_seed_cannot_hide_foreign_device_telemetry(context):
    foreign = deepcopy(context["telemetry"][-1])
    foreign["device_id"] = "nexus-other"
    seed = {"device_id": context["device_id"], "evidence_id": "inspection-1", "source": "simulator",
            "status": "succeeded", "data": {"sample": foreign}}
    with pytest.raises(ValueError):
        run(context, write_then_diagnose(), initial_observations=[seed])
