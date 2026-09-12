# Signal-wire monitoring for the MVP

NeXus must not label a signal wire healthy only because a numeric value exists. A signal is
accepted only when the firmware can prove electrical liveness and semantic plausibility. Failed
checks are logged immediately, the sample is withheld, and the backend streams an actionable
Vietnamese fault card to the Hardware Graph.

## What is monitored now

| Signal | Positive proof | Immediate fault | Safe repair |
| --- | --- | --- | --- |
| INA226 SDA → GPIO1 | bus idle HIGH, address `0x40` ACK, correct chip ID and valid register reads | `I2C_SDA_STUCK_LOW`, `INA226_I2C_NO_ACK`, read/identity failure | Turn motor power off; reseat SDA, check short-to-GND and pull-up |
| INA226 SCL → GPIO2 | bus idle HIGH plus the same complete I²C transaction | `I2C_SCL_STUCK_LOW`, `INA226_I2C_NO_ACK`, read/identity failure | Turn motor power off; reseat SCL, check short-to-GND and pull-up |
| INA226 measurement path | current register agrees with `shunt_mV / 0.1 Ω` within tolerance | `INA226_SIGNAL_INCONSISTENT` | Check SDA/SCL routing, R100 marking, GND and calibration |
| Encoder A → GPIO16 | A edges observed during a commanded motor run | `ENCODER_CHANNEL_A_MISSING` or shared encoder fault | Turn motor power off; reseat the yellow A wire |
| Encoder B → GPIO17 | B edges observed during a commanded motor run | `ENCODER_CHANNEL_B_MISSING` or shared encoder fault | Turn motor power off; reseat the green B wire |

The UI shows `Chờ kiểm chứng` for an encoder while the motor is stopped. No pulse at rest is
normal and cannot prove either a healthy or broken wire. A supervised motor run is required.

## Detection latency

- SDA/SCL electrical, ACK, identity and measurement-consistency checks run before every
  one-second telemetry sample. A failed sample never reaches the UI as valid telemetry.
- Encoder A/B are observed for at least 250 ms while the driver is enabled. Long runs are
  evaluated every second; short supervised motor tests are evaluated before stopping.
- Firmware emits a monitor heartbeat every ten seconds so a backend attached after boot can
  verify that the new watchdog firmware is present.
- The backend sends every new fault through the existing WebSocket immediately; no page reload
  is required.

## Safe acceptance cases

Do not move wires while motor power or USB power is present. For each case: stop the app, turn
off 12 V, unplug USB, change one connection, reconnect USB, start the app, observe the expected
fault, then power down again and restore the wire.

1. Remove SDA or SCL: the UI must show `INA226_I2C_NO_ACK`; telemetry must stop advancing.
2. Hold-down or short faults encountered in real wiring: the UI names SDA/GPIO1 or SCL/GPIO2
   when the affected line is observed LOW. Do not deliberately short a powered board.
3. Restore I²C wiring: the firmware retries within five seconds; fresh verified telemetry clears
   the active I²C fault.
4. Remove encoder A, then perform one short supervised motor test: the UI must name the yellow
   A/GPIO16 wire.
5. Remove encoder B and repeat: the UI must name the green B/GPIO17 wire.
6. Restore both encoder wires and repeat the supervised test: `ENCODER_SIGNAL_OK` must clear the
   active encoder fault.

## Rule for future signals

Every new input wire must define a positive liveness check, invalid/stuck states, detection
latency, a stable fault code, and a safe recovery test. Every output wire must have independent
feedback before NeXus can claim continuity. For the current L298N ENA/IN1/IN2 wires, firmware
knows the ESP32 output state but cannot prove the physical jumper reaches the driver. NeXus can
only infer that path from current and encoder response during a supervised run. Guaranteed
per-wire continuity would require extra feedback hardware and is outside the frozen MVP BOM.
