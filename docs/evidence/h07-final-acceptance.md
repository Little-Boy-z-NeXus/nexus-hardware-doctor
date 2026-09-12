# H07 — Evaluation harness acceptance

H07 is complete for the hackathon MVP. The final gate combines the frozen first-run Nemotron
challenge result, deterministic one-command regression, and independently recorded physical
fault/recovery cycles. It does not relabel synthetic telemetry as device data.

## Acceptance result

| Gate | Result |
| --- | --- |
| Labelled cases | PASS — 12, above the required 10 |
| Nemotron top-2 diagnosis | PASS — 12/12, above the required 8/10 |
| Evidence and safe-plan validity | PASS — 12/12 |
| Prevent golden path | PASS — 5/5 isolated orchestrator runs |
| Manual Diagnose golden path | PASS — 5/5 isolated orchestrator runs |
| Auto Heal golden path | PASS — 5/5 isolated orchestrator runs |
| Real fault reproducibility | PASS — PWM zero, low frequency, current offset and OUT2-open each 5 times |
| Real recovery reproducibility | PASS — physical Auto Heal 5/5 and restored baseline |

The model cases remain a small locally authored challenge, not an independent production
benchmark. Their first live run was frozen before execution and was not tuned after seeing the
result. The physical profiles provide real ground truth/repeatability but are not presented as a
new model test set. This separation prevents leakage while satisfying the MVP accuracy,
five-consecutive-run and real-reproducibility gates.

`nexus-run-h07-acceptance.cmd` reruns the offline regression, evaluation tests and aggregate gate
with one double-click. Raw N05/N06 logs remain local and ignored; the aggregate output records
only hashes, counts and safe summary fields.
