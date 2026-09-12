"""Validated loading and querying for the NeXus hardware-as-code profile."""

from __future__ import annotations

import json
import os
import sys
from argparse import ArgumentParser
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

DEFAULT_PROFILE_FILENAME = (
    "nexus-profile-goouuu-esp32-s3-ina226-l298n-jgb37-v1.json"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class HardwareProfileError(ValueError):
    """The hardware profile is absent, invalid or internally inconsistent."""


def _repository_paths() -> tuple[Path, Path]:
    return (
        REPOSITORY_ROOT / "nexus-hardware" / "v1" / "nexus-hardware-profile.schema.json",
        REPOSITORY_ROOT / "nexus-hardware" / "profiles" / DEFAULT_PROFILE_FILENAME,
    )


def _packaged_paths() -> tuple[Path, Path]:
    package = files("nexus_backend")
    return (
        Path(str(package.joinpath("profile_data/schema/nexus-hardware-profile.schema.json"))),
        Path(str(package.joinpath(f"profile_data/profiles/{DEFAULT_PROFILE_FILENAME}"))),
    )


def default_profile_path() -> Path:
    configured = os.getenv("NEXUS_HARDWARE_PROFILE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    repository_schema, repository_profile = _repository_paths()
    if repository_schema.is_file() and repository_profile.is_file():
        return repository_profile
    return _packaged_paths()[1]


def schema_path() -> Path:
    repository_schema, _ = _repository_paths()
    if repository_schema.is_file():
        return repository_schema
    return _packaged_paths()[0]


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HardwareProfileError(f"{label} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HardwareProfileError(
            f"{label} is not valid JSON at line {exc.lineno}, column {exc.colno}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise HardwareProfileError(f"{label} must contain one JSON object: {path}")
    return payload


def _json_pointer(parts: list[object]) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _validate_references(profile: dict[str, Any]) -> None:
    components = {item["component_id"]: item for item in profile["components"]}
    if len(components) != len(profile["components"]):
        raise HardwareProfileError("components must use unique component_id values")

    for role, component_id in profile["roles"].items():
        if component_id not in components:
            raise HardwareProfileError(
                f"hardware role {role} references unknown component {component_id}"
            )

    pin_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for component_id, item in components.items():
        pins = {pin["pin_id"]: pin for pin in item["pins"]}
        if len(pins) != len(item["pins"]):
            raise HardwareProfileError(
                f"component {component_id} must use unique pin_id values"
            )
        pin_maps[component_id] = pins

    connection_ids = [item["connection_id"] for item in profile["connections"]]
    if len(connection_ids) != len(set(connection_ids)):
        raise HardwareProfileError("connections must use unique connection_id values")

    for connection in profile["connections"]:
        endpoints: dict[str, dict[str, Any]] = {}
        for direction in ("from", "to"):
            endpoint = connection[direction]
            component = components.get(endpoint["component_id"])
            if component is None:
                raise HardwareProfileError(
                    f"connection {connection['connection_id']} references unknown component "
                    f"{endpoint['component_id']}"
                )
            pin = pin_maps[endpoint["component_id"]].get(endpoint["pin_id"])
            if pin is None:
                raise HardwareProfileError(
                    f"connection {connection['connection_id']} references unknown pin "
                    f"{endpoint['component_id']}.{endpoint['pin_id']}"
                )
            endpoints[direction] = pin

        source_voltage = endpoints["from"].get("logic_voltage_v")
        target_max = endpoints["to"].get("max_voltage_v")
        if source_voltage is not None and target_max is not None and source_voltage > target_max:
            raise HardwareProfileError(
                f"connection {connection['connection_id']} is electrically unsafe: "
                f"{source_voltage}V exceeds destination maximum {target_max}V"
            )
        if connection["signal_type"] == "i2c":
            target_voltage = endpoints["to"].get("logic_voltage_v")
            source_max = endpoints["from"].get("max_voltage_v")
            if target_voltage is not None and source_max is not None and target_voltage > source_max:
                raise HardwareProfileError(
                    f"connection {connection['connection_id']} is electrically unsafe: "
                    f"bidirectional {target_voltage}V exceeds source maximum {source_max}V"
                )

    for measurement in profile["telemetry"]["measurements"]:
        if measurement["component_id"] not in components:
            raise HardwareProfileError(
                f"telemetry field {measurement['field']} references unknown component "
                f"{measurement['component_id']}"
            )

    fields = [item["field"] for item in profile["telemetry"]["measurements"]]
    if len(fields) != len(set(fields)):
        raise HardwareProfileError("telemetry measurements must use unique field values")

    safety = profile["safety"]
    if safety["min_bus_voltage_v"] >= safety["max_bus_voltage_v"]:
        raise HardwareProfileError("min_bus_voltage_v must be lower than max_bus_voltage_v")


@lru_cache(maxsize=8)
def _load_hardware_profile_cached(profile_path: str, profile_mtime_ns: int) -> dict[str, Any]:
    del profile_mtime_ns  # The value participates in the cache key.
    path = Path(profile_path)
    profile = _read_json(path, label="Hardware profile")
    schema = _read_json(schema_path(), label="Hardware profile schema")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(profile), key=lambda item: list(item.absolute_path))
    if errors:
        first = errors[0]
        pointer = _json_pointer(list(first.absolute_path))
        raise HardwareProfileError(f"Invalid hardware profile at {pointer}: {first.message}")
    _validate_references(profile)
    return profile


def load_hardware_profile(path: str | Path | None = None) -> dict[str, Any]:
    """Load, schema-check and cross-reference-check one immutable profile snapshot."""
    resolved = Path(path).expanduser().resolve() if path else default_profile_path()
    try:
        mtime_ns = resolved.stat().st_mtime_ns
    except FileNotFoundError as exc:
        raise HardwareProfileError(f"Hardware profile does not exist: {resolved}") from exc
    return deepcopy(_load_hardware_profile_cached(str(resolved), mtime_ns))


def component(profile: dict[str, Any], component_id: str) -> dict[str, Any]:
    try:
        return next(item for item in profile["components"] if item["component_id"] == component_id)
    except StopIteration as exc:
        raise HardwareProfileError(f"Hardware profile has no component {component_id}") from exc


def profile_fingerprint(profile: dict[str, Any]) -> str:
    canonical = json.dumps(
        profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the stable UI/backend view derived from the machine-readable profile."""
    return {
        "profile_id": profile["profile_id"],
        "profile_schema_version": profile["schema_version"],
        "profile_sha256": profile_fingerprint(profile),
        "hardware_model_id": profile["hardware_model_id"],
        "controller": profile["controller"]["model"],
        "sensor": component(profile, profile["roles"]["power_monitor"])["model"],
        "driver": component(profile, profile["roles"]["motor_driver"])["model"],
        "motor": component(profile, profile["roles"]["actuator"])["model"],
        "power": component(profile, profile["roles"]["power"])["model"],
        "capabilities": list(profile["capabilities"]),
        "limits": {
            "min_bus_voltage_v": profile["safety"]["min_bus_voltage_v"],
            "max_bus_voltage_v": profile["safety"]["max_bus_voltage_v"],
            "max_current_ma": profile["safety"]["max_current_ma"],
            "max_pwm_percent": profile["safety"]["max_pwm_percent"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Validate one NeXus hardware-as-code JSON profile.")
    parser.add_argument("profile", nargs="?", help="Profile path; default uses the active profile")
    parser.add_argument("--json", action="store_true", help="Print the validated summary as JSON")
    args = parser.parse_args(argv)
    try:
        profile = load_hardware_profile(args.profile)
    except HardwareProfileError as exc:
        print(f"NEXUS HARDWARE PROFILE: FAIL — {exc}", file=sys.stderr)
        return 1

    summary = profile_summary(profile)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"NEXUS HARDWARE PROFILE: PASS — {summary['profile_id']}")
        print(f"Controller: {summary['controller']}")
        print(f"Hardware model: {summary['hardware_model_id']}")
        print(f"Capabilities: {', '.join(summary['capabilities'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
