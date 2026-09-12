# H06 — Safety Policy Engine acceptance

H06 is complete for the MVP. The backend tool allowlist is exact, malformed/unknown actions
default to deny, real diagnosis writes require manual handling, and simulated changes cannot pass
without distinct fresh before/after samples. Policy decisions and verification reasons are present
in the audit path.

## Acceptance result

| Gate | Result |
| --- | --- |
| Unknown or unsafe request | PASS — denied by the policy/adapter matrices |
| Undeclared action default | PASS — deny |
| Voltage/current/PWM/duration/freshness bounds | PASS |
| Write evidence | PASS — reason plus before/after measurement required |
| Physical Auto Heal | PASS — 5/5 supervised cycles |
| Final state | PASS — PWM 0, driver off and fault profile reset |

The physical record was captured on 12 September 2026 on the frozen GOOUUU ESP32-S3-N16R8,
INA226 R100, L298N and JGB37-520 rig. Each cycle records approval, execution, a current rise of at
least 50 mA, a bounded 500 ms motor test, post-action verification and the safe final state. Raw
NDJSON remains local and ignored; the acceptance report stores only the digest and safe summary.

Run `nexus-run-h06-acceptance.cmd` to execute the policy tests and qualify the latest N06 record.
The ordinary live diagnosis API remains read-only; supervised physical acceptance does not create
an unreviewed remote actuation route.
