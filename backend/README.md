# nexus-backend

The backend owns telemetry validation, the hardware graph, deterministic checks, Nemotron reasoning, orchestration, safety policy, device tools, and the API consumed by the frontend.

## Current MVP state

Available now:

- FastAPI application and `/health` endpoint
- strict Python mirrors of all four v1 contracts
- JSON Schema and fixture validation
- automated tests and Ruff linting

Not implemented yet:

- telemetry ingest and persistence
- Nebius/Nemotron runtime calls
- diagnosis orchestration and tool execution
- WebSocket stream for the frontend

Those capabilities are separate backlog items. Do not mock them inside the production adapter without marking the data source.

## Prerequisites

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
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

## Environment configuration

The root [`.env.example`](../.env.example) is the canonical backend/device template.

| Variable | Required now | Purpose |
| --- | --- | --- |
| `NEXUS_ENV` | Yes | Runtime mode such as `development` |
| `NEXUS_NEBIUS_BASE_URL` | Later | Nebius API base URL |
| `NEXUS_NEBIUS_API_KEY` | Later | Secret API credential; never expose to frontend |
| `NEXUS_NVIDIA_MODEL` | Later | Selected NVIDIA/Nemotron model ID |
| `NEXUS_MQTT_URL` | Later | Device transport broker |
| `NEXUS_DEVICE_ID` | Yes | Device identity matching contract v1 |
| `NEXUS_MAX_PWM_PERCENT` | Yes | Backend safety ceiling; firmware clamps independently too |

FastAPI does not load the future integration variables yet. Keeping the template stable lets later tasks add adapters without renaming configuration.

## Run tests and lint

From the repository root:

```bash
ruff check backend scripts
python -m pytest backend/tests -q
python scripts/validate_contracts.py
```

Expected result: ten tests pass, including success and rejected-contract paths; four schemas and four fixtures validate; and all three stack mirrors contain the shared telemetry fields.

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
│   ├── __init__.py
│   ├── app.py          FastAPI entry point
│   └── contracts.py    Typed v1 contract mirrors
└── tests/
    ├── test_health.py
    ├── test_contracts.py
    └── test_contract_validation.py
```

Canonical JSON Schemas live in [`nexus-contracts/v1`](../nexus-contracts/v1/README.md). Python models mirror them but do not replace them.

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
- Nebius key appears in a log: revoke it, remove the log from shared artifacts, and follow [docs/security.md](../docs/security.md).
