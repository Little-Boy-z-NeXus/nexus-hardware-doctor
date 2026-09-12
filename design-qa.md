# Design QA — Hardware graph responsive flow

## Visual truth and test state

- Source reference: `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-7449ed4e-bd78-4d2b-b38a-6ae2d5bdbdf5.png` (1461 × 592).
- Implementation capture: Codex in-app Browser tab 8 at `http://localhost:5173/hardware`.
- Viewports checked: 808 × 680 (default app viewport) and 390 × 844 (mobile).
- Runtime state: `/hardware`, live COM8 profile, five declared components, zero active issues during the final pass.

## Comparison history

### Initial issues from the supplied reference

- The signal path assumed exactly four cards, so additional hardware could be omitted or force uneven wrapping.
- Long component names changed card height and pushed status rows out of alignment.
- The full BOM title and profile identifier could compete with the issue badge and overflow their containers.
- Narrow layouts stacked a potentially unbounded number of cards vertically.

### Fixes applied

- Render every component declared by the active hardware profile instead of a fixed role list.
- Use an equal-width, equal-height horizontal track with scroll snap and keyboard focus.
- Clamp long names and supporting text while preserving full values in native title tooltips and accessible labels.
- Protect the header, issue badge, footer profile identifier, connectors, and card status alignment from overflow.
- Keep the same horizontal browsing model on mobile, with the next card partially visible as a scroll affordance.

## Fidelity review

- Layout and hierarchy: passed — the section header, issue badge, signal path, and legend retain the source hierarchy without collisions.
- Typography: passed — headings remain legible; long hardware names wrap predictably and no longer resize the cards.
- Color and surfaces: passed — existing semantic colors, borders, shadows, and health states are preserved.
- Content and data: passed — controller, sensor, driver, actuator, power, and future profile components are driven by profile data.
- Responsive behavior: passed — no page-level horizontal overflow; only the labelled hardware-flow region scrolls.

## Interaction and regression checks

- Keyboard navigation: passed — focusing the hardware-flow region and pressing End changed `scrollLeft` from 6.4 to 426.4 at 390 px.
- Mobile visual pass: passed — header and issue badge remain separated; cards stay aligned and horizontally discoverable.
- Desktop/app visual pass: passed — two-line BOM title, stable badge, equal cards, and intentional contained overflow.
- Browser console: passed — zero errors.
- Automated frontend gate: passed — ESLint, 15 Vitest tests, TypeScript, and Vite production build.

## Final result

passed
