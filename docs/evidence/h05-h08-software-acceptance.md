# H05–H08 independent software work — 12 September 2026

H05 now connects the diagnosis API to N03 read commands on the bridge's existing
serial connection and saves device-bound telemetry into H02 history. H06 rejects
motor actions both at the orchestrator policy and the serial adapter boundary.
An optional explicit device binding enables this path; it does not register or
reconfigure hardware and does not enable motor writes.

The [machine-readable evidence](h05-h08-software-acceptance.json) contains the
frozen challenge digests, safe provider metadata, per-case scores and scope limits.
It contains no API key, raw provider body, hidden reasoning or physical measurements.

## Software verification

- 381 backend tests passed, including 36 N03 channel/API integration cases.
- The serial tests use an in-memory port and scripted planner. They exercise the
  real bridge worker, split serial frames, correlated ACK/result processing,
  fresh telemetry, persistence, history WebSocket and diagnosis audit traces.
- Wrong source/device/model, reboot/reset, duplicate responses, timeouts,
  cancellation, partial writes and invalid readings cannot establish success.
- An ACK alone cannot pass; a valid command result and subsequent canonical
  telemetry frame are required. Firmware timestamps and sequences remain intact.
- All three motor write proposals are rejected without reaching the port, even
  when a test injects a permissive policy directly into the serial adapter.
- Ruff, repository validation and frozen contract checks passed. No v1 contract
  or firmware change was required.

## First live challenge result

Twelve new synthetic cases were frozen at `2026-09-12T05:33:59Z`, before the first
live run, with the already accepted `diagnosis-v2` prompt and Nemotron Ultra
configuration. No case, answer label, prompt or model setting was tuned against
the result, and the live suite was run once.

| Check | Result |
| --- | --- |
| Expected diagnosis among top two | 12/12 |
| Evidence and permitted-plan checks | 12/12 |
| Completed model calls | 12; no correction attempts |
| Input / output tokens | 45,732 / 19,579 |
| Slowest request | 11.642 seconds |
| Existing simulated Prevent / Manual / Auto Heal paths | 5/5 each |

The cases include unknown RPM, negative current versus a positive reference,
separate electrical inspections and an untrusted symptom requesting a fabricated
repair. This is a small locally authored challenge, not an independently collected
hardware benchmark. Future uses of this set are regression checks, not new unseen
evaluations. The original ten development cases remain unchanged.

## Reproducibility and remaining work

The runbook and `.env.example` describe explicit serial binding and fixed failure
status. Container CI verifies installed serial modules and all challenge fixtures
without USB access or API calls. Existing packaging checks verify the installed
API, prompts, development cases and simulated regression. Backend tests cover
disabled configuration, model failures and persisted controlled error outcomes.

```bash
python -m pytest backend/tests -q
python -m ruff check backend scripts
python scripts/validate_repo.py
python scripts/validate_contracts.py
python -m nexus_backend.evaluation --output artifacts/h07-offline.json
```

The optional `--live --env-file .env --dataset challenge` evaluation consumes
Nebius credits. It is not part of CI and should not be repeated without a reason.

The live Nebius challenge and in-memory serial integration were tested separately.
No real board, motor motion, physical fault profile or calibrated operating limit
was verified. GPIO support, supervised write integration, physical H05/H06
verification, N05-based H07 evaluation and final integrated H08 release acceptance
remain open. These results complete independent software deliverables, not every
acceptance gate of H05–H08.
