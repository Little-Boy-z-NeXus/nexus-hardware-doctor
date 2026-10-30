# NeXus wiring schematic v7

Six circuit-style pages with explicit colored wires and no wire crossing through a module:

1. Power, fuse, relay, SW1, E-stop, buck, INA226 and PCT.
2. ESP32, INA226 low-voltage pins and PS2 receiver.
3. L298N #1, motor 1 phía trước and motor 2 phía sau trái.
4. L298N #2 and motor 3 phía sau phải.
5. Three Hall A/B encoders.
6. Physical triangular layout: M1 front, M2 rear-left, M3 rear-right. Thin power and signal
   corridors stay outside every module box.

Source of truth: `nexus-profile-goouuu-esp32-s3-ina226-dual-l298n-3wheel-ps2-v1.json`.

## PCT terminal map

- `nexus-pct-terminal-map-v1.html`: editable source listing every PCT-213/PCT-218 port.
- `nexus-pct-terminal-map-v1.png`: ready-to-view terminal map.
