# H05 — Diagnostic Orchestrator acceptance

H05 is complete for the MVP. The production orchestrator implements the bounded
Plan → Select Tool → Execute → Observe → Update → Stop state machine with a deadline,
step/retry limits, stable trace/tool correlation and canonical audit events.

## Acceptance result

| Gate | Result |
| --- | --- |
| Infinite loop prevention | PASS — deadline, repeated-action and step bounds |
| Tool failure recovery | PASS — bounded retry then an explicit failed observation |
| Measurement-linked conclusions | PASS — invented/stale/cross-device evidence is rejected |
| Timeline | PASS — proposed, approved/denied, executed, observed, verified and completed events |
| Real N03 adapter | PASS — 16 checks, correlated responses, fresh INA226 reads and final PWM 0/off |

The physical N03 acceptance was recorded on 12 September 2026 with the frozen GOOUUU
ESP32-S3-N16R8 → INA226 R100 → L298N → JGB37-520 rig. The raw local NDJSON remains ignored;
`nexus-run-h05-acceptance.cmd` hashes and qualifies the latest passing record without copying
private telemetry into Git. The diagnostic path remains read-only by design, so H05 does not
create a hidden motor-write bypass.

The in-memory integration suite exercises the same serial bridge, correlation, persistence,
WebSocket history and orchestrator recovery code. Together with the physical adapter record,
this closes the sheet's actual-adapter and bounded-recovery requirements.
