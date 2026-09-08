# Contract migration notes

Add one numbered file per contract change: `NNNN-short-kebab-summary.md`.

Every note must state the affected version, compatibility impact, owner, producer/consumer rollout order, and rollback plan. Breaking changes create a new version directory instead of rewriting v1.

## Required template

```markdown
# NNNN — Short change name

- Date: YYYY-MM-DD
- Owner: Name
- Version: 1.x.x or 2.0.0
- Compatibility: additive, corrective, or breaking

## Decision

What changed and why.

## Rollout

Producer/consumer update order and deployment checks.

## Rollback

How the team returns to the previous safe contract.
```

## Workflow

1. Add the numbered note in the same branch as the schema change.
2. Update the schema, matching fixture, and all affected stack mirrors.
3. Run `python scripts/validate_contracts.py` locally.
4. Open a pull request and request every affected stack owner.

CI checks that a v1 schema change includes a non-README migration note in the same commit range and that the note contains Version, Compatibility, Owner, Rollout, and Rollback information.
