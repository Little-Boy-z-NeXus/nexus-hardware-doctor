# Migration 0003 — Use INA226 with R100 shunt

## Status

Accepted for the hackathon MVP on 2026-09-10.

## Change

Replace the INA219 current sensor in the frozen motor rig with the confirmed INA226 module carrying an `R100` (0.1 Ω) shunt. The wiring remains high-side on GPIO1/GPIO2 I²C: adapter `+12V → VIN+`, `VIN− → L298N +12V`, INA226 `VBUS → VIN−`, and all logic grounds common.

The hardware model identity changes from `nexus-s3-l298n-motor-rig-v1` to `nexus-s3-ina226-l298n-motor-rig-v1`. The sensor component ID changes from `ina219` to `ina226`. Telemetry schema version `1.0.0` and measurement field names remain unchanged.

## Firmware calibration

- shunt resistance: `0.1 Ω`
- current LSB: `0.1 mA`
- INA226 calibration register: `512`
- default I²C address: `0x40`
- expected manufacturer ID: `0x5449`
- expected die ID family: `0x226x`

INA219 and INA226 are not driver-compatible. Old firmware can produce a current approximately eight times too high and invalid bus voltage. Consumers must reject the old hardware model ID and operators must upload the INA226 firmware before collecting a new baseline.

## Consumer impact

- Firmware uses the INA226 register model and rejects failed I²C reads.
- Backend diagnostics and hardware metadata identify INA226.
- Frontend topology and troubleshooting labels identify INA226 R100.
- Existing saved logs remain historical evidence and are not rewritten.
