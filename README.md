# NeXus Hardware Doctor

NeXus is an AI doctor for physical hardware. The hackathon MVP turns one ESP32 motor rig into a software-readable system that can prevent unsafe configurations, diagnose failures from telemetry, and safely heal software-controllable faults.

This repository targets the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) and intentionally supports one topology: GOOUUU Tech ESP32-S3-N16R8, INA226 with an R100 (0.1 Ω) shunt, L298N, one JGB37-520 12 V DC gearmotor with encoder, and a 12 V supply.

The INA226 `VBUS` input must be bridged to `VIN−` (the load side of the R100 shunt) so the application can read the 12 V motor bus.

## Current build status

| Area | What works now | Next integration |
| --- | --- | --- |
| Frontend | Realtime Dashboard/Hardware Graph, ESP32 live log, reconnect and human-readable fault cards | Connect AI Doctor to the same evidence stream |
| Backend | Persistent sessions/telemetry, serial live snapshots/logs, hardware context, configurable Nebius client, simulated diagnosis/policy/evaluation and Docker runbook | Verify live model calls and integrate serial evidence plus real commands |
| Firmware | Safe PWM clamp, strict telemetry v1, calibrated INA226 startup/error logs | Add authenticated command transport and encoder calibration |
| Contracts | Four frozen JSON Schemas, fixtures and migration enforcement | Change only through a reviewed migration note or v2 |

The three demo paths are `Prevent`, `Manual Diagnose`, and `Auto Heal`. Features that do not make one of those paths more reliable are out of scope until after the hackathon.

## Prerequisites

Install only the tools needed for the component you are working on:

| Tool | Version | Required for |
| --- | --- | --- |
| Git | 2.40+ | Everyone |
| Python | 3.11 | Backend, repository checks, contract checks |
| Node.js | 22 LTS | Frontend |
| PlatformIO CLI | Current stable | Firmware build/upload only |
| USB data cable and ESP32 driver | Board-dependent | Physical firmware upload only |

Confirm the main tools:

```bash
git --version
python --version
node --version
npm --version
```

## Windows: run by double-clicking

No command typing is required after the prerequisite applications are installed. Open the repository folder in File Explorer and double-click the appropriate `nexus-*.cmd` file:

| File | Action |
| --- | --- |
| `nexus-setup.cmd` | Install backend, frontend, and PlatformIO dependencies on the first run |
| `nexus-start-app.cmd` | Start backend/frontend, connect ESP32 serial, then open the realtime Hardware Graph |
| `nexus-stop-app.cmd` | Stop only this repository's backend and frontend processes |
| `nexus-start-backend.cmd` | Start only the API at `http://127.0.0.1:8000` |
| `nexus-start-frontend.cmd` | Start only the UI at `http://127.0.0.1:5173` |
| `nexus-upload-firmware.cmd` | Upload firmware through the GOOUUU ESP32-S3 built-in USB-JTAG interface |
| `nexus-monitor-firmware.cmd` | Standalone Serial Monitor; saves each session under `logs/device-monitor-*.log` |
| `nexus-run-firmware.cmd` | Upload firmware, open standalone Serial Monitor, and save the session under `logs/` |
| `nexus-check-project.cmd` | Run repository, backend, frontend, and firmware checks |

For the first use, double-click `nexus-setup.cmd` once. Normal operation then requires only `nexus-start-app.cmd`: the backend automatically finds the GOOUUU ESP32-S3 COM port, writes `logs/hardware-live-*.ndjson`, and streams the same log to Hardware Graph in realtime. Do not open PlatformIO Serial Monitor at the same time because only one process can own the COM port. Close the two server windows or use `nexus-stop-app.cmd` to stop the application. Keep motor power disconnected while uploading firmware.

For the U05 physical acceptance only, double-click `nexus-run-hardware-baseline.cmd` and
remain beside the rig for the complete 30-minute test. It validates the 12 V/INA226/current
path, stops on unsafe readings, writes local evidence, and restores normal safe firmware.
Follow [`docs/hardware-baseline-u05.md`](docs/hardware-baseline-u05.md); never leave the motor
running unattended.

## Clone and validate the repository

