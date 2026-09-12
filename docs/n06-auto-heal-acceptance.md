# N06 — Physical closed-loop Auto Heal acceptance

N06 proves only one software-controllable recovery on the frozen MVP rig: a PWM command that
is forced to zero by the supervised `PWM_ZERO` fault profile. It does not claim that NeXus can
repair a disconnected cable, failed driver, damaged motor, or unsafe power supply.

## One-click run

1. Keep the motor fixed to the bench and the 12 V disconnect within reach.
2. Close PlatformIO/Arduino Serial Monitor and the NeXus app.
3. Double-click `nexus-run-n06-auto-heal-acceptance.cmd` and confirm the safety prompt.
4. Stay beside the rig while five short recovery cycles run.

The batch file uploads the test-only fault firmware, runs the acceptance, then uploads the
default-safe firmware again. If the safe-firmware restore fails, disconnect 12 V motor power.

## Required sequence per cycle

1. Force `PWM 0` and driver `OFF`; read the INA226 idle current.
2. Apply `PWM_ZERO`, request 30% PWM, and prove the physical output remains unenergized.
3. Read voltage/current and pass the default-deny policy: 9.5–13.0 V, at most 1500 mA,
   start at PWM 0/OFF, requested PWM at most 30%, motor test at most 1000 ms.
4. Clear only the software fault, set PWM, enable the driver, and require current to rise by
   more than 5 mA above that cycle's idle reading.
5. Reset, run a bounded 500 ms motor test, and require the firmware to return PWM 0/OFF.
6. Append correlated requests, device responses, policy decision, before/after measurements,
   and the final reset to a local NDJSON audit file.

N06 passes only when `motor_fail → motor_pass` is demonstrated 5/5 and every cycle ends safe.
Reports are stored under ignored `artifacts/N06/`; raw hardware telemetry is never committed.

## Failure handling

- Any missing/non-finite INA226 reading, out-of-range voltage/current, incomplete response,
  insufficient current rise, timeout, or unsafe final state fails the run.
- The runner reuses the same request ID for one transport retry, relying on firmware
  idempotency so a motor command cannot be applied twice.
- A final `reset_driver` plus fault reset is attempted even after failure.
- This acceptance must not be run unattended and must not be used with a free-spinning rig.
