# U07 final acceptance — physical vertical slice

U07 passed on 12 September 2026 against the frozen physical MVP rig. This evidence is a
redacted, reviewable summary; the detailed runtime report and internal video remain local and
Git-ignored because they contain private device/session identifiers.

## Accepted result

- Physical source: GOOUUU ESP32-S3-N16R8 on `COM8`, device `nexus-demo-esp32`.
- Telemetry path: serial -> persistent backend history -> live WebSocket -> React Dashboard.
- Runtime gate: 3/3 live diagnosis runs passed with `source=device` and provider `nebius`.
- Reasoning: every run returned one evidence-linked hypothesis.
- Tooling: every run executed a policy-approved, read-only `get_telemetry` serial read and a
  matching audit event.
- Model proof: every run recorded three completed, redacted model calls.
- Safety: `physical_commands_enabled=false` and `physical_operation_verified=false` in all runs;
  PWM remained 0 and the driver remained off.
- Observed dashboard sample: approximately 12.10 V, 26.2 mA and 317 mW from INA226.

The Dashboard shell loaded successfully and `/api/v1/live/ws` delivered device sample
`nexus-demo-esp32-90`. The persisted history gate also received a fresh physical sample.

## Local evidence manifest

| Artifact | SHA-256 |
| --- | --- |
| `artifacts/U07/nexus-u07-vertical-slice.json` | `A5E03FED6754EE1A40B8F3E866F51A0F5982C5337C9EE0FE317679579EFBE1CA` |
| `artifacts/U07/nexus-u07-internal-demo-complete.mp4` | `707C267727F29156E8D71E16A61F9171B716B8D8997252242068E4B5B8E26FA7` |

The video shows the live Dashboard followed by a summary of all three run statuses, hypotheses,
read-only tool calls and safety state. The JSON report records the audit evidence and redacted
model-call metadata. Neither artifact contains the Nebius API key or a raw provider response.

## Scope statement

This proves the hackathon MVP vertical slice on one physical rig. It does not claim production
reliability, model quality benchmarking, or autonomous motor actuation. Motor writes remain
behind the separate H05/H06 and N03/N06 safety gates.
