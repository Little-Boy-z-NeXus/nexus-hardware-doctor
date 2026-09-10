# H07 development evaluation

H07 has an offline regression dataset, a scored runner, and repeated simulated
orchestration checks. H07 remains **in progress** until the real diagnosis flow,
N05 fault profiles, and physical acceptance runs are available. A passing mock
report is software development evidence, not a completed hardware evaluation.

## Run the offline checks

From the repository root, after installing `backend[dev]`:

```bash
python -m nexus_backend.evaluation
```

This makes no external model calls and controls no physical device, even if
Nebius environment variables are already configured. It writes the detailed
report to `artifacts/h07-evaluation.json` and prints a small JSON summary. Use
`--output PATH` to choose another report location. Exit code `0` means the
software gates passed, `1` means a scored gate failed, and `2` means the runner
could not complete. `h07_complete` always remains `false`.

The default repeats each simulated path five times. `--repetitions 1` through
`20` can shorten debugging or increase repetition; fewer than five repetitions
cannot pass the repeated-path gate.

## Dataset and scoring

The ten labelled fixtures live in the installed `nexus_backend/eval_cases.json`
package resource. They cover normal operation, declared overvoltage conflict,
absent power, zero PWM, current calibration drift, driver output failure,
disconnected motor output, sensor timeout, tool transport error, and disabled
driver. Device inputs use the frozen hardware/telemetry schemas and explicitly
carry `source: simulator`.

Synthetic electrical inspections, continuity results and reference-current
readings are separate labelled simulator observations. They do not add sensors
to the real rig or change the frozen telemetry schema. No RPM or temperature
measurement is invented.

The runner constructs planner input from an explicit allowlist: symptom,
canonical hardware model, telemetry, and observed facts. It never passes case
names, case IDs, expected labels, or expected outcomes to the planner. Expected
labels are compared only after the returned prediction is available.

The report records:

- **Top-2 accuracy:** the expected diagnosis must occur among the two highest
  confidence predictions. The accuracy gate requires at least ten cases and
  accuracy of at least 80%.
- **Evidence and action validity:** predictions must reference available
  telemetry/observation evidence. A failed tool observation can support a
  `tool_error` outcome that stops for help; it cannot establish a successful
  hardware measurement. Unsupported tools, unsafe PWM and writes in scenarios
  requiring no actuation fail the scenario.
  An insufficient-evidence stop may retain unevidenced tentative alternatives;
  the leading hypothesis must cite evidence whenever any is available.
- **Scenario pass:** both the expected diagnosis and the independent evidence
  and action checks must pass. A model's own `success` claim has no authority.

The deterministic mock uses explicit measurement rules. These ten cases are a
small development set, not a held-out estimate of Nemotron accuracy.

## Repeated simulated paths

Every repetition creates a fresh isolated simulator and uses the real software
orchestrator and policy. The evaluator checks the resulting hypotheses, executed
tools, canonical audit events, and actual readback data. Synthetic timestamps are
set at run time so the policy's freshness checks remain active. Each repetition's
observations and audit events are included in the detailed report.

| Path | What the software check proves | What it does not prove |
| --- | --- | --- |
| Prevent | Supplied synthetic electrical-conflict evidence produces a stop without a write | N04's independent electrical rules, correct physical wiring, or a hardware interlock |
| Manual Diagnose | Synthetic disconnected-output evidence produces manual intervention without a write | Physical repair, motor movement, or a real post-repair test |
| Auto Heal | PWM correction executes in the simulator, verification is recorded, and a fresh canonical sample has enabled drive, allowed PWM and recovered current | Real motor movement or recovery against a calibrated rig baseline |

All events must validate against frozen event v1. Auto Heal cannot pass from a
success status alone, an initial sample, or a verification event without the
corresponding correction and fresh healthy readback. Repeating deterministic
software checks five times is not evidence of physical repeatability.
The evaluator correlates policy approval, execution, and verification to the same
tool call and checks matching before/after sample IDs, device identity, increasing
sample sequence, requested PWM, and measured current. Unrelated verification
events or another device's healthy sample cannot satisfy the check.

## Optional live-model scoring

Only when an operator explicitly chooses live calls and has safely configured
`NEXUS_NEBIUS_BASE_URL`, `NEXUS_NEBIUS_API_KEY`, and `NEXUS_NVIDIA_MODEL`:

```bash
python -m nexus_backend.evaluation --live --output artifacts/h07-live-synthetic.json
```

This can incur model usage. It sends the ten **synthetic** cases to the configured
Nebius model. Repeated software paths still use the deterministic mock and
isolated simulator. It does not send actions to a physical board. The report
marks its planner mode `live_model_synthetic_inputs`, and H07 remains incomplete.
Exception messages and raw provider bodies are not written to evaluation reports.

## Remaining acceptance evidence

Complete H01/H04–H06 and N05 on the chosen rig. Record actual baseline readings,
fault ground truth, model identity, before/after telemetry, tool/audit traces,
and five consecutive physical runs of each required golden path. Evaluate the
integrated live diagnosis against at least ten known cases and retain a report
showing top-2 accuracy of at least 8/10. Clearly identify any unavailable or
synthetic case instead of counting it as a physical test. Human-observed motor
movement and safe manual wiring repair remain external evidence.
