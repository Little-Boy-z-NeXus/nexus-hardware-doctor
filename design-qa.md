# Design QA — dual-motor PID hardware architecture

## Comparison target

- Source visual truth: `docs/nexus-dual-motor-pid-wiring-v1.png` (1672 × 941 px).
- Source browser capture: `cua-session://iab/1/tab/2/sourceCompareShot`.
- Implementation browser capture: `cua-session://iab/1/tab/1/implementationCompareShot`.
- Desktop capture: `cua-session://iab/1/tab/1/desktopReadyShot` at 1440 × 900 CSS px.
- Mobile capture: `cua-session://iab/1/tab/1/mobileCroppedShot` at 390 × 844 CSS px.
- URL: `http://localhost:5173/hardware`.

## Full-view comparison evidence

The source wiring diagram and the implemented Hardware page were emitted together in one visual
comparison input. The frontend preserves the source hierarchy: protected 3S power chain, shared
3.3 V I²C bus, ESP32-S3 control center, L298N dual channels and separate left/right motors. The UI
translates that dense technical diagram into a scan-first architecture view plus a bounded,
filterable wiring list.

## Findings and corrections

- P2 fixed: the wiring eyebrow initially said 40 paths while the manifest projection contains 43;
  the heading now reads the data length dynamically.
- No remaining P0/P1/P2 visual differences.
- Typography and spacing: long hardware names wrap or truncate inside bounded regions; the two
  motor cards stay balanced at desktop and stack cleanly on mobile.
- Color fidelity: red, black, green, yellow, blue, orange, purple and white are rendered literally,
  with a text label beside every swatch so color is never the only signal.
- Information density: the 43 paths are constrained to a 520 px scroll area and can be reduced to
  Power, I²C, Motor left or Motor right without growing the page.
- State honesty: all dual-motor readings remain `--` and the page says `Chờ firmware dual-motor`;
  the live single-motor runtime stays available in its own mode.
- Asset quality: the 1672 × 941 reference diagram loads at natural resolution and has descriptive
  alternative text.

## Responsive and interaction checks

- Desktop 1440 px: architecture hero, three-column PID balance and two evidence panels align.
- Mobile 390 px: no horizontal body overflow; mode switch, motor cards and evidence panels stack.
- Mobile wiring list: 10 right-motor rows fit without horizontal overflow.
- Right-motor filter: exposes GPIO4, GPIO5, GPIO6, GPIO7 and GPIO8 and exactly 10 paths.
- Reference diagram toggle: opens and closes the source image successfully.
- Live-mode switch: restores current BOM, telemetry and ESP32 realtime log.
- Browser console: no errors.
- Accessibility smoke: no unnamed buttons, duplicate IDs or images without alt text.

## Automated verification

- ESLint: passed.
- Vitest: 20 tests passed.
- TypeScript + Vite production build: passed.

## Follow-up polish

- P3: connect the planned dual-motor telemetry contract after the firmware exposes independent
  left/right RPM and PWM fields.

final result: passed
