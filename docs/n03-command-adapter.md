# N03 — hardware command adapter

Owner: Nguyễn. Device protocol: `1.0.0`. Hardware model:
`nexus-s3-ina226-l298n-motor-rig-v1`.

## What is implemented

The ESP32 reads newline-delimited JSON while continuing to emit telemetry at roughly 1 Hz.
Every accepted request produces a correlated `ack` and one `result` or `error`. Results carry
sensor/motor snapshots before and after execution. The four most recent request IDs are cached;
an identical repeat returns the cached result and never repeats a hardware action, while a
different command using the same ID is rejected.

The device protocol is intentionally below the frozen Tool Call v1 boundary:

```text
Tool Call v1 tool_call_id
          │ copy unchanged
          ▼
Device command request_id → ESP32 ACK → result/error → host adapter
```

`read_voltage` and `read_current` are device-level parts of canonical `get_telemetry`.
`reset_driver` and `recalibrate_sensor` are local recovery primitives; exposing either to the AI
requires a future reviewed contract migration. N03 therefore does not silently add tools to v1.

## Safety behavior

- Boot state is PWM 0 and driver disabled.
- JSON larger than 512 bytes, unknown fields, unknown commands and bad arguments are rejected
  before command execution.
- GPIO reads are limited to GPIO12/13/14/16/17; no arbitrary write command exists.
- PWM is capped at 80%; motor tests require 1–80% for 100–3000 ms; command timeout is
  100–5000 ms.
- Motion requires a valid INA226 sample, bus voltage from 9.5 to 13.0 V and absolute current at
  or below 1500 mA.
- A motor test always returns to PWM 0/driver off, including a sensor/current safety failure.
- Normal firmware rejects all motor writes. Only the supervised `command-test` build enables
  them.

## Software acceptance completed without the rig

| Check | Expected |
| --- | --- |
| Default firmware build | PASS; writes compiled as disabled |
| Command-test firmware build | PASS; bounded write path compiled |
| Protocol schema examples | Every command/response fixture validates |
| Invalid command tests | unknown command, PWM 81%, GPIO0 and extra arguments rejected |
| Timeout tests | missing/invalid timeout and duration above 3000 ms rejected |
| Host adapter tests | telemetry ignored; matching ACK/result correlated by `request_id` |
| Backend log compatibility | command responses remain visible and do not create fake `TELEMETRY_INVALID` |

## Physical acceptance still required

Stop `nexus-start-app.cmd` and every serial monitor first because only one process can own the
COM port. Double-click `nexus-upload-command-firmware.cmd`, then run the following from the
repository root with the actual port:

| Case | Command | Pass condition |
| --- | --- | --- |
| Read voltage | `python scripts/nexus_device_command.py read_voltage --port COM8 --request-id n03-v-1` | ACK then result near the multimeter bus reading; no hardware effect |
| Read current | `python scripts/nexus_device_command.py read_current --port COM8 --request-id n03-i-1` | ACK then finite current result; no hardware effect |
| Read GPIO | `python scripts/nexus_device_command.py read_gpio --port COM8 --pin-id gpio_16 --request-id n03-g-1` | level is 0 or 1; GPIO0 request is locally rejected |
| Stage PWM + duplicate | `python scripts/nexus_device_command.py set_pwm --port COM8 --pwm-percent 20 --confirm-write --request-id n03-p-1 --verify-duplicate` | duplicate check PASS; repeated request does not create a second action |
| Enable/stop | enable with `--enabled`, then run `reset_driver` | motor runs only after explicit enable; reset result shows PWM 0/off |
| Bounded motor test | `python scripts/nexus_device_command.py run_motor_test --port COM8 --duration-ms 500 --pwm-percent 20 --timeout-ms 1000 --confirm-write --request-id n03-m-1` | runs briefly, returns to PWM 0/off, before/after included |
| Recalibrate | `python scripts/nexus_device_command.py recalibrate_sensor --port COM8 --request-id n03-c-1` | only works while stopped and returns fixed R100 values |
| ID conflict | resend `n03-p-1` with a different PWM | `REQUEST_ID_CONFLICT`; motor state unchanged |

Save the terminal output under ignored local evidence/log storage. After physical cases pass,
restore the default-safe build with `nexus-upload-firmware.cmd` before starting the full app.

For the complete automated matrix, double-click `nexus-run-n03-hardware-acceptance.cmd`.
It uploads the supervised command-test build, checks every allowlisted GPIO, invalid command and
timeout default-deny behavior, duplicate replay, request-ID conflict, a brief physical load,
bounded motor test, recalibration and final safe stop. Evidence is saved under `artifacts/N03/`.

## Scope boundary

N03 supplies the firmware executor and a direct supervised serial client. H05 owns connecting
the backend orchestrator/policy to this transport. N05 owns repeatable fault profiles, and N06
owns real closed-loop auto-heal. Those tasks remain separate so no AI path can bypass policy.
