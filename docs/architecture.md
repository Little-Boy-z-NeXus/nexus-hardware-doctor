# NeXus MVP architecture

Contract version: `1.0.0` — frozen on 2026-09-08.

## Runtime flow

```mermaid
flowchart LR
    HW["Hardware<br/>ESP32-S3 · INA226 R100 · L298N · Motor"]
    TEL["Telemetry<br/>schema v1"]
    API["Backend<br/>ingest · deterministic checks"]
    LLM["Nemotron on Nebius<br/>hypotheses · explanation"]
    ORC["Orchestrator<br/>state machine · trace"]
    SAFE["Safety Policy<br/>allowlist · limits · approval"]
    TOOL["Device Tool<br/>read · enable · PWM · test"]
    VERIFY["Verify<br/>fresh telemetry · expected result"]
    UI["Frontend<br/>health · graph · AI Doctor · timeline"]

    HW -->|telemetry.schema.json| TEL
    TEL --> API
    API -->|grounded context| LLM
    LLM -->|structured proposal| ORC
    ORC -->|tool.schema.json| SAFE
    SAFE -->|approved call| TOOL
    TOOL --> HW
    HW -->|new sample| VERIFY
    VERIFY -->|event.schema.json| API
    API --> UI
    API -->|hardware-model.schema.json| UI
```

The model can propose; only the deterministic safety policy can approve. A tool execution is not considered successful until Verify receives a newer telemetry sample and emits `verification.passed`.

## Auto Heal sequence

```mermaid
sequenceDiagram
    participant F as Firmware
    participant B as Backend
    participant N as Nemotron
    participant O as Orchestrator
    participant S as Safety Policy
    participant T as Device Tool
    participant V as Verify
    participant UI as Frontend

    F->>B: Telemetry v1
    B->>N: Hardware model + recent telemetry + symptom
    N-->>O: Diagnosis and proposed allowlisted action
    O->>S: Tool Call v1
    alt policy approves
        S->>T: Approved tool call
        T->>F: Execute bounded command
        F->>V: Fresh telemetry v1
        V->>B: verification.passed / verification.failed
    else policy rejects
        S->>B: action.rejected event
    end
    B->>UI: Lifecycle Event v1
```

## Contract boundary

The canonical files live under [`nexus-contracts/v1`](../nexus-contracts/v1/README.md):

| Interface | Canonical identity | Required shared keys |
| --- | --- | --- |
| Hardware model | `urn:nexus:contracts:v1:hardware-model` | `schema_version`, `hardware_model_id`, `device_id`, `components`, `connections`, `safety_limits` |
| Telemetry | `urn:nexus:contracts:v1:telemetry` | `schema_version`, `device_id`, `hardware_model_id`, `sample_id`, `recorded_at`, `sequence`, `measurements`, `quality` |
| Tool call | `urn:nexus:contracts:v1:tool` | `schema_version`, `tool_call_id`, `trace_id`, `device_id`, `tool_name`, `arguments`, `requires_verification` |
| Lifecycle event | `urn:nexus:contracts:v1:event` | `schema_version`, `event_id`, `trace_id`, `device_id`, `event_type`, `source`, `payload` |

The same names are represented in:

- firmware: `firmware/include/nexus_contract_v1.h`
- backend: `backend/src/nexus_backend/contracts.py`
- frontend: `frontend/src/contracts/v1.ts`

## Service boundaries

- Firmware owns measurements, actuator control, command execution, and a local PWM ceiling.
- Backend owns schema validation, the hardware graph, deterministic electrical checks, structured model responses, orchestration, policy, and the audit trail.
- Frontend owns presentation of the fixed topology, health state, telemetry, conversation, and Before/Action/After timeline.
- Nemotron ranks hypotheses and proposes the next test or action. It never defines safety limits and never calls a device directly.
- Safety Policy checks tool allowlist, requested arguments, hardware limits, and approval requirements.
- Verify compares fresh telemetry against the expected observation before an action becomes successful.

## Tool allowlist

- `get_hardware_graph`
- `get_telemetry`
- `read_gpio`
- `enable_driver`
- `set_pwm` from 0 to the model's `max_pwm_percent`
- `run_motor_test` within `max_motor_test_duration_ms`

Every proposal, approval, rejection, execution, and verification result shares one `trace_id`.

## Versioning and migrations

- `schema_version` uses semantic versioning and is mandatory on every envelope.
- Consumers reject unknown major versions and unexpected envelope fields.
- Breaking changes create `nexus-contracts/v2`; they never silently rewrite v1.
- Any intentional v1 schema edit must add a migration note under `nexus-contracts/migrations/` in the same commit. CI checks this rule.
