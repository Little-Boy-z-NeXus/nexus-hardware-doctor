# H08 final release acceptance

Accepted on 12 September 2026 for the local/container hackathon MVP release path.

## Evidence

- The backend image installs the built package into a pinned Python 3.11 base image, runs as
  non-root UID 10001, disables serial discovery, binds through the host loopback mapping and uses
  an isolated SQLite data path.
- CI builds the image from a fresh checkout and empty database, then checks health, both API
  families, device registration, canonical telemetry ingest and a complete offline diagnosis with
  persisted trace events.
- The same package is started with no Nebius credential and live mode disabled. A live diagnosis
  must return the bounded HTTP 503 message `Live model access is not enabled and configured`.
- `/api/diagnosis/capabilities` contains no credential, prompt or provider-body fields. The browser
  lab exposes a retry path and renders error/model text through `textContent`, never `innerHTML`.
- Simulation remains explicitly labelled `mock`, performs no provider call and keeps physical
  commands disabled. It is a controlled offline demo fallback, not a silent substitute for a live
  Nemotron result.
- Provider authentication, refusal, timeout, invalid-response and rate-limit behavior remains
  covered by mocked unit tests. The locked live-model evaluation and physical evidence used by
  H04-H07 are independently recorded; this release probe makes no paid API call.

## Repeat

On Windows, start Docker Desktop and double-click `nexus-run-h08-acceptance.cmd`. The generated
machine-readable result is local and ignored at
`artifacts/H08/nexus-h08-release-acceptance.json`.

CI runs the same runtime probe against the installed image. The task deliberately claims a
reproducible local/container MVP, not public hosting, multi-user authentication or production
reliability.
