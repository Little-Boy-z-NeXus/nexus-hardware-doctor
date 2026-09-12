# U06 integration operations

This folder contains evidence and decisions for U06. The Google Sheet remains the source of truth for live task status; dated files here are immutable daily snapshots that can be reviewed in pull requests.

## Daily 15-minute integration meeting

Run once per working day with Hiếu facilitating:

| Minute | Topic | Required output |
| --- | --- | --- |
| 0–3 | Status | Each owner states what changed since the previous check. |
| 3–8 | Blockers | Name the blocked task, owner and a resolution deadline within 24 hours. |
| 8–13 | Integration | Review open PRs, current `main` CI, contract changes and golden-path impact. |
| 13–15 | Next action | Record exactly one next action per active owner in the Sheet. |

Do not use the meeting for implementation or design debate. Move any discussion longer than two minutes to a named follow-up with an owner and deadline.

## Daily operating checklist

1. Read open pull requests and confirm each feature PR targets the agreed integration branch.
2. Require the current PR head to pass `nexus-ci`; stale green runs do not count.
3. Run `python scripts/validate_contracts.py` for any contract-facing change.
4. Reject undocumented field changes to schema version `1.0.0`; require a migration note under `nexus-contracts/migrations/`.
5. Identify impact on Prevent, Manual Diagnose and Auto Heal before merge.
6. Update the Sheet's `Integration Log` row with Status, Blocker, Owner and Next Action.
7. Save a dated snapshot in this folder only when a decision or blocker needs repository evidence.

## Traffic-light status

- `Xanh`: `main` is green, no unowned blocker and the golden path is intact.
- `Vàng`: build remains usable, but a dated blocker can threaten the critical path.
- `Đỏ`: `main` is broken, a safety rule regressed or a golden path cannot run.

## Merge gate

A feature may merge only when all of the following are true:

- acceptance criteria for its backlog ID are evidenced;
- `nexus-ci` is green at the current head;
- contract validation passes or an explicit migration note is included;
- no secret or private telemetry is committed;
- the affected golden path has a smoke result;
- rollback or safe fallback is stated for device-writing changes.

Hiếu owns the final merge decision. Hoàng reviews backend/model and architecture risk, Nguyễn reviews firmware/hardware safety, and Nguyên reviews frontend behavior.

## Decision record format

Use a stable ID such as `U06-DEC-001` and record context, decision, consequence, owner and review date. A decision that changes scope must also update `docs/mvp-scope.md`; one that changes a frozen interface must include a migration note.
