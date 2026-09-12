# H04 — Differential Diagnosis Agent acceptance

H04 is complete against the MVP sheet criteria. The accepted `diagnosis-v2` planner uses
bounded hardware context and measured evidence, ranks hypotheses with confidence, proposes the
next discriminating read, and updates its ranking after observations. The public plan contains
short labels and a user-facing action; chain-of-thought and raw provider responses are neither
requested nor persisted.

## Acceptance result

| Gate | Result |
| --- | --- |
| Real Nemotron structured cases | PASS — 10/10 |
| Evidence-linked and safe plans | PASS — 10/10 |
| Required motor-no-motion hypotheses | PASS — power, PWM, driver and wiring |
| Prompt/template version | PASS — `diagnosis-v2` with recorded SHA-256 |
| Private reasoning or raw provider body stored | PASS — none |

The source is the reviewed [live Nebius record](h01-h04-live-nebius.md) and its redacted JSON.
`nexus-run-h04-acceptance.cmd` validates that immutable evidence plus planner/provider tests in
one command. It makes no new paid request and performs no hardware action.

This acceptance is for H04 diagnosis behavior. It does not claim H07 physical accuracy or
complete U07's physical vertical slice.
