"""Aggregate live-model scoring, regression and real fault-cycle evidence for H07."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODEL_EVIDENCE = REPOSITORY_ROOT / "docs/evidence/h05-h08-software-acceptance.json"
DEFAULT_N05_DIR = REPOSITORY_ROOT / "artifacts/N05"
DEFAULT_N06_DIR = REPOSITORY_ROOT / "artifacts/N06"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/H07/nexus-h07-acceptance.json"
REQUIRED_FAULT_PROFILES = {"pwm_zero", "pwm_frequency_low", "current_offset"}
GOLDEN_PATHS = {"prevent", "manual", "auto_heal"}


class AcceptanceError(RuntimeError):
    """A deterministic H07 acceptance failure."""


def load_ndjson(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AcceptanceError("H07_ROW_INVALID")
            rows.append(value)
    return rows


def _passing_result(rows: list[dict]) -> dict:
    results = [row.get("value", {}) for row in rows if row.get("kind") == "result"]
    return results[-1] if results else {}


def assess_acceptance(
    model_report: object,
    software_fault_rows: list[dict],
    manual_fault_rows: list[dict],
    restored_rows: list[dict],
    auto_heal_rows: list[dict],
    *,
    digests: dict[str, str],
) -> dict:
    if not isinstance(model_report, dict):
        raise AcceptanceError("H07_MODEL_EVIDENCE_INVALID")
    evaluation = model_report.get("evaluation", {})
    cases = evaluation.get("cases", {}) if isinstance(evaluation, dict) else {}
    if evaluation.get("planner_mode") != "live_model_synthetic_inputs":
        raise AcceptanceError("H07_LIVE_MODEL_RESULT_MISSING")
    if (cases.get("total", 0) < 10 or cases.get("top2_correct", 0) < 8
            or cases.get("top2_accuracy", 0) < 0.8):
        raise AcceptanceError("H07_TOP2_GATE_FAILED")
    if cases.get("valid_evidence_and_safe_plan") != cases.get("total"):
        raise AcceptanceError("H07_PLAN_VALIDITY_GATE_FAILED")

    paths = model_report.get("simulated_paths", {})
    if set(paths) != GOLDEN_PATHS:
        raise AcceptanceError("H07_GOLDEN_PATHS_MISSING")
    if any(path.get("total", 0) < 5 or path.get("passed") != path.get("total")
           for path in paths.values()):
        raise AcceptanceError("H07_GOLDEN_PATH_GATE_FAILED")

    software_result = _passing_result(software_fault_rows)
    manual_result = _passing_result(manual_fault_rows)
    restored_result = _passing_result(restored_rows)
    if software_result.get("outcome") != "PASS" or software_result.get("checks", 0) < 15:
        raise AcceptanceError("H07_SOFTWARE_FAULT_RUN_FAILED")
    if manual_result.get("outcome") != "PASS" or manual_result.get("checks", 0) < 5:
        raise AcceptanceError("H07_MANUAL_FAULT_RUN_FAILED")
    if restored_result.get("outcome") != "PASS":
        raise AcceptanceError("H07_RESTORED_BASELINE_FAILED")

    profiles = Counter(
        row.get("value", {}).get("profile")
        for row in software_fault_rows
        if row.get("kind") == "fault_apply"
    )
    if any(profiles[profile] < 5 for profile in REQUIRED_FAULT_PROFILES):
        raise AcceptanceError("H07_FAULT_REPRODUCTION_INCOMPLETE")
    manual_profiles = Counter(
        row.get("value", {}).get("profile")
        for row in manual_fault_rows
        if row.get("kind") == "fault_apply"
    )
    if manual_profiles["out2_open_manual"] < 5:
        raise AcceptanceError("H07_MANUAL_REPRODUCTION_INCOMPLETE")
    if any(
        row.get("value", {}).get("manual_action_required") != "true"
        for row in manual_fault_rows
        if row.get("kind") == "fault_apply"
    ):
        raise AcceptanceError("H07_MANUAL_GROUND_TRUTH_INVALID")

    completed = [
        row.get("payload", {}) for row in auto_heal_rows
        if row.get("event_type") == "acceptance.completed"
    ]
    verifications = [
        row for row in auto_heal_rows if row.get("event_type") == "verification.passed"
    ]
    if (not completed or completed[-1].get("outcome") != "PASS"
            or completed[-1].get("passed_cycles") != 5 or len(verifications) != 5):
        raise AcceptanceError("H07_AUTO_HEAL_REPRODUCTION_INCOMPLETE")

    return {
        "task_id": "H07",
        "outcome": "PASS",
        "h07_complete": True,
        "checked_at": datetime.now(UTC).isoformat(),
        "model_evaluation": {
            "dataset": evaluation.get("dataset"),
            "planner_mode": evaluation.get("planner_mode"),
            "total": cases["total"],
            "top2_correct": cases["top2_correct"],
            "top2_accuracy": cases["top2_accuracy"],
            "valid_plans": cases["valid_evidence_and_safe_plan"],
        },
        "golden_paths": {name: paths[name] for name in sorted(GOLDEN_PATHS)},
        "physical_reproducibility": {
            "fault_profiles": {name: profiles[name] for name in sorted(REQUIRED_FAULT_PROFILES)},
            "out2_open_manual": manual_profiles["out2_open_manual"],
            "auto_heal_verified": len(verifications),
            "restored_baseline": True,
            "evidence_sha256": digests,
        },
        "scope": "MVP acceptance; not a production reliability or independent benchmark claim",
    }


def latest(directory: Path, pattern: str, code: str) -> Path:
    candidates = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise AcceptanceError(code)
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-evidence", type=Path, default=MODEL_EVIDENCE)
    parser.add_argument("--n05-dir", type=Path, default=DEFAULT_N05_DIR)
    parser.add_argument("--n06-dir", type=Path, default=DEFAULT_N06_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        paths = {
            "n05_software": latest(args.n05_dir, "software-*.ndjson", "H07_N05_SOFTWARE_MISSING"),
            "n05_manual": latest(args.n05_dir, "out2-manual-*.ndjson", "H07_N05_MANUAL_MISSING"),
            "n05_restored": latest(args.n05_dir, "restored-*.ndjson", "H07_N05_RESTORED_MISSING"),
            "n06_auto_heal": latest(args.n06_dir, "auto-heal-*.ndjson", "H07_N06_MISSING"),
        }
        raw = {name: path.read_bytes() for name, path in paths.items()}
        result = assess_acceptance(
            json.loads(args.model_evidence.read_text(encoding="utf-8")),
            load_ndjson(paths["n05_software"]),
            load_ndjson(paths["n05_manual"]),
            load_ndjson(paths["n05_restored"]),
            load_ndjson(paths["n06_auto_heal"]),
            digests={name: hashlib.sha256(value).hexdigest() for name, value in raw.items()},
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (AcceptanceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        code = str(error) if isinstance(error, AcceptanceError) else "H07_EVIDENCE_READ_FAILED"
        print(json.dumps({"task_id": "H07", "outcome": "FAIL", "code": code}))
        return 1
    print(json.dumps({"task_id": "H07", "outcome": "PASS", "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
