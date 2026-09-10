# nexus-backend

The backend owns telemetry validation, the hardware graph, deterministic checks, Nemotron reasoning, orchestration, safety policy, device tools, and the API consumed by the frontend.

## Current MVP state

Available now:

- FastAPI device registration, telemetry ingest/history, WebSocket streaming and `/health`
- persistent SQLite device configuration, diagnosis session records and telemetry audit logs
- raw canonical validation plus semantic hardware graph checks
- bounded, source-labeled context for the later model adapter
- a simulated device producer and a browser telemetry monitor at `/monitor`
- GOOUUU ESP32-S3 serial auto-detection and reconnect
- timestamped session logs under `logs/hardware-live-*.ndjson`
- `/api/v1/live` snapshot plus `/api/v1/live/ws` realtime stream
- deterministic Vietnamese diagnostics for the fixed INA226 R100/L298N/motor rig
- strict Python contract mirrors, JSON Schema/fixture validation, automated tests and Ruff linting

Prepared for H01/H04–H08:

- a strict, configurable async Nebius/Nemotron client and a separately labelled mock planner
- bounded read/plan/policy/execute/verify orchestration with an isolated simulator
- persistent diagnosis outcomes/events and a browser lab at `/doctor-lab`
- synthetic evaluation, container packaging and a reproducible runbook

Still awaiting live acceptance/integration:

- successful real Nebius/Nemotron runtime proof
- actual device command transport and verified physical actions
- transfer of serial snapshots into the persistent per-device history and diagnosis context
- cloud telemetry storage and automatic retention policies

Those capabilities are separate backlog items. Simulated/replayed samples carry an explicit source and do not prove physical hardware behavior. See the [H02/H03 API guide](../docs/backend-api.md) for endpoint semantics, limitations and acceptance checks.

See [H resources and completion gates](../docs/h-resource-checklist.md) for the remaining inputs and [H08 runbook](../docs/h08-runbook.md) for installation, live opt-in and controlled failures. This preemptive software does not mark H01/H04–H08 complete.

## Prerequisites

On Windows, no terminal commands are required: double-click `nexus-start-backend.cmd` in the repository root. The launcher creates or repairs the backend environment automatically. Use `nexus-start-app.cmd` to start both backend and frontend.

- Python 3.11
- Git
- A cloned `nexus-hardware-doctor` repository

All commands below start from the repository root unless the heading says otherwise.

## Install on Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\backend[dev]"
Copy-Item .env.example .env
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

The policy change applies only to the current PowerShell process.

## Install on macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./backend[dev]"
cp .env.example .env
```

## Run the API

From the repository root with the virtual environment active:

```bash
uvicorn nexus_backend.app:app --reload --host 127.0.0.1 --port 8000
```

Verify it:

```bash
curl http://127.0.0.1:8000/health
```

Expected payload:

```json
{
  "status": "ok",
  "service": "nexus-backend",
  "version": "0.1.0"
}
```

Browser links:

- Health: <http://127.0.0.1:8000/health>
- Live snapshot: <http://127.0.0.1:8000/api/v1/live>
- Latest valid telemetry: <http://127.0.0.1:8000/api/v1/telemetry>
- Recent serial log: <http://127.0.0.1:8000/api/v1/logs>
- Active diagnostics: <http://127.0.0.1:8000/api/v1/diagnostics>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Browser telemetry monitor: <http://127.0.0.1:8000/monitor>

In another activated terminal, generate explicitly simulated telemetry:

```bash
python -m nexus_backend.mock_device --count 60 --interval 1
```

The monitor receives the actual backend WebSocket stream. It supports device selection, reconnection and stale-data indication without requiring a board or model credential.

The browser subscribes to `ws://127.0.0.1:8000/api/v1/live/ws`. The first message is a complete snapshot; subsequent messages replace it, which makes reconnect deterministic.

## Environment configuration

The root [`.env.example`](../.env.example) is the canonical backend/device template.

