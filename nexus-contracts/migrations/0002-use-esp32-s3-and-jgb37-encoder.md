# 0002 — Use ESP32-S3 and JGB37-520 encoder

- Date: 2026-09-09
- Owner: Hiếu
- Version: 1.0.0
- Compatibility: corrective

## Decision

Replace the original ESP32 DevKit V1 with the GOOUUU Tech ESP32-S3-N16R8 while keeping the INA219, L298N, and JGB37-520 motor. The hardware model is now `nexus-s3-l298n-motor-rig-v1`. INA219 uses GPIO1/GPIO2, L298N channel A uses GPIO12/GPIO13/GPIO14, and encoder A/B use GPIO16/GPIO17. The schema envelope and telemetry field names do not change.

## Rollout

Update the hardware fixture, telemetry fixture, firmware build target, firmware pin map, frontend labels, and wiring diagram together. Build for the ESP32-S3 target before upload and verify boot with motor power disconnected. Keep `motor_rpm` nullable until pulse counting is implemented.

## Rollback

Disconnect motor power and restore the ESP32 DevKit V1 firmware target, hardware-model ID, GPIO mapping, fixture, UI labels, and diagram as one change. Do not reconnect external wiring until the checked-out diagram matches the physical board.