```bash
git clone https://github.com/Little-Boy-z-NeXus/nexus-hardware-doctor.git
cd nexus-hardware-doctor
python scripts/validate_repo.py
```

The repository is private during the build phase, so GitHub may ask you to authenticate. Do not place a token in the clone URL or commit it to a file.

## Quick start: backend

Run these commands from the repository root.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\backend[dev]"
Copy-Item .env.example .env
uvicorn nexus_backend.app:app --reload
```

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate again. This changes policy only for the current process.

### macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
cp .env.example .env
uvicorn nexus_backend.app:app --reload
```

Open:

- API health: <http://127.0.0.1:8000/health>
- Live hardware snapshot: <http://127.0.0.1:8000/api/v1/live>
- Latest valid telemetry: <http://127.0.0.1:8000/api/v1/telemetry>
- Interactive API docs: <http://127.0.0.1:8000/docs>

The backend exposes device registration, telemetry/history, WebSocket streaming, diagnosis session records, audit events, hardware models and bounded context. SQLite retains configuration and data across restarts. See the [backend API guide](docs/backend-api.md).

To exercise H02 and H03 without a board, keep the backend running and open another activated terminal:

```bash
python -m nexus_backend.mock_device --count 60
```

Open <http://127.0.0.1:8000/monitor> while the simulator runs. It displays source-labeled telemetry from the persistent per-device backend stream. The React Dashboard and Hardware Graph use the separate serial live snapshot API; simulator registration does not replace their hardware readings.

The backend owns the serial port, rejects malformed/`nan` packets, persists timestamped NDJSON entries under `logs/`, and streams complete live snapshots over `/api/v1/live/ws`. These read-only live endpoints coexist with the SQLite device/session APIs. Live model acceptance, transfer of serial snapshots into diagnosis history and physical command integration remain pending.

