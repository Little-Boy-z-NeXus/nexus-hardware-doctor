"""Load the single-rig hardware graph and validate its semantic references."""

from __future__ import annotations

from .validation import ContractValidationError, validate_contract

MAX_COMPONENTS = 64
MAX_PINS_PER_COMPONENT = 64
MAX_CONNECTIONS = 256
MAX_CAPABILITIES = 32


def load_hardware_model(payload: dict) -> dict:
    """Reject ambiguous identities, dangling wires and unusable model metadata."""
    model = validate_contract("hardware-model", payload)
    errors = []

    def reject(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    if len(model["components"]) > MAX_COMPONENTS:
        reject("/components", f"At most {MAX_COMPONENTS} components are supported")
    if len(model["connections"]) > MAX_CONNECTIONS:
        reject("/connections", f"At most {MAX_CONNECTIONS} connections are supported")
    if not model["name"].strip() or len(model["name"]) > 256:
        reject("/name", "A nonblank name of at most 256 characters is required")

    component_pins = {}
    for index, component in enumerate(model["components"]):
        path = f"/components/{index}"
        component_id = component["component_id"]
        if component_id in component_pins:
            reject(f"{path}/component_id", "Component IDs must be unique")
        if not component["model"].strip() or len(component["model"]) > 256:
            reject(f"{path}/model", "A nonblank model name of at most 256 characters is required")
        if not 1 <= len(component["pins"]) <= MAX_PINS_PER_COMPONENT:
            reject(f"{path}/pins", f"Between 1 and {MAX_PINS_PER_COMPONENT} pins are required")
        if not 1 <= len(component["capabilities"]) <= MAX_CAPABILITIES:
            reject(f"{path}/capabilities", f"Between 1 and {MAX_CAPABILITIES} capabilities required")
        for cap_index, capability in enumerate(component["capabilities"]):
            if not capability.strip() or len(capability) > 128:
                reject(f"{path}/capabilities/{cap_index}", "Capability must contain 1–128 characters")
        pins = set()
        for pin_index, pin in enumerate(component["pins"]):
            pin_path = f"{path}/pins/{pin_index}"
            if pin["pin_id"] in pins:
                reject(f"{pin_path}/pin_id", "Pin IDs must be unique within each component")
            for field in ("pin_id", "label"):
                if not pin[field].strip() or len(pin[field]) > 128:
                    reject(f"{pin_path}/{field}", "Pin metadata must contain 1–128 characters")
            pins.add(pin["pin_id"])
        component_pins[component_id] = pins

    connection_ids = set()
    for index, connection in enumerate(model["connections"]):
        path = f"/connections/{index}"
        if connection["connection_id"] in connection_ids:
            reject(f"{path}/connection_id", "Connection IDs must be unique")
        connection_ids.add(connection["connection_id"])
        for side in ("from", "to"):
            component_field = f"{side}_component_id"
            pin_field = f"{side}_pin"
            component_id = connection[component_field]
            if component_id not in component_pins:
                reject(f"{path}/{component_field}", "Connection references an unknown component")
            elif connection[pin_field] not in component_pins[component_id]:
                reject(f"{path}/{pin_field}", "Connection references an unknown component pin")
    if errors:
        raise ContractValidationError(errors)
    return model
