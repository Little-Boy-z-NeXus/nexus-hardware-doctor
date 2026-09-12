# N05 — Repeatable fault injection

Owner: Nguyễn. This is a supervised physical-test mode for the finalized GOOUUU
ESP32-S3-N16R8, INA226 R100, L298N and JGB37-520 12 V rig. It is never the default demo
firmware.

## Profiles

| Profile | Safe mechanism | Expected evidence |
| --- | --- | --- |
| `PWM_ZERO` | Test build forces requested motor motion to PWM 0/off | Five requests remain at PWM 0/off |
| `PWM_FREQUENCY_LOW` | Test build changes PWM carrier from 1 kHz to 100 Hz | Status reports 100 Hz and physical current rises 5/5 |
| `CURRENT_OFFSET` | Test build adds exactly +200 mA after a valid INA226 read | Shift and reset to real reading reproduce 5/5 |
| `OUT2_OPEN_MANUAL` | Operator turns off 12 V and disconnects only L298N OUT2/M− | Driver is commanded on but current stays at idle 5/5 |

Every profile starts with PWM 0/off. `NEXUS FAULT RESET` restores the normal 1 kHz PWM,
zero measurement offset and safe motor state. The runner also retries a timed-out serial result
with the same request ID; firmware idempotency prevents a second hardware action.

## One-click acceptance

Double-click `nexus-run-n05-fault-acceptance.cmd` and remain beside the rig. It:

1. uploads the dedicated `nexus-goouuu-esp32-s3-n16r8-fault-test` environment;
2. runs PWM-zero, 100 Hz and +200 mA profiles five times each;
3. pauses before the physical OUT2 step;
4. tells the operator to turn off 12 V before removing OUT2/M−;
5. runs the open-output check five times;
6. pauses for OUT2 reconnection with 12 V off;
7. verifies voltage, a 500 ms motor test and final PWM 0/off.

Local NDJSON and Markdown evidence is written under `artifacts/N05/`. Do not mark N05 done
until the software report, manual OUT2 report and restored-baseline report all pass.

## Safety boundary

- Never disconnect a motor wire while 12 V is on.
- Do not short OUT1/OUT2, VIN+/VIN− or the INA226 shunt.
- Keep the motor secured and the 12 V quick disconnect within reach.
- The fault build is locally gated and not exposed as an AI tool.
- Restore the default-safe build with `nexus-upload-firmware.cmd` after acceptance.
