# H02/H03 backend API

The local backend provides durable device configuration, telemetry, diagnosis session records and audit events. The hardware loader validates the frozen v1 document and prepares bounded context for a later model adapter. It does not call Nemotron, execute device commands or infer physical safety from missing electrical metadata.

The H02/H03 endpoints described below retain that behavior. Additional preemptive H endpoints now support bounded diagnosis: `GET /api/diagnosis/capabilities`, `POST /api/devices/{device_id}/diagnoses` with `{symptom, mode: "mock" | "live", max_steps: 1..8}`, and `GET /api/devices/{device_id}/sessions/{session_id}/events`. The POST returns the persisted session plus `result`; expected provider/tool failures are saved with a non-success status. Mock mode requires a registered simulator. Live mode requires explicit environment enablement and configuration, and only reads context. Neither mode controls physical hardware. See the [runbook](h08-runbook.md); `/doctor-lab` demonstrates these endpoints without completing the React frontend backlog.

## Run the software demonstration

From the repository root, with the backend installed in an activated environment:

```bash
uvicorn nexus_backend.app:app --host 127.0.0.1 --port 8000
```

In another activated terminal:

```bash
python -m nexus_backend.mock_device --count 60 --interval 1
```

Open <http://127.0.0.1:8000/monitor>. The browser receives actual WebSocket messages carrying explicitly simulated measurements. It shows source, connection state, stale data, voltage, current, PWM and driver state. A simulation is not evidence of motor movement or hardware health. Reconnect restores the latest persisted sample, then streams new samples. To demonstrate multiple devices, rerun the simulator with `--device-id nexus-second`.

The producer stops after the requested sample count. Restarting it generates new sample IDs, so resetting its sequence to zero does not collide with earlier runs. `--fixtures PATH` accepts a directory containing the canonical example filenames. `--base-url` changes the backend origin.

## Configuration and persistence

The read-only serial routes `/api/v1/live`, `/api/v1/telemetry`, `/api/v1/logs`,
`/api/v1/diagnostics` and `/api/v1/live/ws` coexist with the persistent `/api/devices`
routes in one application. Serial snapshots and NDJSON logs are separate from
SQLite telemetry/session records; receiving serial data does not register a device
or overwrite stored simulator data. Both WebSocket families use the configured
origin policy. An idle live client is removed when it disconnects.

Each application owns its bridge, live subscribers and database connection. The
exported server starts/stops the bridge with the database lifespan and follows
`NEXUS_SERIAL_ENABLED`; set it to `false` for development without hardware access.
`create_app(...)` disables serial access by default for isolated consumers/tests;
pass `serial_enabled=None` to use the environment or inject a bridge explicitly.
Importing the application alone does not open USB or SQLite. Live snapshots and
health remain readable before lifespan startup; persistent routes require it.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NEXUS_DB_PATH` | `artifacts/nexus.sqlite3` | SQLite path, relative to the server working directory |
| `NEXUS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed to call the API |

Set variables in the launching environment, or pass `--env-file` to Uvicorn for a separately managed file. The application does not automatically load `.env`. Keep the same database path after restarting. SQLite stores device configuration, hardware documents, telemetry, associated audit events and session records. Runtime artifacts are ignored by Git. Queries return bounded windows; this MVP does not implement automatic retention/deletion.

This is a local development API with no authentication. Bind it to loopback as shown above. Device IDs isolate records logically; they are not authorization credentials. Network deployment and authenticated device transport are separate tasks.

## HTTP endpoints

