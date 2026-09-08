# NeXus Hardware Doctor

NeXus is an AI doctor for physical hardware. The hackathon MVP turns one ESP32 motor rig into a software-readable system that can prevent unsafe configurations, diagnose failures from telemetry, and safely heal software-controllable faults.

## MVP status

This repository is the shared foundation for the Nebius x NVIDIA Global AI Hackathon build. The scope is intentionally limited to one hardware topology:

- ESP32 DevKit V1
- INA219 voltage/current sensor
- L298N motor driver
- One 6–12 V DC motor and a 12 V supply

The three required demo paths are `Prevent`, `Manual Diagnose`, and `Auto Heal`. Anything that does not make one of those paths more reliable is deferred until after the hackathon.

## Repository layout

```text
nexus-hardware-doctor/
├── firmware/   ESP32 telemetry and approved device actions
├── backend/    hardware model, Nemotron orchestration, policy, and APIs
├── frontend/   health dashboard, chat, telemetry, and action timeline
├── nexus-contracts/ frozen v1 schemas, fixtures, and migration notes
├── docs/       architecture, ownership, workflow, and MVP decisions
└── scripts/    repository and contract validation used by CI
```

Every project root and future split repository must use a lowercase `nexus-<name>` name. Package names follow the same prefix where the ecosystem permits it.

## Team ownership

| Area | Primary owner | Review partner |
| --- | --- | --- |
| Product scope, integration, release | Hiếu | Hoàng |
| AI reasoning, backend, Nebius integration | Hoàng | Hiếu |
| Firmware, telemetry, automated test rig | Nguyễn | Hoàng |
| Frontend and scoped implementation tasks | Nguyên | Hiếu |

Detailed boundaries and handoff rules are in [docs/ownership.md](docs/ownership.md).

## Start here

1. Clone the repository and create a branch from `main`.
2. Copy `.env.example` to `.env`; never commit credentials.
3. Read [docs/mvp-scope.md](docs/mvp-scope.md) and pick an item from the [shared backlog](docs/backlog.md).
4. Run the foundation check before opening a pull request:

   ```bash
   python scripts/validate_repo.py
   ```

The frozen cross-stack interface is documented in [nexus-contracts/v1](nexus-contracts/v1/README.md) and [docs/architecture.md](docs/architecture.md). After installing backend development dependencies, validate it with `python scripts/validate_contracts.py`.

Component-specific setup lives in each component README:

- [Firmware](firmware/README.md)
- [Backend](backend/README.md)
- [Frontend](frontend/README.md)

## Working agreement

- `main` must stay demoable.
- Use `feat/<issue>-short-name`, `fix/<issue>-short-name`, `docs/<issue>-short-name`, or `chore/<issue>-short-name`.
- Open a focused pull request and request the review partner for the affected area.
- Never commit API keys, Wi-Fi credentials, device tokens, or raw private logs.
- A change is done only when its acceptance test and relevant documentation pass.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete branch and pull-request convention.

## Hackathon delivery checklist

- A real NVIDIA model call runs through Nebius Token Factory or Nebius AI Cloud.
- The agent returns structured diagnostic JSON and the runtime stores a redacted evidence log.
- Safety policy blocks tools outside the allowlist and PWM values above the configured limit.
- All three demo paths run on the same hardware without code changes between scenes.
- The public repository has this README and the root license visible before submission.
- The public demo video is no longer than three minutes and shows operating hardware for at least one minute.

## Project links

- [MVP scope and team backlog](https://docs.google.com/spreadsheets/d/1EOCmOg-qVQ_2OJV1DkeH9ULjkR7oT8kNMNGyrTKTUFs/edit?gid=9060801#gid=9060801)
- [Hackathon page](https://nebiusglobalaihackathon.devpost.com/)

## License

Licensed under the [MIT License](LICENSE).
