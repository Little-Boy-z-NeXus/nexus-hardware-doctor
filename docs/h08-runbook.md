# H08 reproducible backend runbook

This is preemptive release work. A local/container demonstration and controlled failure behavior can be checked now. H08's full release acceptance remains dependent on H01–H07 and their live/physical evidence. The task permits this reproducible runbook instead of a hosted URL.

## Start without credentials

From the repository root with Docker running:

```bash
docker compose up --build -d
docker compose exec backend python -m nexus_backend.mock_device --count 60
```

While the simulator is producing samples, open <http://127.0.0.1:8000/monitor> or <http://127.0.0.1:8000/doctor-lab>. Select Simulation to exercise diagnosis without API calls. Persisted simulator measurements older than five seconds cannot authorize a new simulated write; restart the simulator for fresh samples.

The container runs as user `nexus`, publishes only on host loopback, has a health check, and retains its SQLite database in the `nexus-data` volume. `docker compose down` stops the service without deleting that volume. No hardware USB device, physical adapter or public ingress is configured.

The upstream USB telemetry bridge and its `/api/v1/live` routes coexist with the persisted H APIs in one application. Docker/Compose explicitly disables serial discovery; direct Python startup follows `NEXUS_SERIAL_ENABLED` (upstream default: enabled). Use `NEXUS_SERIAL_ENABLED=false` for a software-only local run. Serial snapshots are read-only and do not automatically register devices or populate H diagnosis history; that integration still needs verified device identity and hardware configuration. CI starts the installed container and checks both API families as well as the packaged evaluation.

### Upgrading an existing demo database

The current GOOUUU ESP32-S3/JGB37 example changes the hardware model and wiring while retaining the example device ID. A database containing the earlier example correctly rejects its replacement with HTTP 409: device configuration is immutable. Preserve that history and register the updated simulator under a distinct ID:

```bash
docker compose exec backend python -m nexus_backend.mock_device --device-id nexus-demo-esp32-s3 --count 60
```

Use that ID in the lab. A fresh database needs no override. Agree on real-device identity/configuration migration with the firmware integration owner before connecting changed hardware; do not delete history to bypass the conflict.

## Regression and clean environment

```bash
docker compose exec backend python -m nexus_backend.evaluation --output /tmp/nexus-evaluation.json
docker compose cp backend:/tmp/nexus-evaluation.json ./artifacts/nexus-evaluation.json
```

Create the local `artifacts` directory before copying if it does not exist. The report separates deterministic simulation results from unperformed live/physical acceptance. It does not measure Nemotron accuracy in mock mode.

For a Python environment instead of Docker:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c backend/constraints.txt -e './backend[dev]'
python -m pytest backend/tests -q
python -m nexus_backend.evaluation --output artifacts/nexus-evaluation.json
python -m uvicorn nexus_backend.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

The image's Python base is pinned by digest. `backend/constraints.txt` records tested dependency versions for both runtime and development. Update those constraints deliberately and rerun the checks. Canonical schemas/fixtures, prompt, dataset and HTML pages ship inside the installed backend package.

## Enable the real model only when ready

Store these values in the ignored root `.env`, keeping the key out of chat/repository:

```dotenv
NEXUS_ENABLE_LIVE_MODEL=true
NEXUS_NEBIUS_BASE_URL=<the supported Nebius HTTPS v1 endpoint>
NEXUS_NEBIUS_API_KEY=<your secret>
NEXUS_NVIDIA_MODEL=<your supported NVIDIA model ID>
```

Recreate the container with `docker compose up -d --force-recreate`, then explicitly choose Live model in the lab. For direct Python startup, add `--env-file .env` to the Uvicorn command; the application does not automatically read that file. Never print a resolved Compose configuration containing credentials.

The capability endpoint `/api/diagnosis/capabilities` reports only whether live configuration/enablement is present, not its secret values. Live mode has read-only backend tools. Physical writes remain disabled even with a working model key; N03 integration and verified operating limits are separate prerequisites.

## Controlled failures and observability

- Missing/disabled model configuration returns a clear 503 response, with no paid call or silent mock fallback.
- Provider authentication, refusal, rate limit, invalid response and timeout paths are tested with mocked HTTP responses. Provider errors contain fixed messages and no raw response/credentials.
- Diagnosis admission is bounded to ten runs per minute and two simultaneous runs per process. Rejected requests include a retry delay. Each run also has bounded steps, tool/model retries and an outer 30-second deadline.
- Completed and failed outcomes and their canonical trace events persist under their owning device/session. `/api/devices/{id}/sessions/{session_id}/events` returns that run's events.
- `nexus.diagnosis` emits JSON summaries (trace, mode, status, step count and duration) without symptoms, prompts, telemetry or provider bodies. Uvicorn access logs are disabled in the container.
- The lab displays failures and lets the user retry. It uses text rendering for model output, avoiding HTML interpretation.

These are local controls; public multi-user authentication and distributed rate limiting are not claimed. Real model-outage rehearsal with the final demo still belongs to release acceptance after integration.

## Implementation references

[Docker build guidance](https://docs.docker.com/build/building/best-practices/) and [Compose environment configuration](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).
