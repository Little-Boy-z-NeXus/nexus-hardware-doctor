# nexus-backend

Owns the hardware model, rule engine, Nemotron reasoning, tool orchestration, safety policy, and API exposed to the frontend.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn nexus_backend.app:app --reload
pytest
```

On Windows PowerShell, activate the environment with `.venv\\Scripts\\Activate.ps1`.

Copy the root `.env.example` to `.env`. Keep Nebius credentials outside source control and redact them from request logs.
