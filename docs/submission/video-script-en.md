# Final demo video — 2:55 maximum

The physical rig must remain on screen continuously from **00:15 through at least 01:20**. That is
65 seconds of unambiguous real-hardware footage. Record in landscape, show the E-stop before motor
power, and never stage an unsafe loose power wire.

| Time | Picture | Voice-over |
| --- | --- | --- |
| 00:00–00:15 | Title, team, one-sentence architecture | “NeXus is an AI doctor for physical hardware. It turns a real machine into a software-readable model, diagnoses faults with NVIDIA Nemotron on Nebius, and verifies recovery safely.” |
| 00:15–00:30 | Wide shot: complete three-wheel rig, battery disconnected; point to fuse, relay, E-stop, ESP32, sensor, drivers, motors | “This is our real ESP32-S3 platform: a fused 3S supply, INA226, two L298N drivers, three encoder motors, PS2 control, relay isolation, and emergency stop.” |
| 00:30–00:47 | Close-up of profile ID in UI and physical labels | “The wiring is not only a diagram. A versioned JSON profile defines every component, pin, connection, limit, and telemetry field. Firmware, backend, and UI all load the same source of truth.” |
| 00:47–01:05 | Connect power safely; show UI change from disconnected to live | “When power and USB are connected, the backend verifies firmware and sensor identity, reads serial telemetry, stores the log, and streams it to the browser. Missing or stale signal wires are reported separately from a powered-off motor rail.” |
| 01:05–01:20 | Wheels raised; supervised low-speed PS2 command; show three RPM readings and stop | “With the wheels raised, the PS2 controller arms a bounded test. NeXus shows each wheel’s RPM instead of treating current as proof of motion. Releasing control returns the vehicle to fail-safe stop.” |
| 01:20–01:42 | Hardware Graph and exact wiring guide | “The Hardware Graph scales to a larger BOM, and the wiring view shows exact endpoints, signal type, and declared wire color. A human or an agent can inspect the same machine-readable topology.” |
| 01:42–02:08 | Create or select a safe fault; open AI Doctor Live; send question; show returned evidence | “For diagnosis, Nemotron receives only grounded hardware context, recent telemetry, and allowlisted tools. It ranks hypotheses and explains the next safe step. It never sets electrical limits and never talks directly to the motor.” |
| 02:08–02:30 | Show diagnosis timeline and a rejected/approved action | “Every proposal enters a bounded orchestrator. Deterministic policy approves or rejects the tool call, and the timeline records telemetry, diagnosis, policy, execution, and verification under one trace.” |
| 02:30–02:47 | Show Before/After verification, Manual and Auto Treatment cards, export evidence | “NeXus does not call an action successful until a newer sample proves the expected change. Manual Treatment gives a controlled repair sequence; Auto Treatment remains locked when the physical safety conditions are not met.” |
| 02:47–02:55 | Product name and impact | “NeXus reduces guesswork without giving AI unsafe authority. One machine today; a reusable hardware adapter platform next.” |

## Recording checklist

- Show `source=device`, device/profile identity, and live timestamps in the same take.
- Keep secrets, raw prompts, terminal environment variables, and private URLs out of frame.
- Use the final `main` commit and run `nexus-run-submission-gate.cmd` first.
- Add `subtitles-en.srt`, verify the total duration is below 03:00, and test the public link in an
  incognito window.
