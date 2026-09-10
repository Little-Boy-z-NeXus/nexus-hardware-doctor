# Contributing to NeXus

## Branches

Create branches from an up-to-date `main` using one of these forms:

- `feat/<issue>-short-kebab-name`
- `fix/<issue>-short-kebab-name`
- `docs/<issue>-short-kebab-name`
- `chore/<issue>-short-kebab-name`

Examples: `feat/h02-nemotron-client` and `fix/n03-ina226-timeout`.

`main` is the integration and demo branch. Do not commit directly to it after the initial repository bootstrap.

## Commits

Use a short imperative subject with an optional area:

```text
feat(backend): return ranked hypotheses
fix(firmware): clamp pwm at policy limit
docs(scope): record auto-heal pass gate
```

## Pull requests

Keep a pull request focused on one backlog item. Include:

- the task or issue ID
- what changed and why
- evidence that the acceptance test passed
- safety impact for firmware, policy, and agent-tool changes
- screenshots or a short clip for visible behavior

At least one review partner from [docs/ownership.md](docs/ownership.md) should approve a change before merge. Do not merge with a failing CI check.

## Local foundation check

```bash
python scripts/validate_repo.py
```
