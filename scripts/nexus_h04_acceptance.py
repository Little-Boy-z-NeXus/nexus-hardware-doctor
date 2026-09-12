"""Validate the reviewed H04 live-model evidence without making another paid call."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = REPOSITORY_ROOT / "docs/evidence/h01-h04-live-nebius.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/H04/nexus-h04-acceptance.json"
REQUIRED_HYPOTHESES = {"power", "pwm", "driver", "wiring"}
FORBIDDEN_KEYS = {"api_key", "chain_of_thought", "hidden_reasoning", "raw_response"}


class AcceptanceError(RuntimeError):
    """A deterministic H04 acceptance failure."""


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        found = {str(key).lower() for key in value}
        for item in value.values():
            found.update(_keys(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_keys(item))
        return found
    return set()


def assess_live_evidence(report: object) -> dict:
    if not isinstance(report, dict):
        raise AcceptanceError("H04_EVIDENCE_NOT_OBJECT")
    cases = report.get("cases")
    model = report.get("model_configuration")
    if report.get("planner_mode") != "live_model_synthetic_inputs":
        raise AcceptanceError("H04_NOT_LIVE_MODEL")
    if report.get("prompt_version") != "diagnosis-v2":
        raise AcceptanceError("H04_PROMPT_VERSION_MISMATCH")
    if not isinstance(model, dict) or model.get("model") != "nvidia/Nemotron-3-Ultra-550b-a55b":
        raise AcceptanceError("H04_MODEL_MISMATCH")
    if not isinstance(cases, dict) or not isinstance(cases.get("cases"), list):
        raise AcceptanceError("H04_CASES_MISSING")
    if cases.get("total", 0) < 10 or cases.get("top2_correct", 0) < 8:
        raise AcceptanceError("H04_ACCURACY_GATE_FAILED")
    if cases.get("valid_evidence_and_safe_plan") != cases.get("total"):
        raise AcceptanceError("H04_EVIDENCE_GATE_FAILED")
    if not all(item.get("scenario_passed") is True for item in cases["cases"]):
        raise AcceptanceError("H04_SCENARIO_FAILED")

    hypotheses = {
        hypothesis
        for item in cases["cases"]
        for hypothesis in item.get("top2", [])
        if isinstance(hypothesis, str)
    }
    missing = sorted(REQUIRED_HYPOTHESES - hypotheses)
    if missing:
        raise AcceptanceError("H04_REQUIRED_HYPOTHESES_MISSING")
    leaked_fields = sorted(FORBIDDEN_KEYS & _keys(report))
    if leaked_fields:
        raise AcceptanceError("H04_PRIVATE_FIELD_PRESENT")

    return {
        "task_id": "H04",
        "outcome": "PASS",
        "checked_at": datetime.now(UTC).isoformat(),
        "planner_mode": report["planner_mode"],
        "prompt_version": report["prompt_version"],
        "model": model["model"],
        "cases": cases["total"],
        "top2_correct": cases["top2_correct"],
        "valid_plans": cases["valid_evidence_and_safe_plan"],
        "required_hypotheses": sorted(REQUIRED_HYPOTHESES),
        "private_reasoning_recorded": False,
        "new_model_call_made": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = assess_live_evidence(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (AcceptanceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        code = str(error) if isinstance(error, AcceptanceError) else "H04_EVIDENCE_READ_FAILED"
        print(json.dumps({"task_id": "H04", "outcome": "FAIL", "code": code}))
        return 1
    print(json.dumps({"task_id": "H04", "outcome": "PASS", "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
