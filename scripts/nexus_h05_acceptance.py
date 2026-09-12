"""Qualify H05 from the locked software report and a real N03 adapter run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_EVIDENCE = REPOSITORY_ROOT / "docs/evidence/h05-h08-software-acceptance.json"
DEFAULT_N03_DIR = REPOSITORY_ROOT / "artifacts/N03"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/H05/nexus-h05-acceptance.json"
REQUIRED_SOFTWARE_COVERAGE = {
    "ACK/result/tool-call correlation",
    "fresh post-result telemetry",
    "timeouts, cancellation, duplicate replies and reset isolation",
    "persistent device-bound history and audit",
    "failed-read recovery without a success claim",
}


class AcceptanceError(RuntimeError):
    """A deterministic H05 acceptance failure."""


def load_ndjson(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AcceptanceError("H05_N03_ROW_INVALID")
            rows.append(value)
    return rows


def assess_acceptance(software: object, rows: list[dict], *, evidence_sha256: str) -> dict:
    if not isinstance(software, dict):
        raise AcceptanceError("H05_SOFTWARE_EVIDENCE_INVALID")
    integration = software.get("integration_evidence")
    if not isinstance(integration, dict):
        raise AcceptanceError("H05_INTEGRATION_EVIDENCE_MISSING")
    covered = set(integration.get("covered", []))
    if not REQUIRED_SOFTWARE_COVERAGE <= covered:
        raise AcceptanceError("H05_SOFTWARE_COVERAGE_INCOMPLETE")

    result_rows = [row for row in rows if row.get("kind") == "result"]
    if not result_rows or result_rows[-1].get("value", {}).get("outcome") != "PASS":
        raise AcceptanceError("H05_N03_PHYSICAL_RUN_NOT_PASSING")
    terminals = [row.get("value", {}) for row in rows if row.get("kind") == "terminal"]
    requests = [row.get("value", {}) for row in rows if row.get("kind") == "request"]
    request_ids = {row.get("request_id") for row in requests}
    correlated = all(row.get("request_id") in request_ids for row in terminals)
    if not correlated:
        raise AcceptanceError("H05_CORRELATION_FAILED")
    reads = [row for row in terminals if row.get("command") == "read_current"]
    if not reads or not all(row.get("response_type") == "result" for row in reads):
        raise AcceptanceError("H05_FRESH_MEASUREMENT_MISSING")
    denied = [
        row for row in terminals
        if row.get("response_type") == "error" and row.get("error", {}).get("code")
    ]
    if not denied:
        raise AcceptanceError("H05_FAILURE_PATH_MISSING")
    final = next((row.get("value", {}) for row in reversed(rows)
                  if row.get("kind") == "final_stop"), None)
    after = final.get("after", {}) if isinstance(final, dict) else {}
    if after.get("pwm_percent") != 0 or after.get("driver_enabled") is not False:
        raise AcceptanceError("H05_FINAL_SAFE_STATE_MISSING")

    return {
        "task_id": "H05",
        "outcome": "PASS",
        "checked_at": datetime.now(UTC).isoformat(),
        "orchestrator_coverage": sorted(REQUIRED_SOFTWARE_COVERAGE),
        "physical_adapter": {
            "source": "device",
            "outcome": "PASS",
            "evidence_sha256": evidence_sha256,
            "request_count": len(requests),
            "terminal_count": len(terminals),
            "failure_paths": len(denied),
            "fresh_current_reads": len(reads),
            "final_pwm_percent": 0,
            "final_driver_enabled": False,
        },
        "physical_write_path_from_diagnosis": False,
    }


def latest_evidence(directory: Path) -> Path:
    candidates = sorted(directory.glob("acceptance-*.ndjson"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise AcceptanceError("H05_N03_EVIDENCE_MISSING")
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--software-evidence", type=Path, default=SOFTWARE_EVIDENCE)
    parser.add_argument("--n03-evidence", type=Path)
    parser.add_argument("--n03-dir", type=Path, default=DEFAULT_N03_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        evidence = args.n03_evidence or latest_evidence(args.n03_dir)
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
        code = str(error) if isinstance(error, AcceptanceError) else "H05_EVIDENCE_READ_FAILED"
        print(json.dumps({"task_id": "H05", "outcome": "FAIL", "code": code}))
        return 1
    print(json.dumps({"task_id": "H05", "outcome": "PASS", "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
