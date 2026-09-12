# Design QA — Compact hardware explorer

## Evidence and state

- Source visual truth: `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-b4ef546d-3d0e-4b58-84a0-78f9a594703c.png` (1463 × 615). This is the user-identified problem state, not a pixel-match target.
- Rendered implementation: Codex in-app Browser tab 8 at `http://localhost:5173/hardware` (802 × 680 CSS viewport, density 1).
- Focused implementation capture: the accepted in-app Browser capture with search value `INA226`, one result, and the INA226 detail panel selected automatically.
- Runtime state: live COM8 telemetry, five profile components, zero active hardware issues.

## Full-view comparison

The problem state repeats the complete hardware path in the title and presents every component as a large card in one horizontal strip. The revised view keeps the section width bounded, replaces the strip with a fixed-height searchable index, and shows details for only one selected component. At 802 px, the document measured 802 px client width and 802 px scroll width, so the redesign does not introduce page-level horizontal overflow.

## Focused region comparison

The BOM region required a focused comparison because the user concern was scanability with long names and many components. The final capture shows one compact result row for `INA226` and a corresponding detail panel with status, live measurement, identity, connections, pins, capabilities, and immediate neighbors. Long names are ellipsized in the index and retained in accessible labels and title tooltips.

## Comparison history

1. P1 — The horizontal card carousel scaled linearly with component count and hid later components. Fixed with a fixed-height searchable component index and one on-demand detail panel.
2. P1 — The first redesign pass could show details for a component that no longer matched the search. Fixed by automatically selecting the first matching component as the query changes.
3. P2 — The complete BOM path duplicated the same names already shown in the cards and dominated the header. Fixed with a short component count and a direct instruction.
4. P2 — The old scrollbar was the only discovery mechanism for off-screen hardware. Fixed with visible search, result count, ordered rows, and native vertical list scrolling.

## Required fidelity surfaces

- Fonts and typography: passed — the existing NeXus type scale is preserved; long component names truncate only in compact overview rows and remain available in the detail view.
- Spacing and layout rhythm: passed — list and detail use bounded heights, consistent 8–18 px spacing, and stable alignment independent of BOM length.
- Colors and visual tokens: passed — existing blue, teal, violet, orange, healthy, warning, and error tokens are preserved.
- Image and icon quality: passed — no raster assets were required; existing Lucide component icons are reused consistently.
- Copy and content: passed — English path duplication was removed; Vietnamese instructions explain the primary action in one sentence.
- Responsiveness and accessibility: passed — no page overflow at the verified viewport; search is labelled, every component is a real button, selection uses `aria-pressed`, and the detail panel is live-announced.

## Interaction and regression evidence

- Search `INA226`: passed — result count changed from 5/5 to 1/5 and detail changed automatically to component 2/5.
- Search with no match: passed — `Không có linh kiện phù hợp.` appeared.
- Direct component selection: passed — selected state and detail content update from the profile data.
- Browser console: passed — no warning or error entries; only Vite connection and React development information messages.
- Automated frontend gate: passed — ESLint, 15 Vitest tests, TypeScript, and Vite production build.

## Final result

passed
