# Hardware graph UX audit

## Overall verdict

The original BOM graph was visually tidy for four or five parts but did not scale as an operational interface. Finding one component required horizontal scrolling, the full path was repeated in the heading, and each extra component added another large card. The highest-impact fix is progressive disclosure: keep a compact searchable index visible and reveal one component's operational detail at a time.

## Audited flow

1. **Read system health — needs improvement in the original.** The zero-error badge is clear, but the very long path competes with it and repeats content below.
2. **Find a component — poor in the original.** Later components are off-screen and the scrollbar gives no clue which hardware is hidden.
3. **Inspect one component — poor in the original.** Every card receives equal visual weight even when the user only needs one faulty or selected component.
4. **Use the revised explorer — healthy.** Search narrows the bounded list, automatically selects the matching component, and preserves live status plus neighboring path context in one detail panel.

## Findings addressed

- **P1 — Unbounded horizontal navigation.** Replaced the card carousel with a fixed-height, vertically scrolling component index.
- **P1 — Weak information priority.** Replaced the full path heading with the component count and a single instruction.
- **P2 — Hidden selection context.** Added ordered component numbers, selected styling, health dots, and previous/next neighbors.
- **P2 — Long-name instability.** Overview names now ellipsize without changing row height; full names remain visible in the detail panel and accessibility labels.
- **P2 — Search/detail mismatch.** The first matching result now becomes the selected detail automatically.

## Accessibility notes and limits

Search has an explicit accessible label, list entries are native buttons with `aria-pressed`, health has textual equivalents, and focus styling remains visible. Screenshot and DOM inspection cannot prove full screen-reader behavior or text zoom beyond the checked viewport; those remain broader regression-test concerns rather than blockers for this focused change.

## Evidence

- User-provided original: `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-b4ef546d-3d0e-4b58-84a0-78f9a594703c.png`.
- Revised runtime: Codex in-app Browser tab 8, `http://localhost:5173/hardware`, verified with live COM8 data.
