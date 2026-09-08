# nexus-k6-tests

This folder contains protocol-level performance checks for the NeXus MVP. The scripts never issue hardware control commands; they only read the backend health endpoint and frontend routes.

## Test profiles

| Script | Purpose | Default workload | Intended use |
| --- | --- | --- | --- |
| `smoke.js` | Verify availability, response contract and basic latency | 1 virtual user, 1 iteration | Local checks and every CI run |
| `load.js` | Establish a small hackathon demo baseline | Ramp from 0 to 5 virtual users over 25 seconds | Manual run before demos or releases |

## Prerequisites

Start the applications in two separate terminals from the repository root.

Terminal 1:

```powershell
uvicorn nexus_backend.app:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
npm --prefix frontend run dev
```

Install k6 with the method for your operating system:

- Windows: `winget install k6 --source winget`
- macOS: `brew install k6`
- Linux: follow the official package instructions at <https://grafana.com/docs/k6/latest/set-up/install-k6/>

## Run the tests

From the repository root:

```bash
k6 run nexus-k6-tests/smoke.js
k6 run nexus-k6-tests/load.js
```

Override the targets for a deployed environment:

```powershell
$env:NEXUS_API_BASE_URL = "https://api.example.com"
$env:NEXUS_WEB_BASE_URL = "https://app.example.com"
k6 run nexus-k6-tests/smoke.js
```

```bash
NEXUS_API_BASE_URL=https://api.example.com \
NEXUS_WEB_BASE_URL=https://app.example.com \
k6 run nexus-k6-tests/smoke.js
```

Only run load tests against environments owned by the team and sized for the configured traffic. The default profile is deliberately small; increase it only after agreeing on a target SLO and environment capacity.

## Pass criteria

The smoke test requires every check to pass, no failed HTTP requests, backend p95 below 500 ms, and frontend p95 below 1 second. The manual baseline uses tighter error-rate and latency thresholds; k6 exits non-zero when any threshold fails.
