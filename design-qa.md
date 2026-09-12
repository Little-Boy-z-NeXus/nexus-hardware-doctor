# Design QA — profile-driven wiring guide

## Comparison target

- Source visual truth path: `cua-session://iab/1/tab/8/wiringBeforeShot` (existing BOM explorer,
  captured before implementation in this run).
- Implementation screenshot path: `cua-session://iab/1/tab/8/wiringFinalShot` (selected INA226
  wiring view after implementation).
- URL: `http://localhost:5173/hardware`.
- Viewport: 818 × 698 CSS px at device pixel ratio 1.25.
- Source and implementation image pixels: both in-app Browser captures normalized to 800 × 686 px.
- State: Hardware page, light theme, active profile loaded; implementation filtered to the selected
  INA226 component.

## Full-view comparison evidence

The source and implementation captures were emitted together in one comparison input. The new
section preserves the source card surface, green eyebrow, heading scale, warning status pill,
rounded corners, muted supporting copy and sidebar proportions. It adds a bounded wiring list
below the existing BOM rather than changing the accepted BOM explorer.

## Focused region comparison evidence

The wiring section was inspected in selected-component and all-18-connections states at the same
viewport. A focused pass confirmed that long component names remain within endpoint cards, pin
labels and IDs remain visible, literal wire colors have text labels, incomplete colors use a
dashed treatment, and the internal scrollbar prevents page-length growth. A separate close-up was
not needed because the current narrow viewport already renders the section at readable scale.

## Findings

- No actionable P0/P1/P2 visual differences remain.
- Typography: heading/body hierarchy matches the existing Hardware page; pin and connection text
  remains readable without overflowing the cards.
- Spacing and layout: the compact BOM remains unchanged; wiring rows stack cleanly at this viewport
  and stay inside a 470–520 px scroll region.
- Colors and tokens: existing NeXus green, slate and warning tokens are reused. Known physical wire
  colors are literal; white includes a border and incomplete colors are visually distinct.
- Image quality: no raster assets are needed for this structured hardware view. All icons come from
  the project's existing Lucide icon family; the wire itself is a data-driven connection mark.
- Copy and content: Vietnamese setup instructions state the safe order and explicitly prohibit
  guessing missing colors.
- Accessibility: controls are native buttons, selected state is exposed with `aria-pressed`, focus
  is visible, and every color has a text name.

## Interaction and runtime checks

- Selected-component scope: passed.
- All 18 connections scope: passed.
- Selecting INA226 from a wire endpoint and returning to filtered scope: passed.
- Browser DOM contains exact profile endpoints, signal types and connection IDs: passed.
- No visible error overlay or broken interaction was observed. Frontend lint, 18 tests and
  production build all pass.

## Comparison history

1. Initial implementation: core layout passed; pin metadata at 9 px was judged too small for a
   hardware setup aid (P2).
2. Fix: increased endpoint labels, pin IDs, electrical metadata and wire labels by 1–2 px.
3. Post-fix comparison: the same filtered INA226 state remained stable and the metadata became
   easier to scan. No actionable P0/P1/P2 finding remains.

## Follow-up polish

- P3: after the seven real jumper colors are physically confirmed, replace the legacy profile
  placeholders so the completion pill can reach 18/18.

final result: passed
