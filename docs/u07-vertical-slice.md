# U07 — First vertical slice

U07 is the first strict end-to-end gate for the physical MVP:

```text
GOOUUU ESP32-S3 -> serial telemetry -> backend history/WebSocket -> React dashboard
                                      -> Nemotron hypothesis
                                      -> policy-approved get_telemetry -> fresh serial measurement
```

The slice is deliberately read-only. It never enables the L298N, changes PWM or starts the
motor. A replay or mock run is useful for development but cannot pass U07.

## One-time local configuration

Copy `.env.example` to the ignored `.env`. Keep the key only on the demo computer and set:

```dotenv
NEXUS_SERIAL_ENABLED=true
NEXUS_SERIAL_DEVICE_ID=nexus-demo-esp32
NEXUS_ENABLE_LIVE_MODEL=true
NEXUS_NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
NEXUS_NEBIUS_API_KEY=<local secret; never paste or commit>
NEXUS_NVIDIA_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b
NEXUS_NEBIUS_ENABLE_THINKING=true
NEXUS_NEBIUS_MAX_OUTPUT_TOKENS=4096
```

Use the exact endpoint and model available to the team's Nebius account if they change.
The application exposes only whether configuration is present; it never returns the key.

Before running, connect the GOOUUU board over USB, load current default-safe firmware, close
PlatformIO/Arduino Serial Monitor and leave the rig at PWM 0/driver off. The 12 V supply may
remain off because U07 performs no motor write, but INA226 will then truthfully report 0 V.

## One-click acceptance

Double-click `nexus-run-u07-vertical-slice.cmd`. It stops an old local app instance, starts
backend and frontend, registers the frozen physical rig when needed, waits for durable device
telemetry, verifies the realtime WebSocket and Dashboard shell, and runs three live diagnoses.

Every diagnosis starts without a cached measurement. Nemotron must first propose the
`get_telemetry` read-only tool; the policy approves it, the shared serial bridge obtains a new
N03 reading, and Nemotron must then return at least one evidence-linked hypothesis. A pass
requires all three runs to use `source=device` and `provider=nebius`.

The backend CMD log emits a payload-free `diagnosis.completed` record with `model_calls` and
model ID. The detailed redacted report is saved locally at
`artifacts/U07/nexus-u07-vertical-slice.json`; it contains trace/session/tool/model response IDs,
token counts and hypothesis IDs, but no key, prompt, provider body or raw serial log.

## Pass criteria

- backend and frontend start from the one batch file;
- connected telemetry is from `nexus-demo-esp32` with `quality.source=device`;
- the frontend Dashboard loads and `/api/v1/live/ws` carries device telemetry;
- 3/3 live runs contain a Nemotron hypothesis;
- 3/3 live runs contain a successful `get_telemetry` serial observation and matching audit event;
- 3/3 live runs contain redacted completed model-call metadata;
- physical commands and physical-operation claims remain false.

If any gate fails, the batch exits non-zero and prints a stable blocker code. Do not relabel a
replay/mock pass as U07 evidence.

## Internal video

After a 3/3 pass, record one short internal clip showing: the batch PASS line, Dashboard values
updating without reload, and the report's three `status`/`hypotheses` entries. Do not show the
`.env`, API key, raw provider response or private telemetry logs. Keep the video in the team's
private Drive during development; add only a reviewed share link to the Sheet.

## Current acceptance status — 12 September 2026

The software gate and one-click runner are implemented. The current local app was running the
explicit telemetry replay and had no live model configuration, so no new physical 3/3 report or
video was claimed. Existing H01 evidence proves earlier real Nemotron calls on synthetic data;
it does not replace this U07 physical vertical-slice run.
