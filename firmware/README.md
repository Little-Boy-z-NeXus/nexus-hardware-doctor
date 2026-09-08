# nexus-firmware

Owns ESP32 telemetry and the small set of device actions allowed by the MVP policy.

## Responsibilities

- read INA219 bus voltage and current
- report PWM duty, driver enable, and motor state
- accept only versioned, authenticated commands from the backend
- clamp PWM to the firmware safety ceiling
- emit structured Before/After telemetry for the action timeline

## Local setup

Install PlatformIO, connect the ESP32 DevKit V1, then run:

```bash
pio run
pio run --target upload
pio device monitor
```

Pin assignments and calibration values must be recorded in `docs/hardware-baseline.md` once the physical rig is assembled.
