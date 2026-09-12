# NeXus hardware as code

This directory is the machine-readable source of truth for the physical NeXus rig. A wiring
image is useful to a person, but it is not authoritative because software and agents cannot
reliably validate its pins, limits or identities. The canonical MVP definition is JSON:

- schema: [`v1/nexus-hardware-profile.schema.json`](v1/nexus-hardware-profile.schema.json)
- active profile: [`profiles/nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1.json`](profiles/nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1.json)

JSON is used instead of YAML for v1 so the same document has strict JSON Schema validation,
unambiguous scalar types, deterministic generation and no additional firmware build dependency.
A future editor may accept YAML, but it must convert to and validate the canonical JSON before
the profile can be selected.

The Hardware page renders the same `connections` array as an interactive wiring guide. Every
row shows both components, both exact pin IDs, signal type and the declared physical wire color.
Canonical color names (`red`, `black`, `yellow`, `green`, `blue`, `white`, `orange`, `purple`,
`gray`, `brown`) are drawn literally. Legacy placeholders such as `configured` or `jumper` are
shown as a dashed **Chưa chốt màu** wire: the UI and an agent must never guess a physical color.

For the JGB37-520 harness in this profile, the fixed lead sequence remains **red, black, yellow,
green, blue, white**. The mapping is red = Motor+, black = encoder GND, yellow = encoder A,
green = encoder B, blue = encoder VCC and white = Motor-. For every other jumper, record the color
that is physically installed; a general convention is only a setup default and must not override
the real harness.

## What the profile controls

The selected profile declares:

- controller family, exact board, runtime and logic voltage;
- transport and USB discovery identities;
- every component, driver, pin and machine capability;
- the physical connection graph, including motor wire colors;
- telemetry field-to-component/unit mappings;
- voltage, current, PWM and test-duration safety limits;
- firmware GPIOs, INA226 calibration and chip identity registers.

PlatformIO compiles these values into
`firmware/include/nexus_hardware_profile.generated.h` before every build. The backend loads the
same profile at startup and uses it for USB discovery, compatibility checks, UI metadata and
safety thresholds. Firmware reports `profile_id`, `hardware_model_id`, sensor profile and driver
profile in every `HARDWARE_PROFILE` heartbeat. It also reports a SHA-256 fingerprint calculated
from canonical JSON, so the backend rejects both a different profile ID and edited content that
improperly reused an existing ID.

## Validate without a terminal

On Windows, double-click `nexus-validate-hardware-profile.cmd` in the repository root. A passing
profile prints its normalized identity, controller, capabilities and limits. Build/upload scripts
also regenerate the firmware header automatically.

From a terminal:

```powershell
backend\.venv\Scripts\python.exe -m nexus_backend.hardware_profile --json
pio run --project-dir firmware
```

## Change the current ESP32 wiring or component

1. Copy the active JSON file and give it a new `nexus-profile-...` filename and `profile_id`.
2. Change the component, connection, pin, identity or safety fields in the copy.
3. Point `custom_nexus_hardware_profile` in `firmware/platformio.ini` at the new file.
4. Set `NEXUS_HARDWARE_PROFILE_PATH` to the same file for the backend.
5. Run the profile validator and the full project checks.
6. Rebuild and upload firmware. Never reuse a previous binary after changing a profile.
7. Confirm the UI shows matching reported and expected profile IDs before trusting telemetry.

Do not overwrite a profile already used for evidence. Hardware profiles are versioned artifacts;
an electrical, pin, component, identity or safety change requires a new profile ID.

## Add another board later

The profile is portable, but executable support still needs a board adapter:

| Controller class | Adapter form | Typical transport |
| --- | --- | --- |
| ESP32/ESP8266 | Arduino or RTOS firmware | Serial, MQTT |
| Arduino Uno/Mega/Nano | Small C++ firmware | Serial |
| Raspberry Pi | Linux NeXus Agent plus GPIO/I2C drivers | WebSocket, MQTT, HTTP |
| NVIDIA Jetson | Linux/Jetson NeXus Agent plus GPIO/I2C/GPU drivers | WebSocket, MQTT, HTTP |

An adapter is conformant only when it reports the selected profile, publishes valid canonical
telemetry, advertises only implemented capabilities, starts actuators off, enforces local safety
limits and passes the NeXus compatibility tests. Adding a profile alone must never imply that a
missing driver or unsafe voltage level is supported.

For Raspberry Pi and Jetson, explicitly describe 3.3 V GPIO limits and use level shifting where
required. Never infer electrical safety from a matching pin name.