| Variable | Required now | Purpose |
| --- | --- | --- |
| `NEXUS_DB_PATH` | No | SQLite path; defaults to `artifacts/nexus.sqlite3` |
| `NEXUS_CORS_ORIGINS` | No | Allowed browser origins; defaults to local frontend port 5173 |
| `NEXUS_ENV` | Later | Reserved environment label |
| `NEXUS_NEBIUS_BASE_URL` | Later | Nebius API base URL |
| `NEXUS_NEBIUS_API_KEY` | Later | Secret API credential; never expose to frontend |
| `NEXUS_NVIDIA_MODEL` | Later | Selected NVIDIA/Nemotron model ID |
| `NEXUS_MQTT_URL` | Later | Device transport broker |
| `NEXUS_DEVICE_ID` | Yes | Device identity matching contract v1 and the firmware default |
| `NEXUS_SERIAL_ENABLED` | Yes | Set `false` only for a software-only run |
| `NEXUS_SERIAL_PORT` | No | Leave blank to auto-detect `303A:1001`; set `COM8` only to force one port |
| `NEXUS_LOG_ENABLED` | Yes | Keep `true` to persist every backend/firmware log entry locally |
| `NEXUS_LOG_DIR` | Yes | Log directory; relative paths resolve from the repository root |
| `NEXUS_MAX_PWM_PERCENT` | Yes | Backend safety ceiling; firmware clamps independently too |

The server reads `NEXUS_DB_PATH` and `NEXUS_CORS_ORIGINS` from its process environment. It does not automatically read `.env`; use Uvicorn's `--env-file` option if needed. Keep the same database path across restarts. Future model/policy variables remain reserved. Local development has no API authentication; use the loopback binding shown above.

## Run tests and lint

From the repository root:

```bash
ruff check backend scripts
python -m pytest backend/tests -q
python scripts/validate_contracts.py
```

Tests cover contract rejection, persistent restart, device isolation, exact retries, atomic audit writes, WebSocket reconnect/order, hardware metadata, context bounds, simulated payloads, serial parsing/diagnostics, API coexistence, lifecycle cleanup and idle disconnect. Four schemas and four fixtures validate, and all three stack mirrors retain the shared telemetry fields.

Run one test file while developing:

```bash
python -m pytest backend/tests/test_contracts.py -q
python -m pytest backend/tests/test_contract_validation.py -q
python -m pytest backend/tests/test_health.py -q
```

## Package structure

```text
backend/
├── pyproject.toml
├── src/nexus_backend/
│   ├── app.py             API routes, lifespan and WebSocket streams
│   ├── contracts.py       Typed v1 contract mirrors
│   ├── serial_bridge.py   COM reader, live log and deterministic diagnostics
│   ├── store.py           SQLite devices, telemetry, sessions and audit
│   ├── validation.py      Canonical raw JSON validation
│   ├── hardware.py        Hardware graph semantic validation
│   ├── context.py         Bounded source-labelled model context
│   ├── provider.py        Nebius and simulated model providers
│   ├── diagnosis.py       Diagnosis proposal validation
│   ├── orchestrator.py    Bounded diagnosis execution flow
│   ├── policy.py          Deterministic safety policy
│   ├── tool_adapter.py    Isolated device-tool adapter
│   ├── runtime.py         Runtime configuration and limits
│   ├── evaluation.py      Synthetic evaluation runner
│   ├── mock_device.py     Explicit simulator CLI
│   ├── prompts/
│   └── static/
│       ├── monitor.html
│       └── doctor-lab.html
└── tests/
    ├── test_contracts.py
    ├── test_serial_bridge.py
    ├── test_store.py
    ├── test_device_api.py
    ├── test_hardware.py
    ├── test_context.py
    ├── test_provider.py
    ├── test_orchestrator.py
    ├── test_policy.py
    └── test_evaluation.py
```

Canonical JSON Schemas live in [`nexus-contracts/v1`](../nexus-contracts/v1/README.md). Python models mirror them but do not replace them. The built wheel includes canonical schemas and fixtures directly from that directory so validation and the simulator also work outside a checkout.

## Adding backend code

- Keep modules under the `nexus_backend` package.
- Keep transport, model provider, orchestration, safety policy, and device tool code in separate modules.
- Validate external payloads before business logic.
- Use `trace_id` across diagnosis, tool, and verification events.
- Never allow the model provider to bypass deterministic safety checks.
- Add tests for every new endpoint, policy rule, and failure path.

## Common problems

- `ModuleNotFoundError: nexus_backend`: activate the correct virtual environment and reinstall with `python -m pip install -e ".\backend[dev]"` on Windows or `-e "./backend[dev]"` on Unix.
- Port 8000 is busy: run `uvicorn nexus_backend.app:app --reload --port 8001` and update `VITE_API_BASE_URL` for the frontend.
- Contract validation fails: compare the payload with the matching fixture; do not loosen the backend model alone.
- COM port is busy: close PlatformIO/Arduino Serial Monitor. The backend and a CLI monitor cannot read the same Windows COM port simultaneously.
- Board is connected but no data arrives: press RESET, confirm baud 115200, and upload the current NeXus firmware.
- Nebius key appears in a log: revoke it, remove the log from shared artifacts, and follow [docs/security.md](../docs/security.md).