The [diagnosis lab](http://127.0.0.1:8000/doctor-lab) runs the preemptive H01/H04–H08 software. Simulation requires no model key. Live mode requires configured Nebius access and explicit enablement; its tools are read-only. Real model/physical acceptance has not been claimed. See the [H resource checklist](docs/h-resource-checklist.md), [model guide](docs/h01-h04.md), [orchestration/policy guide](docs/h05-h06.md), [evaluation guide](docs/h07-evaluation.md), and [Docker runbook](docs/h08-runbook.md).

Run all synthetic diagnosis checks with `python -m nexus_backend.evaluation --output artifacts/h07-evaluation.json`. This scores the deterministic mock planner, not Nemotron or real hardware. `docker compose up --build -d` provides an isolated backend with persistent data and no model access enabled by default.

## Quick start: frontend

Open a second terminal at the repository root:

### Windows PowerShell

```powershell
npm --prefix frontend ci
Copy-Item frontend\.env.example frontend\.env.local
npm --prefix frontend run dev
```

### macOS or Linux

```bash
npm --prefix frontend ci
cp frontend/.env.example frontend/.env.local
npm --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. Available routes:

- `/dashboard`
- `/hardware`
- `/doctor`

Dashboard and Hardware Graph use live API data and show `--` while no valid hardware packet exists; they do not invent presentation values. Open `/hardware` for the realtime terminal and fault-resolution guide.

## Quick start: firmware

PlatformIO is optional unless you are working with the ESP32:

```bash
python -m pip install platformio
pio device list
pio run --project-dir firmware
```

Connect the board with a USB data cable, identify its port, then upload and monitor.

Windows example:

```powershell
pio run --project-dir firmware --target upload
pio device monitor --port COM8 --baud 115200
```

macOS/Linux example:

```bash
pio run --project-dir firmware --target upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

The upload uses built-in USB-JTAG and does not need a COM-port argument. Replace the monitor port with the value returned by `pio device list`; the Windows click launcher detects it automatically. Read [firmware/README.md](firmware/README.md) before powering the motor circuit.

## Run all software quality checks

Install backend development dependencies and frontend dependencies first, then run from the repository root:

```bash
python scripts/validate_repo.py
python scripts/validate_contracts.py
ruff check backend scripts
python -m pytest backend/tests -q
npm --prefix frontend run check
k6 run nexus-k6-tests/smoke.js
```

The k6 command requires both local applications to be running. These are the same core checks enforced by GitHub Actions. Hardware upload and the longer k6 baseline are deliberately separate because CI has no physical ESP32 and should remain fast.

Run the small manual load profile before a demo or release:

```bash
k6 run nexus-k6-tests/load.js
```

See [nexus-k6-tests/README.md](nexus-k6-tests/README.md) for installation, environment overrides, workload, and pass thresholds.

## Environment variables

Copy templates locally; never edit the templates with real credentials.

- Backend/device template: [`.env.example`](.env.example) → `.env`
- Frontend template: [`frontend/.env.example`](frontend/.env.example) → `frontend/.env.local`

Important rules:

- Never expose `NEXUS_NEBIUS_API_KEY` through a `VITE_` variable.
- Never commit `.env`, `.env.local`, Wi-Fi credentials, device tokens, or raw private logs.
- The frontend API default is `http://127.0.0.1:8000`; override it with `VITE_API_BASE_URL` only when required.

## Repository layout

```text
nexus-hardware-doctor/
├── firmware/          ESP32 telemetry and approved device actions
├── backend/           FastAPI, contracts, reasoning, policy and APIs
├── frontend/          Dashboard, Hardware Graph and AI Doctor UI
├── nexus-contracts/   Frozen schemas, fixtures and migration notes
├── nexus-k6-tests/    CI smoke test and manual MVP load baseline
├── docs/              Architecture, scope, ownership and security decisions
├── scripts/           Repository and contract validators
└── .github/           CI and contribution templates
```

Read the component guide before changing an area:

- [Firmware guide](firmware/README.md)
- [Backend guide](backend/README.md)
- [Frontend guide](frontend/README.md)
- [Contract guide](nexus-contracts/README.md)
- [k6 performance test guide](nexus-k6-tests/README.md)
- [Documentation index](docs/README.md)
- [Validation scripts](scripts/README.md)

Every project root and future split repository must use a lowercase `nexus-<name>` name. Package names follow the same prefix where the ecosystem permits it.

## Team ownership

| Area | Primary owner | Review partner |
| --- | --- | --- |
| Product scope, integration, release | Hiếu | Hoàng |
| AI reasoning, backend, Nebius integration | Hoàng | Hiếu |
| Firmware, telemetry, automated test rig | Nguyễn | Hoàng |
| Frontend and scoped implementation | Nguyên | Hiếu |

See [docs/ownership.md](docs/ownership.md) for handoff rules.

## Branch and pull-request workflow

1. Pull the latest `main`.
2. Create `feat/<issue>-short-name`, `fix/<issue>-short-name`, `docs/<issue>-short-name`, or `chore/<issue>-short-name`.
3. Make the smallest change that satisfies one backlog item.
4. Run the relevant checks locally.
5. Open a pull request, link the backlog ID, and request the area's review partner.
6. Keep `main` demoable and never merge with a failing CI run.

Schema v1 changes require a new note under `nexus-contracts/migrations/` in the same change. See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete agreement.

## Common setup problems

- `python` is not 3.11: use `py -3.11` on Windows or install Python 3.11 explicitly.
- `npm ci` rejects the lockfile: use Node 22 and do not hand-edit `package-lock.json`.
- Port 5173 or 8000 is busy: stop the existing process or pass a different supported port.
- ESP32 is not listed: use a USB data cable, install the board's USB-UART driver, and reconnect it.
- Firmware upload cannot open the port: close every serial monitor before uploading.
- UI says the COM port is busy: close `pio device monitor`, Arduino Serial Monitor, or any other serial app; the backend retries automatically.
- Contract validation fails: do not patch a consumer independently; fix the canonical contract/fixture or add a versioned migration.

## Project links

- [MVP scope and team backlog](https://docs.google.com/spreadsheets/d/1EOCmOg-qVQ_2OJV1DkeH9ULjkR7oT8kNMNGyrTKTUFs/edit?gid=9060801#gid=9060801)
- [Hackathon page](https://nebiusglobalaihackathon.devpost.com/)
- [Latest CI runs](https://github.com/Little-Boy-z-NeXus/nexus-hardware-doctor/actions)

## License

Licensed under the [MIT License](LICENSE).
