# nexus-contracts

This directory is the canonical interface boundary shared by firmware, backend, frontend, Nemotron prompts, orchestration, safety policy, and verification.

## Start here

1. Read the active [v1 contract catalogue](v1/README.md).
2. Use the JSON files under `v1/schemas` as the source of truth.
3. Use `v1/fixtures` for local development and tests.
4. Read [migrations/README.md](migrations/README.md) before changing any frozen schema.

## Directory structure

```text
nexus-contracts/
├── README.md
├── v1/
│   ├── README.md
│   ├── schemas/       Four canonical JSON Schemas
│   └── fixtures/      One valid example per schema
└── migrations/
    ├── README.md      Migration-note requirements
    └── 0001-freeze-v1.md
```

## Validate contracts from a clean clone

From the repository root, install backend development dependencies because the validator uses `jsonschema`:

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\backend[dev]"
python scripts/validate_contracts.py
```

### macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e "./backend[dev]"
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

## Version policy

- Every envelope contains `schema_version`.
- v1 is frozen at `1.0.0` for the hackathon MVP.
- Additive or corrective v1 changes require a numbered migration note in the same commit.
- Breaking changes create a new directory such as `v2`; never silently redefine v1.
- Consumers reject unknown major versions and unexpected envelope fields.

GitHub CI compares schema changes with migration-note changes. Updating a schema without a note causes the backend job to fail.

## Safe change workflow

1. Confirm the backlog item and affected producers/consumers.
2. Prefer a new major-version directory for a breaking change.
3. Update the canonical schema and its fixture.
4. Update firmware, backend and frontend mirrors together.
5. Add `migrations/NNNN-short-kebab-summary.md` with owner, compatibility, rollout and rollback.
6. Run contract validation, backend tests and frontend checks.
7. Request reviews from the owners of every affected stack.

Do not copy schema definitions into a new folder or service. Reference this directory or generate types from it in a later tooling task.
