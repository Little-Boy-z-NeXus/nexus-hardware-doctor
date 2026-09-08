# MVP architecture

```text
ESP32 + INA219 + L298N + motor
              |
        telemetry transport
              |
      hardware model and rules
              |
     Nemotron through Nebius
              |
          orchestrator
              |
         safety policy
              |
       approved device tool
              |
    remeasure and update timeline
```

## Service boundaries

- Firmware owns measurements, actuator control, and a local PWM ceiling.
- Backend owns the hardware graph, deterministic electrical checks, model request, structured response validation, orchestration, and policy.
- Frontend owns the fixed topology, health state, telemetry, conversation, and action timeline.
- The model ranks hypotheses and proposes the next test or action. It does not define safety limits and cannot call an unregistered device command.

## MVP tool allowlist

- `get_hardware_graph`
- `get_telemetry`
- `read_gpio`
- `enable_driver`
- `set_pwm` with a configured range of 0–80 percent
- `run_motor_test`

The backend records proposed, approved, rejected, and executed actions. A repair is successful only after fresh telemetry passes the expected observation.
