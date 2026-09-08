# 0001 — Freeze contract v1

- Date: 2026-09-08
- Owner: Hiếu
- Version: `1.0.0`
- Compatibility: initial contract; no prior payload is guaranteed

## Decision

Freeze four MVP envelopes: hardware model, telemetry, tool call, and lifecycle event. Firmware, backend, and frontend use the exact `snake_case` field names defined here.

## Rollout

1. Firmware emits telemetry v1.
2. Backend rejects payloads that do not validate.
3. Frontend consumes only typed v1 payloads.
4. The orchestrator sends allowlisted tool calls and records a verification event.

## Rollback

Revert producers and consumers together to the commit before this freeze. Do not silently mutate a v1 schema to accommodate an incompatible payload.
