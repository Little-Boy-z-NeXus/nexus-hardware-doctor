# N08 — Demo recovery kit and three-minute drill

This runbook prepares the stable, default-safe firmware and the exact recovery path for the
frozen NeXus MVP. N08 remains incomplete until U07 is complete and a team member other than
the author records a successful recovery in under three minutes.

## Pack and label

- Primary rig: GOOUUU ESP32-S3-N16R8, INA226 R100, L298N, JGB37-520 12 V and encoder.
- Power: tested 12 V adapter, labelled quick-disconnect/emergency stop, and one compatible
  spare 12 V adapter with adequate current capacity.
- Cables: two tested USB data cables, labelled motor/encoder/I2C leads, spare jumper/screw
  terminal wires, small screwdriver, insulation tape and cable ties.
- Modules: one spare INA226 R100 and one spare L298N if available; keep modules in antistatic
  packaging and never hot-plug the power path.
- Reference: printed wiring diagram plus a clear real-rig photo saved locally as
  `artifacts/N08/wiring-reference.jpg`.
- Software: repository checkout, PlatformIO/Python/Node prerequisites, and the checksummed
  `artifacts/N08/recovery-kit` copied to a labelled backup USB drive.

Double-click `nexus-prepare-n08-recovery-kit.cmd` after every accepted firmware change. It
builds the `nexus-goouuu-esp32-s3-n16r8` default-safe environment, copies the binary/ELF,
bootloader, partition table and wiring diagram, and writes SHA-256 values to `manifest.json`.

## Recovery drill

1. Operator turns OFF 12 V motor power and checks the emergency disconnect.
2. Compare every wire against the diagram/photo; reseat only with power OFF.
3. Connect the tested USB data cable and double-click `nexus-run-n08-recovery-drill.cmd`.
4. Enter the operator's real name. The timer starts before firmware upload.
5. The script uploads default-safe firmware and waits for fresh INA226 telemetry at 9.5–13.0
   V, no more than 1500 mA, PWM 0, driver OFF and `quality.source=device`.
6. PASS requires completion in less than 180 seconds; evidence is written under
   `artifacts/N08/recovery-drill-*.json`.
7. Start `nexus-start-app.cmd`, open `/hardware`, and perform the normal pre-recording check.

## Stop conditions

Disconnect 12 V immediately for smoke, smell, heating, unexpected motion, reversed polarity,
bus outside 9.5–13.0 V, current over 1500 mA, or a failed safe-firmware upload. Do not substitute
another ESP32 board, sensor, driver, motor or battery during the hackathon MVP demo.

## Final acceptance still requiring people

- U07 vertical slice must pass 3/3 with runtime model proof.
- Another named team member must recover the kit using only this runbook in under three minutes.
- A current wiring photo and confirmation that the listed physical spares are packed are needed.
- Run the existing U05/N01 baseline check before recording if the wiring or a module changes.
