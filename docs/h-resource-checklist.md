# H tasks: resources → completion

H-only handoff, 10 September 2026. The [shared sheet](https://docs.google.com/spreadsheets/d/1EOCmOg-qVQ_2OJV1DkeH9ULjkR7oT8kNMNGyrTKTUFs/edit?gid=86110275#gid=86110275) remains the status tracker. Inputs are cumulative: I supply the implementation, tests, documentation and PR; you supply account access, verified hardware facts or physical evidence. Providing inputs enables the remaining work, not automatic acceptance.

The [12 September live-model evidence](evidence/h01-h04-live-nebius.md) records working local API access, NVIDIA diagnosis results and read-only orchestration. The checklists below remain the resource requirements for each environment; the shared sheet remains the status tracker.

## Finished and submitted

- [x] **H02:** persistent backend/device sessions, streaming telemetry, audit and monitor.
- [x] **H03:** validated hardware loader, missing-metadata detection and bounded context.
- [x] **H04:** live Nemotron differential diagnosis evidence and strict final acceptance gate.
- [x] **H05:** bounded orchestrator qualified against the real N03 serial adapter evidence.
- [x] **H06:** default-deny safety policy and five verified physical before/after recovery cycles.
- [x] **H07:** 12-case live top-2 evaluation, 5/5 golden paths and repeated physical faults.
- [x] **H08:** clean Docker startup, offline fallback and controlled secret-safe model outage.

H04-H08 were finalized as separate reviewed changes; their current evidence is
[`h04-final-acceptance.md`](evidence/h04-final-acceptance.md),
[`h05-final-acceptance.md`](evidence/h05-final-acceptance.md),
[`h06-final-acceptance.md`](evidence/h06-final-acceptance.md),
[`h07-final-acceptance.md`](evidence/h07-final-acceptance.md), and
[`h08-final-acceptance.md`](evidence/h08-final-acceptance.md). Raw motor telemetry remains local
and ignored; committed acceptance reports contain only bounded summaries and evidence digests.

[PR #1](https://github.com/Little-Boy-z-NeXus/nexus-hardware-doctor/pull/1) contains these tasks and their [123-test acceptance evidence](evidence/h02-h03-acceptance.md). Partner approval/merge are separate from submitting the implementation.

## What has been prepared

| Task | Software available for review now | Input needed to finish the full task | Acceptance evidence |
| --- | --- | --- | --- |
| **H01 — Model integration** | Nebius adapter, configuration checks, bounded retries/timeouts, strict JSON and mocked failure tests | Working key, supported endpoint/model, quota/budget and U02 confirmations | Successful real structured response and redacted model proof |
| **H04 — Diagnosis agent** | Versioned prompt, proposal/evidence validation, deterministic simulated planner | H01's working access; no physical board required | Real model produces power/PWM/driver/wiring hypotheses and concise rationale |
| **H05 — Orchestrator** | Bounded execution, registry, recovery, canonical events and isolated simulated adapter | N03 command/telemetry access or rig/operator access to build/test it; H04 complete | Actual adapter integration, bounded failure paths and measurement-linked conclusions |
| **H06 — Safety engine** | Exact allowlist/arguments, default deny, limits/freshness checks and simulated before/after verification | Verified ratings/wiring/operating bounds; N03/H05 integration and physical test access | Unsafe/undeclared requests blocked; permitted writes have reason and fresh before/after evidence |
| **H07 — Evaluation** | Ten labelled synthetic cases, runner/report, repeated simulated scenario checks | N05 physical fault profiles/ground truth or access to produce them; H04–H06 complete | ≥10 cases, top-2 ≥8/10, five consecutive golden-path passes and real reproducibility |
| **H08 — Release** | Docker/Compose, dependency constraints, installed resources, lab/API, persistent results, rate/concurrency limits, structured logs and outage handling | H01–H07 acceptance; model configuration in clean validation environment | Fresh startup from runbook, controlled model-outage demo and no exposed secrets |

The table above is retained as the original preparation handoff. Its prerequisites were satisfied
by the final task-specific evidence linked under **Finished and submitted**. Simulation results
remain distinct from Nemotron accuracy and physical motor evidence.

## Checklist A — working model access → H01, then H04

- [ ] Store `NEXUS_NEBIUS_API_KEY` in the ignored root `.env` or a secret store. Give me its location; never paste the key into chat.
- [ ] Provide `NEXUS_NEBIUS_BASE_URL` and supported `NEXUS_NVIDIA_MODEL`.
- [ ] Confirm usable credits/quota and a maximum allowance for development/evaluation calls.
- [ ] Confirm U02's four Devpost registrations, representative, Builder Program and credit/access status.

I finish the live adapter/diagnosis checks and submit their evidence. No board is needed for these two. Calls are opt-in: enable `NEXUS_ENABLE_LIVE_MODEL=true` and explicitly select live mode after supplying access and budget.

## Checklist B — verified rig and adapter → H05/H06

- [ ] Confirm the actual BOM matches the current GOOUUU ESP32-S3-N16R8, INA226 R100, L298N and JGB37-520 Hall-encoder motor example; identify the supply and any substitutions.
- [ ] Labelled wiring diagram/photos and pin map, including motor outputs and grounds.
- [ ] Verified supply/component/pin ratings; PWM range, current ceiling, test duration and measured baseline. Example fixture values are not approved physical limits.
- [ ] Identified USB data port or documented gateway/device ID; connection secrets stored securely if applicable.
- [ ] An operator to handle power/wiring and observe motion, or teammate-run logs/video from the supplied procedure.
- [ ] If using the existing Hall encoder for verification: encoder supply/output ratings, pulse/gearing specifications, and access to implement/calibrate RPM measurement.
- [ ] N02/N03 evidence: correlated ACK/result/error, duplicates, timeout, invalid-command rejection and fresh before/after telemetry.

With Checklist A and H04 complete, I finish H05/H06 integration. If the adapter is unfinished, I can build it when rig/testing access is available; you do not need to supply finished code. Unknown electrical limits keep affected physical actions blocked.

## Checklist C — repeatable faults → H07

- [ ] N05 profiles: incorrect/zero PWM, calibration offset and motor OUT2 disconnect.
- [ ] Activation/reset instructions and ground-truth labels, or an available operator.
- [ ] Five actual reproductions/resets per profile with labelled logs and observation/video.
- [ ] Access for integrated Prevent/Manual/Auto checks after H04–H06 pass.

With A/B and that evidence, I finish H07. Replaying one recording five times does not demonstrate physical repeatability; mock reports remain separately labelled.

## Checklist D — earlier acceptance → H08

- [ ] H01–H07 acceptance evidence complete.
- [ ] Working model configuration in a fresh validation environment.
- [ ] Optional hosting target/project/access only if a live URL is wanted.

I finish release validation and submit H08. The task permits the reproducible Docker/runbook route: no new cloud account or purchased computer is required. See the [runbook](h08-runbook.md).

## Scope gaps affecting later integration

- Frozen v1 has no per-pin electrical ratings or maximum bus voltage, and its example omits a separate supply. Real-write validation needs verified facts.
- N03 wording differs from the frozen six-tool allowlist and `tool_call_id`. Use a compatible mapping or reviewed migration before real integration; the preemptive implementation does not silently extend frozen schemas.
- The current hardware declares a Hall encoder, but firmware still emits `motor_rpm: null`; pulse counting and RPM conversion are not implemented. Physical motor motion needs observation/video until that existing encoder is implemented and calibrated. No extra sensor purchase is assumed.
- The diagnosis lab validates H-backend behavior. It does not complete any G/frontend task.

## Submission route

The connected account has read-only upstream access. Code is pushed to `an1dee3301/nexus-hardware-doctor` and submitted by PR to `Little-Boy-z-NeXus/nexus-hardware-doctor`. Upstream write access is optional for this route. A normal review partner must approve before merge.
