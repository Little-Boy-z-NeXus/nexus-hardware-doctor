"""Build bounded, source-labelled context data for later diagnosis integrations."""

from __future__ import annotations

from .hardware import load_hardware_model
from .validation import ContractValidationError, validate_contract

MAX_HISTORY_INPUT = 1000
MAX_CONTEXT_SAMPLES = 100
MAX_SYMPTOM_LENGTH = 2000


def build_context(
    hardware_model: dict, telemetry: list[dict], symptom: str, max_samples: int = 10
) -> dict:
    """Select one rig's recent samples without claiming unimplemented device tools.

    The caller supplies telemetry in oldest-to-newest receipt order. Preserve
    that durable order: device sequences reset at reboot and clocks can move
    backwards. Receipt order alone does not establish sample age or freshness.
    """
    if (not isinstance(symptom, str) or not symptom.strip()
            or len(symptom) > MAX_SYMPTOM_LENGTH):
        raise ContractValidationError([{
            "path": "/symptom", "message": "Symptom must contain 1–2000 characters",
        }])
    if type(max_samples) is not int or not 1 <= max_samples <= MAX_CONTEXT_SAMPLES:
        raise ContractValidationError([{
            "path": "/max_samples", "message": "max_samples must be an integer between 1 and 100",
        }])
    if not isinstance(telemetry, list) or len(telemetry) > MAX_HISTORY_INPUT:
        raise ContractValidationError([{
            "path": "/telemetry", "message": "Provide a list of at most 1000 telemetry samples",
        }])

    model = load_hardware_model(hardware_model)
    samples = []
    for raw in telemetry:
        sample = validate_contract("telemetry", raw)
        if (sample["device_id"], sample["hardware_model_id"]) == (
            model["device_id"], model["hardware_model_id"]
        ):
            samples.append(sample)

    recent = samples[-max_samples:]
    has_unsynchronised = any(sample["recorded_at"] is None for sample in recent)
    missing_metadata = [
        {
            "path": "/hardware_model/components/*/pins/*/electrical_ratings",
            "message": "Per-pin voltage/current ratings are absent; electrical safety is unknown",
        },
        {
            "path": "/hardware_model/safety_limits/max_bus_voltage_v",
            "message": "No maximum bus voltage is defined; do not infer an overvoltage limit",
        },
    ]
    if has_unsynchronised:
        missing_metadata.append({
            "path": "/telemetry/recorded_at",
            "message": "Device time is missing; sample age and boot identity cannot be established",
        })
    if not any(component["component_type"] == "power" for component in model["components"]):
        missing_metadata.append({
            "path": "/hardware_model/components",
            "message": "No explicit power-supply component or supply rating is declared",
        })

    return {
        "schema_version": model["schema_version"],
        "device_id": model["device_id"],
        "hardware_model_id": model["hardware_model_id"],
        "symptom": symptom.strip(),
        "hardware_model": model,
        "available_sensors": [
            {
                "component_id": component["component_id"],
                "model": component["model"],
                "capabilities": component["capabilities"],
            }
            for component in model["components"] if component["component_type"] == "sensor"
        ],
        "available_tools": ["get_hardware_graph", "get_telemetry"],
        "telemetry": recent,
        "missing_metadata": missing_metadata,
        "sources": {
            "symptom": "user",
            "hardware_model": "declared_configuration",
            "available_sensors": "declared_hardware_capabilities",
            "available_tools": "implemented_backend_read_operations",
            "telemetry": sorted({sample["quality"]["source"] for sample in recent}),
            "telemetry_order": "received",
        },
    }
