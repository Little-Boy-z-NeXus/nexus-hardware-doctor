# 0004 — Add three-wheel telemetry fields

- Date: 2026-10-30
- Owner: NeXus firmware, backend, and frontend maintainers
- Version: 1.0.0
- Compatibility: additive; all new measurement fields are optional

## Decision

The telemetry v1 schema gained nullable three-wheel RPM, PWM, total-current, PID, PS2,
drive-arm, and optional IMU measurement fields. Existing one-motor telemetry remains valid.
The new fields let the active ESP32-S3 three-wheel profile report control state and per-wheel
measurements without inventing missing readings. This note documents the schema extension
already published with the three-wheel implementation.

## Rollout

Publish the schema and backend validator before connecting firmware that emits the new fields.
Keep older firmware packets valid. Update the frontend to render only values present in validated
telemetry, and confirm the active firmware profile ID and hash match the backend profile.

## Rollback

Disable the three-wheel firmware producer and return to the earlier firmware/profile pair.
The optional schema fields may remain because they do not invalidate older packets. If a full
rollback is needed, revert producer and consumer changes together after confirming no active
device sends the new fields.
