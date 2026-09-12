# NeXus validation scripts

These scripts provide fast, deterministic checks for repository structure and frozen interface contracts. Run them from the repository root.

## Scripts

| Script | Dependencies | Checks |
| --- | --- | --- |
| [`validate_repo.py`](validate_repo.py) | Python 3.11 standard library | Required folders/files, naming, root license, backlog link, package prefixes, secret-file exclusions, README links |
| [`validate_contracts.py`](validate_contracts.py) | Backend development dependencies | Four JSON Schemas, four fixtures, cross-fixture references, shared stack fields, migration-note rule |
| [`nexus_hardware_baseline.py`](nexus_hardware_baseline.py) | Backend virtual environment + supervised hardware | U05 30-minute voltage/current/PWM soak test, failsafe stop, local evidence and report |
| [`nexus_device_command.py`](nexus_device_command.py) | `pyserial` from the backend environment + supervised hardware | N03 correlated ACK/result/error exchange, local argument checks and duplicate replay verification |
| [`nexus_n03_hardware_acceptance.py`](nexus_n03_hardware_acceptance.py) | `pyserial` + secured physical rig | Complete N03 real-board matrix, final failsafe stop and local NDJSON/Markdown evidence |
| [`nexus_n05_fault_acceptance.py`](nexus_n05_fault_acceptance.py) | `pyserial` + secured physical rig | Five-cycle N05 software/manual fault checks, transport retry, safe reset and local evidence |
| [`nexus_n06_auto_heal_acceptance.py`](nexus_n06_auto_heal_acceptance.py) | `pyserial` + secured physical rig | Five-cycle PWM fault → policy → recovery → motor-test loop with before/after audit evidence |

`python -m nexus_backend.replay_server` is the N07 no-hardware replay entry point. It serves
sanitized telemetry through the same live API/WebSocket consumed by the frontend.

Both scripts return exit code `0` on success and a non-zero exit code with actionable messages on failure. GitHub Actions relies on those exit codes.

## Prepare the environment

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\backend[dev]"
```

### macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
```

`validate_repo.py` can run before dependency installation. `validate_contracts.py` needs the `jsonschema` package installed by `backend[dev]`.

## Validate repository structure

```bash
python scripts/validate_repo.py
```

Expected output begins with:

```text
NeXus repository foundation: PASS
```

If it fails, restore the named required file or fix the exact naming/link/secret issue. Do not weaken the validator just to make CI green.

## Validate interface contracts

```bash
python scripts/validate_contracts.py
```

Expected output:

```text
NeXus contracts: PASS
Contract version: 1.0.0
Schemas validated: 4
Fixtures validated: 4
Stack mirrors checked: 3
```

CI also passes a Git base SHA:

```bash
python scripts/validate_contracts.py --base-ref <git-commit-sha>
```

When files under `nexus-contracts/v1/schemas/` changed after that SHA, the same commit range must contain a numbered migration note under `nexus-contracts/migrations/`.

## Run the complete software check

```bash
python scripts/validate_repo.py
python scripts/validate_contracts.py
ruff check backend scripts
python -m pytest backend/tests -q
npm --prefix frontend run check
```

Firmware compilation is separate because it requires PlatformIO:

```bash
pio run --project-dir firmware
```

Build both the default-safe and N03 command-test variants:

```bash
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8
pio run --project-dir firmware --environment nexus-goouuu-esp32-s3-n16r8-command-test
```

The command-test variant permits bounded physical motor writes. Read
[`../docs/n03-command-adapter.md`](../docs/n03-command-adapter.md) and keep the motor-power
disconnect within reach before uploading it.

## Adding or changing a validator

- Keep failure messages actionable and deterministic.
- Avoid network access and credentials during validation.
- Resolve paths from the repository root, not the caller's current directory.
- Add a positive test fixture and, when useful, a failure-path test.
- Update this README and the root README when commands or dependencies change.
- Run the script on Windows and through GitHub Actions before merging.

Do not put generated reports, private telemetry, keys, or raw model logs under `scripts/`.

## H01/H04 live model and H05 read-only smoke check

`python scripts/check_live_model.py --live --env-file .env` exercises a real configured
NVIDIA model through the existing orchestrator. A synthetic PWM fault is held in an isolated
read-only adapter; the model must request telemetry, receive it and return a grounded fault
hypothesis. The report is written under ignored `artifacts/` and explicitly excludes physical
acceptance. It returns 0 for a passing check, 1 for an unsuccessful run, and 2 for configuration
or runner failure. Omitting `--live` is rejected before any API request.

The companion `python -m nexus_backend.evaluation --live --env-file .env` scores ten synthetic
cases. These explicit live commands incur model usage; normal automated tests use mocked HTTP.
Repository secret-file checks require Git and permit ignored local `.env` files, while
rejecting tracked or unignored credentials.
