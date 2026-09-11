# NeXus device command protocol v1

This is the USB serial boundary between the host adapter and the ESP32. It is
deliberately separate from the frozen cross-stack Tool Call v1 schema. The host
copies canonical `tool_call_id` into device `request_id`; internal maintenance
commands never appear as new Tool Call v1 names without a reviewed migration.

Each command is one compact JSON object followed by `\n`. The firmware emits an
`ack` and then exactly one terminal `result` or `error` with the same
`request_id`. The maximum input line is 512 bytes.

## Allowlist and canonical mapping

| Device command | Purpose | Tool Call v1 mapping |
| --- | --- | --- |
| `read_voltage` | Read INA226 bus voltage | part of `get_telemetry` |
| `read_current` | Read INA226 current | part of `get_telemetry` |
| `read_gpio` | Read GPIO12/13/14/16/17 only | `read_gpio` |
| `enable_driver` | Enable only after a non-zero staged PWM | `enable_driver` |
| `set_pwm` | Stage or apply PWM, clamped to 0–80% | `set_pwm` |
| `run_motor_test` | Run 100–3000 ms and always stop | `run_motor_test` |
| `reset_driver` | Force PWM 0 and driver off | internal recovery primitive |
| `recalibrate_sensor` | Reapply fixed INA226 R100 calibration while stopped | internal maintenance primitive |

## Idempotency and failure behavior

The firmware caches the four most recent terminal responses. Repeating the same
semantic command with the same `request_id` returns `duplicate: true` and the
cached terminal response without a second hardware action. Reusing an ID with
different arguments returns `REQUEST_ID_CONFLICT`. Invalid JSON, unknown fields,
unknown commands, out-of-range values and too-short timeouts are rejected before
any hardware function is called.

Normal firmware accepts reads, reset and sensor recalibration, but responds
`COMMAND_WRITES_DISABLED` for motor writes. Physical writes exist only in the
`nexus-goouuu-esp32-s3-n16r8-command-test` build. That build still requires a
valid INA226 sample, 9.5–13.0 V bus, current at or below 1500 mA, PWM at or below
80%, and a motor-test duration at or below 3000 ms.

See `command.schema.json`, `response.schema.json`, and `examples.json` in this
directory for machine-checkable envelopes.
