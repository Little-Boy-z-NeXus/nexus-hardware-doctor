# Devpost submission copy — NeXus Hardware Doctor

## Project name

NeXus — AI Hardware Doctor

## Tagline

Hardware-as-Code, live telemetry, and Nemotron-powered diagnosis for safer physical systems.

## Inspiration

When a robot or small machine fails, the symptom is often obvious but the cause is not. A loose
signal wire, wrong sensor firmware, disabled driver, or unsafe power path can produce misleading
numbers and hours of trial and error. Existing dashboards show values; they rarely understand the
actual wiring or prove that a proposed fix worked.

We built NeXus to make a physical prototype software-readable. The system knows the declared BOM,
pins, connections, electrical limits, firmware identity, live measurements, and every diagnostic
action. It behaves like a doctor for hardware: prevent unsafe setups, diagnose faults with evidence,
and verify recovery instead of declaring success too early.

## What it does

NeXus demonstrates three end-to-end paths on an ESP32-S3 motor platform:

1. **Prevent** — reject an unsafe configuration before actuation.
2. **Manual Diagnose** — combine the machine-readable wiring graph, live current-sensor/encoder telemetry,
   signal-health checks, and a NVIDIA Nemotron hypothesis to give a safe human repair procedure.
3. **Auto Heal** — route a bounded software-controllable correction through deterministic safety
   policy, execute it only when allowed, and require newer Before/After telemetry before recovery is
   accepted.

The React application provides a live system dashboard, searchable Hardware Graph, exact pin and
wire guide, readable ESP32 log, three-wheel drive monitor, AI Doctor conversation, diagnosis
timeline, Manual Treatment steps, Auto Treatment policy state, reconnect handling, and downloadable
session evidence.

## How we built it

- A versioned JSON Hardware-as-Code profile is the source of truth for the ESP32-S3, INA219, dual
  L298N drivers, three JGB37-520 encoder motors, power path, PS2 controller, pins, wiring, limits,
  transport, and telemetry fields.
- PlatformIO generates firmware constants from that profile. Firmware publishes strict telemetry
  v1 and starts in a fail-safe state with drive disabled.
- FastAPI validates and persists telemetry, watches serial signal health, streams realtime updates,
  builds grounded model context, runs a bounded diagnostic state machine, applies a default-deny
  safety policy, and stores audit events under one trace ID.
- NVIDIA Nemotron runs through Nebius Token Factory / AI Cloud using an OpenAI-compatible endpoint.
  Its structured output can rank hypotheses and propose an allowlisted next tool, but it cannot
  define safety limits or talk directly to the device.
- React and TypeScript consume the same contract names as firmware and backend. The UI never invents
  missing measurements and visibly distinguishes device, replay, and simulator sources.

## Architecture

`Hardware → Telemetry → Backend → Nemotron → Orchestrator → Safety Policy → Tool → Verify → UI`

The model proposes. Deterministic policy approves or rejects. Verify requires a fresh sample. All
steps emit schema-validated lifecycle events that the UI exposes as an audit timeline.

## Challenges we ran into

- A mismatched INA219/INA226 assumption produced plausible but wrong readings. We solved this with
  profile identity, firmware hash, sensor identity, and explicit compatibility checks.
- SDA/SCL faults can look like valid zeroes. Firmware and backend now distinguish a missing I2C
  acknowledgement, stale data, invalid reference combinations, and a genuinely powered-off rail.
- Current alone does not prove motor motion. Encoder evidence and fresh Before/After samples are
  required before a motor action can be verified.
- Physical control must fail safely. Browser actions remain read-only in the MVP; write tools are
  bounded, policy-gated, audited, and exercised only in supervised acceptance firmware.

## Accomplishments we are proud of

- One hardware profile drives firmware generation, backend validation, and frontend wiring UX.
- The four cross-service schemas share versioned field names and reject incompatible payloads.
- The demo works in a deterministic safe mode without pretending it is live AI or real hardware.
- Live model metadata, tool evidence, safety decisions, and verification events are visible without
  exposing secrets or chain-of-thought.
- Automated tests cover contracts, orchestration, safety, serial ingestion, UI behavior, firmware
  builds, and API load smoke tests.

## What we learned

The useful AI boundary is not direct control. It is grounded hypothesis generation inside a system
that already knows its hardware, enforces limits, records decisions, and verifies outcomes. Treating
wiring and hardware identity as code made the model more useful and the entire product easier to
debug.

## What's next

After the hackathon we plan to add certified hardware adapters, calibration workflows, richer
vibration/environment sensors, operator approvals for bounded write actions, and fleet-level trend
analysis. New boards will use adapters and versioned profiles rather than special cases in the UI.

## Built with

NVIDIA Nemotron, Nebius Token Factory / AI Cloud, Python, FastAPI, Pydantic, SQLite, WebSockets,
React, TypeScript, Vite, PlatformIO, ESP32-S3, INA219, L298N, JGB37-520 encoders, JSON Schema, pytest,
Vitest, k6, Docker, and GitHub Actions.

## Links to fill immediately before submission

- Public repository: `https://github.com/Little-Boy-z-NeXus/nexus-hardware-doctor`
- Demo video: `https://www.youtube.com/watch?v=ac33K71GrzQ`
- Optional live deployment: `[PASTE URL OR WRITE "Local physical demo"]`
