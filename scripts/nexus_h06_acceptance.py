"""Qualify H06 safety policy and physical before/after verification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_EVIDENCE = REPOSITORY_ROOT / "docs/evidence/h05-h08-software-acceptance.json"
DEFAULT_N06_DIR = REPOSITORY_ROOT / "artifacts/N06"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/H06/nexus-h06-acceptance.json"
REQUIRED_CYCLES = set(range(1, 6))
REQUIRED_EVENTS = {
    "action.approved",
    "action.executed",
    "verification.measurement",
    "verification.passed",
}


class AcceptanceError(RuntimeError):
    """A deterministic H06 acceptance failure."""


def load_ndjson(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AcceptanceError("H06_ROW_INVALID")
            rows.append(value)
    return rows


def _events_by_cycle(rows: list[dict], event_type: str) -> dict[int, dict]:
    return {
        row.get("payload", {}).get("cycle"): row
        for row in rows
        if row.get("event_type") == event_type
        and isinstance(row.get("payload", {}).get("cycle"), int)
    }


def assess_acceptance(software: object, rows: list[dict], *, evidence_sha256: str) -> dict:
    if not isinstance(software, dict):
        raise AcceptanceError("H06_SOFTWARE_EVIDENCE_INVALID")
    integration = software.get("integration_evidence", {})
    covered = set(integration.get("covered", [])) if isinstance(integration, dict) else set()
    if "policy and adapter rejection of physical writes" not in covered:
        raise AcceptanceError("H06_DEFAULT_DENY_EVIDENCE_MISSING")

    completed = [row for row in rows if row.get("event_type") == "acceptance.completed"]
    payload = completed[-1].get("payload", {}) if completed else {}
    if (payload.get("outcome") != "PASS" or payload.get("passed_cycles") != 5
            or payload.get("required_cycles") != 5 or payload.get("failures") != []):
        raise AcceptanceError("H06_PHYSICAL_RUN_NOT_PASSING")

    cycle_events = {event: _events_by_cycle(rows, event) for event in REQUIRED_EVENTS}
    if any(set(events) != REQUIRED_CYCLES for events in cycle_events.values()):
        raise AcceptanceError("H06_CYCLE_TIMELINE_INCOMPLETE")

    current_rises = []
    for cycle in sorted(REQUIRED_CYCLES):
        approved = cycle_events["action.approved"][cycle].get("payload", {})
        measurement = cycle_events["verification.measurement"][cycle].get("payload", {})
        verified = cycle_events["verification.passed"][cycle].get("payload", {})
        requested = approved.get("requested_action", {})
        before = measurement.get("before", {})
        after = measurement.get("after", {})
        final = verified.get("after", {})
        if (requested.get("set_pwm") != 30 or requested.get("motor_test_ms") != 500):
            raise AcceptanceError("H06_ACTION_LIMIT_MISMATCH")
        if not before or not after or after.get("driver_enabled") is not True:
            raise AcceptanceError("H06_BEFORE_AFTER_MISSING")
        rise = measurement.get("current_rise_ma")
        if not isinstance(rise, (int, float)) or isinstance(rise, bool) or rise < 50:
            raise AcceptanceError("H06_RECOVERY_MEASUREMENT_INVALID")
        if (verified.get("healed_measurement") is not True
                or verified.get("bounded_motor_test") is not True
                or verified.get("final_safe_state") is not True
                or final.get("pwm_percent") != 0
                or final.get("driver_enabled") is not False):
            raise AcceptanceError("H06_POST_ACTION_VERIFICATION_FAILED")
        current_rises.append(round(float(rise), 3))

    final_reset = [row for row in rows if row.get("event_type") == "safety.final_reset"]
    if not final_reset:
        raise AcceptanceError("H06_FINAL_RESET_MISSING")
    counts = Counter(row.get("event_type") for row in rows)
    return {
        "task_id": "H06",
        "outcome": "PASS",
        "checked_at": datetime.now(UTC).isoformat(),
        "policy": {
            "unknown_action_default": "deny",
            "real_diagnosis_writes": "manual_required",
            "post_action_verification_required": True,
        },
        "physical_auto_heal": {
            "source": "device",
            "evidence_sha256": evidence_sha256,
            "cycles_passed": 5,
            "current_rise_ma": current_rises,
            "event_counts": {event: counts[event] for event in sorted(REQUIRED_EVENTS)},
            "final_pwm_percent": 0,
            "final_driver_enabled": False,
        },
    }


def latest_evidence(directory: Path) -> Path:
    candidates = sorted(directory.glob("auto-heal-*.ndjson"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise AcceptanceError("H06_PHYSICAL_EVIDENCE_MISSING")
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--software-evidence", type=Path, default=SOFTWARE_EVIDENCE)
    parser.add_argument("--n06-evidence", type=Path)
    parser.add_argument("--n06-dir", type=Path, default=DEFAULT_N06_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        evidence = args.n06_evidence or latest_evidence(args.n06_dir)
        raw = evidence.read_bytes()
        software = json.loads(args.software_evidence.read_text(encoding="utf-8"))
        result = assess_acceptance(
            software,
            load_ndjson(evidence),
            evidence_sha256=hashlib.sha256(raw).hexdigest(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (AcceptanceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        code = str(error) if isinstance(error, AcceptanceError) else "H06_EVIDENCE_READ_FAILED"
        print(json.dumps({"task_id": "H06", "outcome": "FAIL", "code": code}))
        return 1
    print(json.dumps({"task_id": "H06", "outcome": "PASS", "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
