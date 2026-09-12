# H01/H04 live Nebius acceptance — 12 September 2026

Real NVIDIA requests now pass the backend's JSON, evidence and tool checks. The final
run uses the team's current INA226 R100 hardware fixture on top of upstream commit
`221fbff`. The [machine-readable evidence](h01-h04-live-nebius.json) records provider
response IDs, model identity, token usage, latency, prompt digest and per-case outcomes.
It contains no key, raw provider body, private reasoning or real-device telemetry.

## Verified configuration

- Endpoint: `https://api.tokenfactory.nebius.com/v1`
- Model: `nvidia/Nemotron-3-Ultra-550b-a55b`, confirmed by the live catalog and responses
- `NEXUS_NEBIUS_ENABLE_THINKING=true`
- `NEXUS_NEBIUS_MAX_OUTPUT_TOKENS=4096`
- Prompt: `diagnosis-v2`; SHA-256 is recorded in the JSON evidence
- Credentials: local ignored `.env`; never copied into review artifacts

The evaluator's explicit `--live` flag authorizes its model calls. The application also
requires `NEXUS_ENABLE_LIVE_MODEL=true` and a live-mode diagnosis request.

## Results

| Check | Observed result |
| --- | --- |
| Real NVIDIA structured responses | 10/10 valid without a correction attempt in the final suite |
| Top-2 diagnosis | 10/10, exceeding the sheet's 8/10 minimum |
| Evidence references and permitted proposals | 10/10 valid |
| Prevent, Manual, Auto Heal regression | 5/5 each with the deterministic planner and simulator |
| Real-model read-only orchestration | Model-selected `get_telemetry`, followed by a measurement-linked PWM diagnosis |
| Local application path | Live diagnosis, session/event persistence, unchanged input telemetry, physical commands disabled |
| Backend regression after integrating upstream | 344 tests passed; Ruff, repository and frozen-contract checks passed |

The final ten-case suite used 38,141 input and 20,597 output tokens across ten completed
requests. The slowest request took 11.633 seconds. At the catalog rates observed during
setup, that suite is approximately $0.10; this excludes exploratory runs and other smoke
checks, and is not a billing statement.

## What changed

The live grammar compiler rejected `uniqueItems`; the request now omits that unsupported
keyword while full local validation still rejects duplicated references. The model receives
the same schema in its prompt, limited to the run's available tools, known evidence IDs and
shared diagnosis vocabulary. Unknown RPM is explicitly distinguished from zero RPM.

Nemotron's chat-template thinking control and a bounded output-token budget are explicit
configuration. An unusable response can trigger one short correction request; raw output,
private reasoning and credentials are never replayed. Every returned plan is still checked
locally before orchestration. Authentication/service failures retain their separate bounds.

The evaluation CLI can explicitly load an ignored environment file without shell evaluation
or variable interpolation. Completion metadata is allowlisted, and all completed correction
attempts are included in new reports. The root validator now permits ignored local secrets
while rejecting tracked or unignored credential files. The Windows launcher loads an existing
`.env`, matching the documented Python and Docker setup.

## Limits and unresolved work

These are **live model calls on synthetic inputs**. The ten cases were used during prompt
and configuration development; they are not a held-out accuracy benchmark. Earlier runs
scored 0–9/10 or failed validation, depending on model, settings and development version.
They remain in ignored local artifacts; they are not averaged away or represented as the
final configuration's accuracy. Lower-cost Nano/Lightning settings were unreliable for this
workflow. A successful final run does not establish production reliability.

The repeated golden paths still use the deterministic mock. They do not show a real motor
moving, a wire being repaired, calibrated current limits, or physical fault reproducibility.
The new N03 firmware/client exists upstream, but H05's policy-controlled integration with
that serial transport and persistent diagnosis history is still required. Default firmware
and the backend continue to disable physical writes. U05's supervised baseline, N05 fault
profiles and physical H05–H08 acceptance cannot be certified from an API key.

The normal API deadline remains bounded. Slow reasoning or a correction can exhaust it;
that produces a saved failure rather than an unverified success. CI does not call Nebius,
consume credits or use the local API key.

## Reproduce

From the repository root with the backend development environment installed:

```bash
python -m pytest backend/tests -q
python -m ruff check backend scripts
python scripts/validate_repo.py
python scripts/validate_contracts.py
python -m nexus_backend.evaluation --output artifacts/h07-offline.json
python -m nexus_backend.evaluation --live --env-file .env --output artifacts/h07-live.json
python scripts/check_live_model.py --live --env-file .env --output artifacts/h05-live.json
```

The last two commands make bounded billed model calls with synthetic data and never send
commands to a physical serial device. Full reports stay in ignored `artifacts/`; only the
reviewed, compact acceptance projection is committed here.
