# Design QA — Readable latest-first live log

## Evidence and state

- Source visual truth path: `C:\Users\lenovo\AppData\Local\Temp\codex-clipboard-8adc025a-010e-4ef5-9f39-c19d5ee160a1.png`.
- Source pixels: 901 × 566.
- Rendered implementation: Codex in-app Browser tab 8 at `http://localhost:5173/hardware`.
- Implementation capture: browser-rendered inline capture in the current task at 818 × 698 CSS px, device density 1.
- Combined comparison evidence: Codex in-app Browser QA tab 9 rendered the source crop and the live implementation in the same 1280 × 720 comparison frame before handoff.
- State: COM8 live, 160 buffered records, newest telemetry visible, no active hardware error.
- Density normalization: source and implementation were compared at their native 1× browser density; the source is a focused crop while the implementation evidence includes the surrounding app for responsive context.

## Full-view comparison evidence

The source shows raw JSON wrapping across most of each row and no reliable indication that the visible row is the latest. The implementation groups controls into a stable header, adds a live-follow status, keeps a bounded 360 px feed, converts telemetry into compact metric cells, and preserves the dark NeXus terminal visual language. At 818 px viewport width, the document and terminal both measured 0 px horizontal overflow.

## Focused region comparison evidence

The log feed required a focused comparison because readability and scroll state are the requested interaction. In the final capture, two recent telemetry entries fit inside the feed with clear time, level, sequence, four measurements, source, and an optional raw-data disclosure. A second interaction capture verified the `Bạn đang xem log cũ` state and sticky `Về log mới nhất` control after keyboard scrolling.

## Comparison history

1. P1 — Autoscroll depended on `visibleLogs.length`, which remains 160 after the buffer fills. Fixed by following `latestVisibleLog.id`; post-fix evidence showed the last visible sequence and `Mới nhất lúc` advancing together.
2. P1 — Raw JSON dominated every row. Fixed with parsed telemetry summaries and collapsed raw data; post-fix evidence showed voltage, current, power and motor state without horizontal scanning.
3. P2 — Initial responsive pass produced a horizontal scrollbar in the terminal at an 818 px viewport. Fixed with zero-minimum grid tracks and two-column metrics below 1000 px; post-fix measurement was 0 px horizontal overflow.
4. P2 — Layout reflow could incorrectly switch the state to old logs. Fixed by distinguishing real wheel, touch, pointer-scrollbar and keyboard intent from programmatic scroll; post-fix reload remained in `Đang theo dõi log mới nhất`.

## Required fidelity surfaces

- Fonts and typography: passed — existing NeXus fonts remain; hierarchy now separates time, level, event title, source and measurements; long raw content is isolated in a monospaced disclosure.
- Spacing and layout rhythm: passed — 7–18 px spacing, consistent row dividers and responsive two-column measurement layout prevent dense wrapping.
- Colors and visual tokens: passed — the existing navy, teal, amber and red semantic tokens are retained with sufficient separation between live, warning and error states.
- Image and icon quality: passed — no raster assets are required; existing Lucide icons are used for actions and disclosure.
- Copy and content: passed — live-follow, browsing-history and paused states are written in direct Vietnamese; hardware messages are summarized without discarding raw evidence.
- Responsiveness and accessibility: passed — no horizontal overflow at the verified viewport; the log region is keyboard focusable, filters are labelled, focus rings are visible, and live announcements are disabled for the high-frequency feed to avoid assistive-technology noise.

## Primary interactions tested

- Fresh reload follows the latest log by default.
- Realtime updates continue while the buffer stays fixed at 160 records.
- `Home`/manual browsing stops follow mode and reveals `Về log mới nhất`.
- `Về log mới nhất` restores follow mode and scrolls to the latest record.
- Raw JSON disclosure opens without losing the compact summary.
- Search, level filter, pause/resume, clear and download controls remain present.
- Browser console checked: no warnings or errors.
- Automated frontend gate: ESLint, 17 Vitest tests, TypeScript and Vite production build passed.

## Final result

passed
