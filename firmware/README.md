# nexus-firmware

The firmware runs on one ESP32 DevKit V1. It reads INA219 power telemetry, controls one L298N motor channel, clamps PWM locally, and emits the frozen telemetry v1 envelope over serial.

## Current MVP state

Available now:

- INA219 voltage/current reads
- L298N enable and direction output
- local `NEXUS_MAX_PWM_PERCENT` clamp
- one JSON telemetry sample per second
- field names shared with backend and frontend contract v1

Command transport is not implemented yet. The device starts with the driver disabled and does not accept serial or MQTT actions in the current foundation.

## Hardware required

- ESP32 DevKit V1
- INA219 voltage/current sensor module
- L298N motor driver
- 6–12 V brushed DC motor
- regulated 12 V motor supply sized for the motor
- USB data cable
- jumper wires and a physical way to disconnect motor power quickly

Do not power the motor from the ESP32 3.3 V or 5 V pin. Connect grounds correctly and check the exact labels/jumpers on your L298N module before applying motor power.

## Signal wiring used by the code

| From | To | Purpose |
| --- | --- | --- |
| ESP32 GPIO21 | INA219 SDA | I²C data |
| ESP32 GPIO22 | INA219 SCL | I²C clock |
| ESP32 GPIO25 | L298N ENA | PWM speed control |
| ESP32 GPIO26 | L298N IN1 | Direction/control |
| ESP32 GPIO27 | L298N IN2 | Direction/control |
| L298N OUT1/OUT2 | DC motor terminals | Motor drive |
| ESP32 GND | INA219 GND and L298N logic GND | Common signal reference |

For high-side current measurement, place INA219 in the positive motor-supply path according to the module manufacturer's markings. Do not guess `VIN+` and `VIN-` orientation.

The machine-readable topology is [`nexus-contracts/v1/fixtures/hardware-model.example.json`](../nexus-contracts/v1/fixtures/hardware-model.example.json).

## Install PlatformIO

Python 3.11 is recommended.

```bash
python -m pip install platformio
pio --version
```

Alternatively, use the PlatformIO extension in VS Code, but the CLI commands below are the reproducible path used by the team.

## Detect the ESP32 port

Connect the board with a USB data cable, then run:

```bash
pio device list
```

Typical values:

- Windows: `COM4`
- Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
- macOS: `/dev/cu.usbserial-*`

Use the actual port printed on your machine.

## Build firmware

Run from the repository root:

```bash
pio run --project-dir firmware
```

The default PlatformIO environment is `nexus-esp32` and the expected board is `esp32dev`.

## Upload and monitor on Windows

Replace `COM4` with your detected port:

```powershell
pio run --project-dir firmware --target upload --upload-port COM4
pio device monitor --port COM4 --baud 115200
```

Press `Ctrl+C` to leave the serial monitor.

## Upload and monitor on macOS or Linux

Replace `/dev/ttyUSB0` with your detected port:

```bash
pio run --project-dir firmware --target upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

On Linux, serial access may require adding your account to the `dialout` group and signing in again. Follow your distribution's policy rather than running PlatformIO permanently as root.

## Build-time configuration

The checked-in defaults are in [`platformio.ini`](platformio.ini):

| Flag | Default | Meaning |
| --- | --- | --- |
| `NEXUS_DEVICE_ID` | `nexus-demo-esp32` | Device identity in every payload |
| `NEXUS_HARDWARE_MODEL_ID` | `nexus-motor-rig-v1` | Frozen hardware model identity |
| `NEXUS_MAX_PWM_PERCENT` | `80` | Absolute firmware PWM ceiling |

Do not raise the PWM ceiling until the physical hardware baseline and temperature checks are complete. Never store Wi-Fi or broker credentials in `platformio.ini`.

## Telemetry output

At 115200 baud, the device emits one compact JSON object per line:

```json
{
  "schema_version": "1.0.0",
  "device_id": "nexus-demo-esp32",
  "hardware_model_id": "nexus-motor-rig-v1",
  "sample_id": "nexus-demo-esp32-42",
  "recorded_at": null,
  "sequence": 42,
  "measurements": {
    "bus_voltage_v": 11.96,
    "current_ma": 840.0,
    "power_mw": 10046.4,
    "pwm_percent": 0,
    "driver_enabled": false,
    "motor_rpm": null
  },
  "quality": {
    "signal_quality_percent": 100.0,
    "source": "device"
  }
}
```

`recorded_at` remains `null` until a later transport task synchronizes device time. The backend may stamp receipt time but must not rename the field. `motor_rpm` is also `null` because the locked MVP hardware has no RPM sensor.

## Firmware contract files

- Field-name constants: [`include/nexus_contract_v1.h`](include/nexus_contract_v1.h)
- Canonical telemetry schema: [`../nexus-contracts/v1/schemas/telemetry.schema.json`](../nexus-contracts/v1/schemas/telemetry.schema.json)
- Valid telemetry fixture: [`../nexus-contracts/v1/fixtures/telemetry.example.json`](../nexus-contracts/v1/fixtures/telemetry.example.json)

After changing a telemetry field, run `python scripts/validate_contracts.py` from the repository root. A frozen schema change also requires a migration note.

## Safety before every hardware run

1. Keep motor power off while changing wires.
2. Confirm common ground and INA219 polarity.
3. Confirm the motor supply is within the motor and driver ratings.
4. Keep the motor mechanically clear and secured.
5. Keep a quick motor-power disconnect within reach.
6. Start with the driver disabled and low PWM.
7. Stop immediately if the driver, wiring, or motor overheats or smells abnormal.

The 30-minute baseline, temperature result, supply rating, and photos belong to backlog item U05/N01 and are not claimed complete by this README.

## Common problems

- No port appears: replace charge-only USB cables, install the board's USB-UART driver, and reconnect.
- Upload waits forever: hold the ESP32 `BOOT` button while upload begins, then release it.
- Port is busy: close every serial monitor and IDE serial window before upload.
- INA219 is not detected: check SDA/SCL, common ground, module power, and the I²C address.
- Readings are negative: verify INA219 current direction and `VIN+`/`VIN-` orientation.
- Motor never starts: confirm external motor power, ENA jumper/configuration, common ground, and the local safety clamp.
- Device resets when the motor starts: isolate motor power noise, inspect supply capacity and wiring, and do not bypass safety limits.
