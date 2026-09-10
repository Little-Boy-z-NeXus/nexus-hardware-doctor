# U05 — Hardware baseline and demo safety

Owner: Hiếu. Firmware support: Nguyễn. Status remains **Đang làm** until the generated
30-minute report passes and the baseline video exists.

## Fixed MVP kit

| Item | Confirmed MVP choice | Rating/check before power-on |
| --- | --- | --- |
| Controller | GOOUUU Tech ESP32-S3-N16R8 | USB data/power; GPIO is 3.3 V only |
| Current sensor | INA226, R100 shunt | VCC 3.3 V; VBUS bridged to VIN−; high-side current path |
| Motor driver | L298N channel A | External 12 V; remove ENA jumper for GPIO12 PWM |
| Motor | JGB37-520 12 V with Hall A/B encoder | Secure motor; shaft and wires must not catch objects |
| Motor supply | Regulated 12 V DC adapter | Correct polarity and enough current; do not use a 9 V rectangular battery |
| Emergency stop | Inline 12 V switch or reachable barrel plug | Must cut motor power without touching the ESP32 wiring |

## Frozen wiring check

- Adapter `+12V → INA226 VIN+`.
- `INA226 VIN− → L298N +12V/VS`.
- `INA226 VBUS/VBS → INA226 VIN−`.
- Adapter GND, INA226 GND, L298N GND and ESP32 GND are common.
- INA226 VCC → ESP32 3V3; SDA → GPIO1; SCL → GPIO2.
- Remove the L298N ENA jumper; GPIO12 → ENA, GPIO13 → IN1, GPIO14 → IN2.
- Verify the L298N logic supply is active. On the common 12 V module the `5V-EN` regulator
  jumper normally stays installed while the separate channel-A `ENA` jumper is removed.
  Follow the labels on the actual module and never connect its 5 V output to ESP32 3V3.
- L298N OUT1/OUT2 → motor red/white power wires.
- Encoder VCC/GND/A/B → 3V3/GND/GPIO16/GPIO17 using the confirmed cable colors.

Use [`nexus-wiring-jgb37-520.svg`](nexus-wiring-jgb37-520.svg) as the visual source of truth.

## One-click 30-minute test

Double-click `nexus-run-hardware-baseline.cmd` at the repository root. The launcher:

1. stops the app so the test can own the COM port;
2. uploads a special supervised firmware that still boots with the motor off;
3. asks the operator to confirm labels, ENA jumper, motor mounting and emergency stop;
4. runs at 30% PWM with a four-second keepalive failsafe;
5. stops immediately on missing telemetry, invalid voltage, reversed polarity, overcurrent,
   unexpected PWM, or insufficient current rise;
6. saves raw NDJSON and a Markdown report under `artifacts/U05/`;
7. restores normal firmware, where USB baseline commands are disabled;
8. restarts the realtime app.

The operator must remain beside the rig. Press `Ctrl+C` or cut the 12 V supply immediately
for a jam, abnormal vibration/noise, smell, smoke or unsafe temperature.

## Baseline video shot list

Record one continuous or clearly cut video showing:

1. labels on 12 V, VIN+, VIN−/VBUS, GND, ENA, IN1/IN2 and OUT1/OUT2;
2. the physical 12 V emergency disconnect within reach;
3. multimeter or UI bus voltage near 12 V before starting;
4. motor rotating and Hardware Graph updating voltage/current/PWM in realtime;
5. the running-test timer or final 30-minute PASS report;
6. physical emergency stop cutting motor power, followed by the UI fault indication.

Do not create the manual fault by shorting outputs, stalling the shaft or disconnecting GND.
The safe demo fault is cutting only the 12 V motor supply while USB remains connected.

## If PWM changes but current does not rise

When telemetry shows `driver_enabled=true` and the requested PWM but current stays at its
idle value, INA226 and the software command path are working. Check in this order:

1. channel-A `ENA` jumper is removed and GPIO12 reaches the ENA pin;
2. L298N logic power/`5V-EN` is active and its power LED is on;
3. GPIO13 → IN1 and GPIO14 → IN2 are not swapped with ENA;
4. the motor power pair is firmly connected to OUT1/OUT2;
5. with motor power disconnected, use continuity mode to check each wire and verify the
   motor winding is not open-circuit.

Do not bypass the INA226 or short an output to test it.

## Acceptance evidence

U05 is complete only when all are true:

- generated report says `PASS` for at least 1,800 seconds;
- no INA226 read failure, undervoltage, reversed polarity or overcurrent occurred;
- motor and L298N had no abnormal heat, smell, noise or vibration;
- every relevant wire is labelled;
- the quick 12 V disconnect works;
- baseline video is stored in the team's shared evidence location.
