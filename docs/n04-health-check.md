# N04 — NeXus Health Check

N04 is a deterministic pre-power check. It runs without an ESP32, motor, serial port, or
model credential. It validates declared hardware facts only and never invents a voltage
rating that is absent from the frozen hardware model.

## Rules

| Rule | Severity | Trigger | Suggested response |
| --- | --- | --- | --- |
| `VOLTAGE_LIMIT_EXCEEDED` | error | A measured/declared signal voltage is outside the target pin range | Disconnect power; add a level shifter/regulator or use the correct logic level |
| `REQUIRED_CONNECTION_MISSING` | error | A required wire is absent or references an unknown endpoint | Restore the pin-map connection and check continuity |
| `PIN_DIRECTION_CONFLICT` | error | The signal type and pin directions cannot safely communicate | Use one driving output and one receiving input; keep SDA/SCL on I2C pins |
| `POWER_SUPPLY_INCOMPATIBLE` | error | A power connection is outside the target supply range | Disconnect power and use the component's rated supply |
| `COMPONENT_METADATA_MISSING` | error | A component lacks its identity, type, model, pins, or capabilities | Complete the component declaration before wiring |

Every finding contains `severity`, `evidence`, and `remediation`. A report status is
`pass`, `warning`, or `fail`; any error produces `fail`.

## Run through the API

Start the backend, then call `POST /api/v1/health-check`. The request contains the frozen
`hardware_model` and an optional `profile`:

```json
{
  "hardware_model": {"...": "hardware-model v1"},
  "profile": {
    "pin_profiles": [
      {
        "component_id": "dc_motor",
        "pin_id": "encoder_a",
        "direction": "output",
        "nominal_voltage_v": 5.0
      },
      {
        "component_id": "esp32",
        "pin_id": "gpio_16",
        "direction": "input",
        "max_voltage_v": 3.3
      }
    ],
    "connection_readings": [
      {"connection_id": "motor_encoder_a_to_esp32", "voltage_v": 5.0}
    ],
    "required_connections": []
  }
}
```

That example fails with `VOLTAGE_LIMIT_EXCEEDED` and records both 5.0 V observed and
3.3 V allowed in the evidence. `pin_profiles` are declared ratings; `connection_readings`
are measurements or trusted design inputs. Do not put guessed ratings into either list.

## Acceptance evidence

The executable rule fixtures are
[`backend/tests/fixtures/health-check-cases.json`](../backend/tests/fixtures/health-check-cases.json).
They cover all five N04 rule groups, including 5 V into a 3.3 V GPIO. Run:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest `
  backend\tests\test_health_check.py `
  backend\tests\test_health_check_api.py -q
```

The complete backend regression remains mandatory before merge:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -q
.\backend\.venv\Scripts\python.exe -m ruff check backend scripts
```

Passing software fixtures completes N04. It does not validate physical wiring or close
N03, N05, N06, N07, or N08.