Interactive documentation: <http://127.0.0.1:8000/docs>. Machine-readable definition: `/openapi.json`.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Process health |
| POST | `/api/devices` | Register `{hardware_model, display_name, source}` |
| GET | `/api/devices` | List registered devices (maximum 1000) |
| GET | `/api/devices/{device_id}` | Read one device's configuration |
| GET | `/api/devices/{device_id}/hardware-model` | Read its validated v1 hardware document |
| POST | `/api/devices/{device_id}/telemetry` | Ingest a canonical v1 sample; persist an audit event atomically |
| GET | `/api/devices/{device_id}/telemetry` | Read the newest sample by receive order |
| GET | `/api/devices/{device_id}/telemetry/history?limit=20` | Latest 1–200 samples, oldest to newest by receive order |
| POST | `/api/devices/{device_id}/sessions` | Store `{symptom}` and generate session/trace IDs; status stays `created` |
| GET | `/api/devices/{device_id}/sessions?limit=50` | Latest 1–100 session records |
| GET | `/api/devices/{device_id}/sessions/{session_id}` | Read a session only under its owning device |
| GET | `/api/devices/{device_id}/events?limit=100` | Latest 1–200 telemetry audit events |
| POST | `/api/devices/{device_id}/context` | Build context from `{symptom, max_samples: 10}` (1–20 samples) |

Registration `source` is `device`, `simulator` or `replay`. Telemetry must match the registered device, hardware-model ID and source. A repeated identical registration is accepted; a different configuration for an existing ID returns 409. Explicit configuration updates are not implemented.

New telemetry returns 201 with `{sample, event_id, inserted: true}`. An identical retry of a device/sample ID returns 200 and the original audit event with `inserted: false`; a different payload using that ID returns 409. Canonical data is validated before storage without string/number coercion. Invalid contracts return 422 with bounded `{path, message}` details; `path` is a JSON Pointer, with an empty string denoting the document root. Unknown devices/sessions and unavailable latest telemetry return 404. Histories for registered devices with no data return empty arrays.

## WebSocket protocol

Connect to `ws://127.0.0.1:8000/api/devices/{device_id}/telemetry/stream`. The server first sends the latest stored sample if present, then every new sample in persisted receive order:

```json
{"type": "telemetry", "sample": {"schema_version": "1.0.0", "...": "full v1 sample"}}
```

The abbreviated object above describes the envelope; `sample` is the complete canonical document in actual messages. An idle connection receives `{"type":"heartbeat"}` every 15 seconds. Heartbeats do not indicate that measurements are fresh. Unknown devices and disallowed browser origins are rejected with policy code 1008. The monitor uses the same origin; configured frontend origins are also allowed.

The stream polls durable receive cursors every 250 ms, reading up to 100 samples per batch. Device sequence or clock resets do not reorder received data. Reconnecting delivers the latest snapshot rather than replaying every sample missed while offline; the history endpoint provides a bounded recent window.

## Hardware validation and context

The loader checks the canonical schema, formats, finite numeric values, unique component/pin/connection IDs, wiring endpoints and nonblank metadata. Context contains the symptom, declared topology and safety limits, declared sensors, implemented read operations, recent matching samples, source labels and missing-metadata warnings.

Only `get_hardware_graph` and `get_telemetry` are advertised as available backend read operations. Firmware capabilities in a hardware document do not imply that a runnable command adapter exists. Context performs no model call. Text from symptoms and declared hardware remains data for any future model prompt.

U07 may set `require_fresh_read=true` on a live diagnosis. This mode is rejected unless the
registered source is `device` and `NEXUS_SERIAL_DEVICE_ID` explicitly binds the same device.
The first model plan receives no cached telemetry, so a passing run must select the
policy-approved `get_telemetry` tool and ground its next hypothesis in the new serial sample.
The result stores allowlisted model-call metadata for audit; prompts, provider bodies and secrets
are never included.

The frozen v1 schema has no per-pin electrical ratings or maximum bus voltage, and its example has no explicit supply component. Context reports these gaps rather than inventing ratings. A null device timestamp remains unknown. Histories preserve receipt order even when device clocks move backward or sequence counters reset; no age or boot identity is inferred from those counters.

Canonical schemas and fixtures are included in the backend wheel directly from `nexus-contracts/v1`, with no independently maintained schema copy. H02/H03 do not modify frozen schemas.

## Verification

```bash
pytest backend/tests -q
ruff check backend scripts
python scripts/validate_repo.py
python scripts/validate_contracts.py
```

Tests cover database reopen, two-device isolation, idempotent ingest, atomic audit writes, raw contract rejection, WebSocket ordering and reconnect, bounded context, missing metadata and simulator payloads. The monitor provides the browser check without requiring the G02 React client work.
