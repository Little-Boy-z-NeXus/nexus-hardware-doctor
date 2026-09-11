# NeXus documentation

This directory records the decisions required to build and demonstrate the hackathon MVP. Code and contracts are authoritative for runtime behavior; these documents explain scope, ownership, architecture, and operating constraints.

## Recommended reading order

1. [`mvp-scope.md`](mvp-scope.md) — the user, problem, three golden paths, and explicit exclusions.
2. [`architecture.md`](architecture.md) — runtime flow, Auto Heal sequence, service boundaries, and contract versioning.
3. [`nexus-wiring-jgb37-520.svg`](nexus-wiring-jgb37-520.svg) — exact GOOUUU ESP32-S3-N16R8, INA226, L298N and encoder wiring.
4. [`ownership.md`](ownership.md) — responsibilities for Hiếu, Hoàng, Nguyễn, and Nguyên.
5. [`hardware-baseline-u05.md`](hardware-baseline-u05.md) — supervised 30-minute electrical and safety acceptance.
6. [`security.md`](security.md) — secret handling, redaction, model/tool boundaries, and incident basics.
7. [`backlog.md`](backlog.md) — link to the live Google Sheet and local working rules.

## Document index

| Document | Use it when | Primary owner |
| --- | --- | --- |
| [`mvp-scope.md`](mvp-scope.md) | Deciding whether a feature belongs in the hackathon MVP | Hiếu |
| [`architecture.md`](architecture.md) | Changing a service boundary, data flow, tool, or schema | Hiếu + Hoàng |
| [`nexus-wiring-jgb37-520.svg`](nexus-wiring-jgb37-520.svg) | Building or checking the physical ESP32-S3/L298N motor rig | Hiếu + Nguyễn |
| [`ownership.md`](ownership.md) | Assigning work or choosing a reviewer | Hiếu |
| [`hardware-baseline-u05.md`](hardware-baseline-u05.md) | Running and evidencing the U05 hardware/safety gate | Hiếu + Nguyễn |
| [`n04-health-check.md`](n04-health-check.md) | Running deterministic pre-power rule checks without hardware | Nguyễn |
| [`security.md`](security.md) | Handling keys, telemetry, logs, prompts, or device commands | Hoàng + Hiếu |
| [`backlog.md`](backlog.md) | Finding the live plan or mapping a commit to a task ID | Entire team |
| [`h-resource-checklist.md`](h-resource-checklist.md) | Supplying resources to finish H tasks; remaining live acceptance gates | Hoàng |
| [`h01-h04.md`](h01-h04.md) | Configuring and testing model integration/diagnosis | Hoàng |
| [`h05-h06.md`](h05-h06.md) | Reviewing bounded orchestration and default-deny policy | Hoàng |
| [`h07-evaluation.md`](h07-evaluation.md) | Running labelled synthetic evaluation and understanding its limits | Hoàng |
| [`h08-runbook.md`](h08-runbook.md) | Starting an isolated backend and testing controlled failures | Hoàng |

## Source-of-truth rules

- Live task status and dates: the [Google Sheet backlog](https://docs.google.com/spreadsheets/d/1EOCmOg-qVQ_2OJV1DkeH9ULjkR7oT8kNMNGyrTKTUFs/edit).
- Runtime payload definitions: [`nexus-contracts`](../nexus-contracts/README.md).
- Current executable behavior: firmware, backend, and frontend source code.
- Scope decision: [`mvp-scope.md`](mvp-scope.md).
- Contribution process: root [`CONTRIBUTING.md`](../CONTRIBUTING.md).

If a document conflicts with a frozen schema, the schema wins until a migration is approved. If a local backlog note conflicts with the Google Sheet, the Google Sheet wins.

## Updating documentation

1. Link the change to one backlog ID.
2. Update the smallest authoritative document instead of copying the same rule into several files.
3. Use exact file names, contract keys, commands, ports, and hardware pins.
4. Label planned behavior as planned; do not describe incomplete integrations as available.
5. Update relative links when files move.
6. Run `python scripts/validate_repo.py` from the repository root.

Architecture or schema changes must update diagrams and migration notes in the same pull request. Hardware baseline results should be added only after the physical test in U05/N01; this documentation does not claim that test has run.

## Adding a new document

Use lowercase kebab-case, for example `nexus-demo-runbook.md` when a NeXus-specific name is appropriate. Add the new file to this index and identify its owner and authority level.
