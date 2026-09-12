# Hardware wiring UX audit

Date: 2026-09-13

## Scope

The existing compact BOM explorer was reviewed in the in-app browser at
`http://localhost:5173/hardware`. The requested extension is a scalable setup and diagnosis view
that explains the machine-readable connection graph without returning to a long horizontal BOM.

## Source observations

- The component index and selected-component detail already keep long model names bounded.
- Connection counts existed, but the page did not show which two physical pins a connection joins.
- `wire_color` was already present in the active hardware profile, so a second hand-maintained
  wiring source would create drift.
- The active profile contains 18 connections. Eleven use an exact canonical color; seven still use
  legacy placeholders (`configured` or `jumper`) and therefore cannot be rendered truthfully.

## Product decisions

- Preserve the existing BOM explorer and add a separate wiring guide directly below it.
- Default to the currently selected component; provide a bounded, scrollable all-connections view.
- Show both component models, both exact pin IDs, pin labels, electrical mode/voltage, signal type,
  connection ID and the physical color declared by the profile.
- Render known colors literally. Render non-colors as a dashed `Chưa chốt màu` connection instead
  of guessing.
- Let either endpoint select its component, keeping wiring inspection connected to the BOM detail.
- Keep the fixed JGB37 harness convention visible in text as well as color so meaning never depends
  on color alone.

## Accessibility and resilience

- Scope controls and endpoints are native buttons with visible focus treatment.
- Wire colors have text labels and are not the only way to identify a connection.
- Long models are clamped inside endpoint cards; the connection list has a fixed maximum height.
- At the current narrow desktop viewport, each connection becomes a vertical A-to-B sequence. At
  wider viewports it becomes a single horizontal row.

## Evidence limits

The visual check used the current in-app browser viewport and live profile. Physical wire colors
cannot be proven from software alone; the seven incomplete declarations are intentionally exposed
as setup work rather than silently inferred.
