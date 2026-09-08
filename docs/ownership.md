# Team ownership

## Hiếu

- Owns product scope, integration order, demo script, release gate, and Devpost submission readiness.
- Reviews frontend changes and any change that alters the three golden paths.

## Hoàng

- Owns backend architecture, Nemotron integration, structured outputs, diagnosis loop, and technically difficult cross-component work.
- Reviews policy and firmware-to-backend contracts.

## Nguyễn

- Owns ESP32 firmware, INA219 telemetry, device commands, automated test routines, and repeatable hardware fault injection.
- Records the hardware baseline and safe operating limits.

## Nguyên

- Owns scoped frontend tasks, UI states, API wiring, and small well-defined implementation issues.
- Escalates architecture changes to Hiếu or Hoàng before implementation.

## Shared rule

The primary owner implements or coordinates an area. The review partner verifies the acceptance test. Work that crosses two areas needs one named integrator before coding starts.
