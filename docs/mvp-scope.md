# MVP scope

The Google Sheet is the authoritative scope and backlog:

https://docs.google.com/spreadsheets/d/1EOCmOg-qVQ_2OJV1DkeH9ULjkR7oT8kNMNGyrTKTUFs/edit?gid=9060801#gid=9060801

## Locked product statement

NeXus turns one physical prototype into a software-readable hardware model. It observes live telemetry, asks a NVIDIA model on Nebius to reason through failures, and either gives a safe manual repair procedure or runs an approved software action and verifies recovery.

## Golden paths

1. Prevent: detect an unsafe 12 V rail mapped to an ESP32 GPIO before running the rig.
2. Manual Diagnose: use healthy supply and PWM data plus near-zero current to guide a human toward a disconnected motor output.
3. Auto Heal: detect a disabled driver or zero PWM, pass a proposed fix through policy, execute it, and prove recovery with motor motion and Before/After current.

No additional board, generalized circuit editor, SPICE simulation, unrestricted voltage control, predictive maintenance, or production platform belongs in the hackathon MVP.
