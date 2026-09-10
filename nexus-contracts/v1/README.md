# nexus-contracts v1

Contract version `1.0.0` is the frozen MVP interface for one ESP32 motor rig.

## Contract catalogue

| Contract | Producer | Primary consumers | Purpose |
| --- | --- | --- | --- |
| [`hardware-model.schema.json`](schemas/hardware-model.schema.json) | Backend | Frontend, Nemotron, orchestrator | Components, pins, connections, capabilities and safety limits |
| [`telemetry.schema.json`](schemas/telemetry.schema.json) | Firmware | Backend, frontend, Verify | Time-ordered electrical and device state |
| [`tool.schema.json`](schemas/tool.schema.json) | Orchestrator | Safety Policy, device adapter | Allowlisted, traceable and verifiable tool request |
| [`event.schema.json`](schemas/event.schema.json) | Backend pipeline | Frontend timeline, evidence log | Diagnosis, approval, action and verification lifecycle |

Each schema has one valid fixture:

| Fixture | Demonstrates |
| --- | --- |
| [`hardware-model.example.json`](fixtures/hardware-model.example.json) | GOOUUU ESP32-S3-N16R8, INA226 R100, L298N and JGB37-520 graph with the frozen S3 pin map |
| [`telemetry.example.json`](fixtures/telemetry.example.json) | One healthy power sample with a nullable RPM value |
| [`tool.example.json`](fixtures/tool.example.json) | A bounded motor test requested by the orchestrator |
| [`event.example.json`](fixtures/event.example.json) | A verification result linked by `trace_id` and `tool_call_id` |

## Shared conventions

- JSON keys use `snake_case` in every producer and consumer.
- `schema_version` is always `1.0.0` in v1.
- Device and hardware model IDs use the `nexus-` prefix.
- Timestamps use RFC 3339/ISO 8601 UTC strings when a clock is available.
- `recorded_at` may be `null` on the ESP32 until device time is synchronized.
- Stable envelopes reject unknown fields.
- Tool calls never bypass hardware-model safety limits.
- A successful action requires a newer telemetry sample and `verification.passed` event.

## Cross-stack mirrors

| Stack | File |
| --- | --- |
| Firmware | [`firmware/include/nexus_contract_v1.h`](../../firmware/include/nexus_contract_v1.h) |
| Backend | [`backend/src/nexus_backend/contracts.py`](../../backend/src/nexus_backend/contracts.py) |
| Frontend | [`frontend/src/contracts/v1.ts`](../../frontend/src/contracts/v1.ts) |

The JSON Schemas remain canonical. Mirrors exist for compilation and developer ergonomics; changing only one mirror is interface drift.

## Validate

Install backend development dependencies first. From the repository root:

```bash
python scripts/validate_contracts.py
python -m pytest backend/tests/test_contracts.py -q
```

The validator checks:

- all schemas are valid JSON Schema 2020-12 documents;
- all fixtures conform to their schemas;
- component and pin references exist;
- device, model, trace, and tool IDs agree across fixtures;
- firmware, backend, and frontend mirrors contain the shared telemetry keys;
- a schema change includes a migration note when a Git base ref is provided by CI.

## Before editing v1

Read [`../migrations/README.md`](../migrations/README.md). Prefer `v2` for a breaking change. An intentional v1 edit must update its fixture, every affected stack mirror, and a new numbered migration note in the same pull request.

The full runtime relationship is shown in [`docs/architecture.md`](../../docs/architecture.md).
