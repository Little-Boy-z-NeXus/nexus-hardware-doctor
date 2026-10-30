"""Create a secret-safe automated submission-readiness report.

This script verifies repository artifacts after the test/build commands have run. It deliberately
does not certify external accounts, repository visibility, live hardware, video, or Devpost state.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SUBMISSION_FILES = (
    "docs/submission/README.md",
    "docs/submission/devpost-submission.md",
    "docs/submission/video-script-en.md",
    "docs/submission/subtitles-en.srt",
    "docs/submission/release-checklist.md",
    "docs/submission/nebius-feedback.md",
    "docs/submission/significant-updates.md",
)
SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    # Short values in tests and documented placeholders are safe. Provider credentials are long;
    # require at least 32 token characters so the scan stays useful instead of teaching teams to
    # ignore a wall of known false positives.
    re.compile(r"NEXUS_NEBIUS_API_KEY\s*=\s*[\"']?[A-Za-z0-9_.$/{\}-]{32,}"),
)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False, text=True, encoding="utf-8",
    )


def tracked_secret_findings() -> list[dict[str, object]]:
    tracked = git("ls-files", "-z")
    if tracked.returncode != 0:
        return [{"file": "git", "line": 0, "pattern": "unable-to-list-tracked-files"}]
    findings: list[dict[str, object]] = []
    for relative in filter(None, tracked.stdout.split("\0")):
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "file": relative.replace("\\", "/"),
                        "line": line_number,
                        "pattern": pattern.pattern.split("\\s", maxsplit=1)[0],
                    })
    return findings


def load_evaluation(path: Path) -> tuple[bool, dict[str, object]]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"error": "missing-or-invalid-evaluation-report", "path": str(path)}
    scenarios = report.get("simulated_paths", {}).get("scenarios", {})
    summary = {
        name: f"{row.get('passed', 0)}/{row.get('total', 0)}"
        for name, row in scenarios.items() if isinstance(row, dict)
    }
    passed = bool(report.get("software_gate_passed")) and all(
        summary.get(name) == "5/5" for name in ("prevent", "manual", "auto_heal")
    )
    return passed, {
        "planner_mode": report.get("planner_mode"),
        "software_gate_passed": report.get("software_gate_passed"),
        "golden_paths": summary,
        "source": report.get("measurement_source"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=ROOT / "artifacts/submission/offline-evaluation.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/submission/readiness.json",
    )
    args = parser.parse_args(argv)
    missing = [relative for relative in REQUIRED_SUBMISSION_FILES if not (ROOT / relative).is_file()]
    secrets = tracked_secret_findings()
    evaluation_passed, evaluation = load_evaluation(args.evaluation)
    firmware = ROOT / "firmware/.pio/build/nexus-esp32-s3-devkitc-3wheel-ps2/firmware.bin"
    head = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain")
    automated = {
        "submission_files": {"passed": not missing, "missing": missing},
        "tracked_secret_scan": {"passed": not secrets, "findings": secrets},
        "offline_golden_paths": {"passed": evaluation_passed, **evaluation},
        "firmware_artifact": {
            "passed": firmware.is_file(),
            "path": str(firmware.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    automated_passed = all(item["passed"] for item in automated.values())
    report = {
        "report_version": "1.0.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "commit": head.stdout.strip() if head.returncode == 0 else None,
        "automated_gate_passed": automated_passed,
        "automated_checks": automated,
        "manual_gates": {
            "working_tree_clean": dirty.returncode == 0 and not dirty.stdout.strip(),
            "public_repository_verified": False,
            "final_live_nebius_rehearsal_verified": False,
            "final_physical_rig_verified": False,
            "public_video_under_three_minutes_verified": False,
            "devpost_team_and_submission_verified": False,
        },
        "scope_note": (
            "PASS covers local code, contracts, deterministic golden paths, tracked-secret scan, "
            "and firmware artifact only. Manual gates remain false until a human verifies them."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "automated_gate_passed": automated_passed,
        "manual_gates_remaining": sum(not value for value in report["manual_gates"].values()),
        "report": str(args.output),
    }))
    return 0 if automated_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
