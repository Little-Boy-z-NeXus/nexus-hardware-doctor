# NeXus diagrams — active INA219 three-wheel profile

These English diagrams describe the active
[`nexus-profile-esp32-s3-devkitc-ina219-dual-l298n-3wheel-ps2-v2.json`](../../nexus-hardware/profiles/nexus-profile-esp32-s3-devkitc-ina219-dual-l298n-3wheel-ps2-v2.json)
hardware adapter. Each PNG has an editable diagrams.net (`.drawio`) source beside it.

| Sheet | PNG | Editable source |
| --- | --- | --- |
| Power, protection and distribution | [`01-power-wiring.png`](01-power-wiring.png) | [`01-power-wiring.drawio`](01-power-wiring.drawio) |
| ESP32-S3 signals to INA219, PS2 and motor drivers | [`02-signal-wiring.png`](02-signal-wiring.png) | [`02-signal-wiring.drawio`](02-signal-wiring.drawio) |
| Motor outputs and Hall encoders | [`03-motor-encoder-wiring.png`](03-motor-encoder-wiring.png) | [`03-motor-encoder-wiring.drawio`](03-motor-encoder-wiring.drawio) |
| Runtime system design | [`04-system-design.png`](04-system-design.png) | [`04-system-design.drawio`](04-system-design.drawio) |
| Edge, local and cloud architecture | [`05-system-architecture.png`](05-system-architecture.png) | [`05-system-architecture.drawio`](05-system-architecture.drawio) |

The wiring sheets use one isolated row per signal or motor lead. The power sheet uses
shared net labels for ground to keep the drawing legible. It follows the physical
power guide in [`wiring-schematic-v9`](../wiring-schematic-v9/README.md).

GPIO11 is L298N #1 IN2 in the active v2 profile. Older wiring images that show
GPIO14 for that connection are superseded by these diagrams.

The architecture views show the intended current adapter and software boundaries.
They are not evidence that the INA219 three-wheel rig has passed physical acceptance;
replay data must remain labeled as replay. Verify labels, 5 V and 3.3 V rails, and
polarity on the actual parts before applying power.

Run `python docs/diagrams-v10/generate.py` to rebuild the `.drawio` files. Export
each file from diagrams.net to regenerate the PNG after a diagram change.
