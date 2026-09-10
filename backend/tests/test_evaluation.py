"""Check evaluation leakage, false positives, evidence gates and offline execution."""

import asyncio
import copy
import json
from datetime import UTC, datetime

import pytest

from nexus_backend.evaluation import (
    assess_plan,
    assess_simulated_run,
    case_inputs,
    evaluate_cases,
    load_cases,
    main,
    run_evaluation,
)
from nexus_backend.validation import validate_contract


def make_plan(identifier, evidence_ids, *, next_tool=None, stop_condition="diagnosed"):
    return {
        "hypotheses": [{"id": identifier, "label": "A test hypothesis",
                        "confidence": 1.0, "evidence_ids": evidence_ids}],
        "next_tool": next_tool, "confidence": 1.0,
        "user_message": "Test result", "stop_condition": stop_condition,
    }


def test_dataset_contains_ten_distinct_canonical_synthetic_cases():
    cases = load_cases()
    assert len(cases) >= 10
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({case["name"] for case in cases}) == len(cases)
    for case in cases:
        context, observations = case_inputs(case)
        validate_contract("hardware-model", context["hardware_model"])
        for sample in context["telemetry"]:
            validate_contract("telemetry", sample)
            assert sample["quality"]["source"] == "simulator"
            assert sample["measurements"]["motor_rpm"] is None
            assert "temperature" not in sample["measurements"]
        assert all(observation["source"] == "simulator" for observation in observations)
        assert case["expected_top2"]


def test_answers_and_case_names_cannot_leak_into_planner_input():
    original = load_cases()[3]
    changed = copy.deepcopy(original)
    changed.update(case_id="SECRET_CASE_ID", name="SECRET_DIAGNOSIS",
                   expected_top2=["SECRET_ANSWER"], require_no_write=True)
    assert case_inputs(original) == case_inputs(changed)
    serialized = json.dumps(case_inputs(changed))
    assert "SECRET" not in serialized
    assert "expected_top2" not in serialized


def test_confident_wrong_predictions_fail_even_if_planner_claims_success():
    class WrongPlanner:
        async def plan(self, context, observations):
            assert "expected_top2" not in context
            assert "case_id" not in context
            evidence = [sample["sample_id"] for sample in context["telemetry"]]
            if not evidence:
                evidence = [item["evidence_id"] for item in observations
                            if item["status"] == "succeeded"]
            return {**make_plan("normal", evidence), "success": True}

    report = asyncio.run(evaluate_cases(WrongPlanner()))
    assert report["top2_correct"] == 1
    assert not report["accuracy_gate_passed"]
    assert sum(case["scenario_passed"] for case in report["cases"]) == 1


def test_correct_answer_with_fabricated_evidence_fails_scenario():
    class FabricatingPlanner:
        async def plan(self, context, observations):
            return make_plan("power", ["made-up-sample"])

    report = asyncio.run(evaluate_cases(FabricatingPlanner(), [load_cases()[2]]))
    assert report["cases"][0]["top2_correct"]
    assert not report["cases"][0]["valid"]
    assert not report["cases"][0]["scenario_passed"]


@pytest.mark.parametrize("value", [81, 101, -1, "70", True, float("nan")])
def test_evaluator_rejects_unsafe_pwm_proposal(value):
    context, observations = case_inputs(load_cases()[3])
    plan = make_plan("pwm", ["simulation-sample-1"],
                     next_tool={"tool_name": "set_pwm", "arguments": {"pwm_percent": value}})
    assert not assess_plan(plan, context, observations, no_write=False)["valid"]


def test_failed_tool_evidence_is_not_a_successful_measurement():
    context, observations = case_inputs(load_cases()[8])
    evidence = ["simulation-observation-1"]
    invalid = make_plan("wiring", evidence, stop_condition="diagnosed")
    assert not assess_plan(invalid, context, observations, no_write=True)["valid"]
    valid = make_plan("tool_error", evidence, stop_condition="insufficient_evidence")
    assert assess_plan(valid, context, observations, no_write=True)["valid"]


def test_simulated_auto_heal_cannot_pass_by_claiming_success():
    result = {"status": "completed", "success": True, "plan": {},
              "observations": [], "events": [], "steps": 1}
    checked = assess_simulated_run(result, scenario="auto_heal")
    assert not checked["passed"]
    assert "No successful PWM correction was observed" in checked["errors"]
    assert "No fresh canonical readback proves the simulated current recovered" in checked["errors"]


@pytest.mark.parametrize("corruption", ["unrelated_verification", "old_sample", "other_device"])
def test_auto_heal_requires_correlated_fresh_readback(corruption):
    from nexus_backend.diagnosis import MockPlanner
    from nexus_backend.orchestrator import run_diagnosis

    context, observations = case_inputs(load_cases()[3], recorded_at=datetime.now(UTC).isoformat())
    result = asyncio.run(run_diagnosis(context, MockPlanner(), initial_observations=observations))
    assert assess_simulated_run(result, scenario="auto_heal")["passed"]
    if corruption == "unrelated_verification":
        for event in result["events"]:
            if event["event_type"] == "verification.passed":
                event["related_tool_call_id"] = "another-tool-call"
    else:
        write = next(item for item in result["observations"] if item["tool_name"] == "set_pwm")
        if corruption == "old_sample":
            write["data"]["after"]["sample_id"] = write["data"]["before"]["sample_id"]
        else:
            write["data"]["after"]["device_id"] = "nexus-another-device"
    assert not assess_simulated_run(result, scenario="auto_heal")["passed"]


def test_mock_report_never_uses_configured_live_credentials(monkeypatch):
    from nexus_backend import provider

    def forbidden_provider(*args, **kwargs):
        raise AssertionError("Offline evaluation tried constructing a live provider")

    monkeypatch.setattr(provider, "NebiusProvider", forbidden_provider)
    monkeypatch.setenv("NEXUS_NEBIUS_API_KEY", "not-a-real-key")
    report = asyncio.run(run_evaluation())
    assert report["planner_mode"] == "deterministic_mock"
    assert report["measurement_source"] == "simulator"
    assert report["cases"]["top2_correct"] == 10
    assert report["software_gate_passed"]
    assert not report["h07_complete"]
    assert report["acceptance_not_tested"]
    assert all(row["passed"] == row["total"] == 5
               for row in report["simulated_paths"]["scenarios"].values())


def test_cli_writes_report_and_keeps_hardware_gate_open(tmp_path, capsys):
    output = tmp_path / "report.json"
    assert main(["--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["software_gate_passed"]
    assert report["h07_complete"] is False
    assert json.loads(capsys.readouterr().out)["h07_complete"] is False


def test_live_flag_requires_configuration_and_does_not_print_secrets(monkeypatch, capsys):
    for key in ("NEXUS_NEBIUS_BASE_URL", "NEXUS_NEBIUS_API_KEY", "NEXUS_NVIDIA_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NEXUS_NEBIUS_API_KEY", "do-not-print-this-value")
    assert main(["--live"]) == 2
    output = capsys.readouterr().out
    assert "do-not-print-this-value" not in output
    assert json.loads(output)["h07_complete"] is False
