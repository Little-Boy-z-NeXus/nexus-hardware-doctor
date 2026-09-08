# nexus-contracts v1

This directory is the frozen interface boundary shared by firmware, backend, and frontend.

## Contract catalogue

| Contract | Producer | Primary consumers | Purpose |
| --- | --- | --- | --- |
| `hardware-model.schema.json` | Backend | Frontend, Nemotron, orchestrator | Fixed graph, pins, connections, capabilities, safety limits |
| `telemetry.schema.json` | Firmware | Backend, frontend, verify | Time-ordered measurements from one device |
| `tool.schema.json` | Orchestrator | Safety policy, firmware tool adapter | Allowlisted and traceable tool request |
| `event.schema.json` | Backend pipeline | Frontend timeline, evidence log | Diagnosis/action/verification lifecycle |

All payloads use `snake_case` and include `schema_version: "1.0.0"`. Unknown fields are rejected at the stable envelopes so accidental interface drift fails early.

## Freeze rule

The schemas under `v1/schemas` are frozen. Prefer creating `v2` for breaking changes. Any intentional v1 change must include a new Markdown file under `nexus-contracts/migrations/` in the same commit, with impact, compatibility, owner, and rollout notes. CI enforces this rule.

Validate locally after installing backend development dependencies:

```bash
python scripts/validate_contracts.py
```
