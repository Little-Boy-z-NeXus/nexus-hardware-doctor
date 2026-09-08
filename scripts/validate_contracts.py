"""Validate frozen NeXus v1 schemas, fixtures, and cross-stack field names."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "nexus-contracts"
SCHEMA_ROOT = CONTRACT_ROOT / "v1" / "schemas"
FIXTURE_ROOT = CONTRACT_ROOT / "v1" / "fixtures"

SCHEMA_FIXTURES = {
    "hardware-model.schema.json": "hardware-model.example.json",
    "telemetry.schema.json": "telemetry.example.json",
    "tool.schema.json": "tool.example.json",
    "event.schema.json": "event.example.json",
}

SHARED_TELEMETRY_FIELDS = (
    "schema_version",
    "device_id",
    "hardware_model_id",
    "sample_id",
    "recorded_at",
    "sequence",
    "measurements",
    "bus_voltage_v",
    "current_ma",
    "power_mw",
    "pwm_percent",
    "driver_enabled",
    "motor_rpm",
    "quality",
    "signal_quality_percent",
    "source",
)

STACK_CONTRACT_FILES = (
    ROOT / "firmware" / "include" / "nexus_contract_v1.h",
    ROOT / "backend" / "src" / "nexus_backend" / "contracts.py",
    ROOT / "frontend" / "src" / "contracts" / "v1.ts",
)


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schemas_and_fixtures(errors: list[str]) -> None:
    for schema_name, fixture_name in SCHEMA_FIXTURES.items():
        schema_path = SCHEMA_ROOT / schema_name
        fixture_path = FIXTURE_ROOT / fixture_name

        if not schema_path.is_file():
            errors.append(f"Missing schema: {schema_path.relative_to(ROOT)}")
            continue
        if not fixture_path.is_file():
            errors.append(f"Missing fixture: {fixture_path.relative_to(ROOT)}")
            continue

        schema = load_json(schema_path)
        fixture = load_json(fixture_path)

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            errors.append(f"Invalid JSON Schema {schema_name}: {exc}")
            continue

        version_rule = schema.get("properties", {}).get("schema_version", {})
        if version_rule.get("const") != "1.0.0":
            errors.append(f"{schema_name} must freeze schema_version at 1.0.0")

        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for error in sorted(
            validator.iter_errors(fixture), key=lambda item: list(item.path)
        ):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{fixture_name}:{location}: {error.message}")


def validate_cross_stack_fields(errors: list[str]) -> None:
    for path in STACK_CONTRACT_FILES:
        if not path.is_file():
            errors.append(f"Missing stack contract mirror: {path.relative_to(ROOT)}")
            continue

        text = path.read_text(encoding="utf-8")
        missing = [field for field in SHARED_TELEMETRY_FIELDS if field not in text]
        if missing:
            errors.append(
                f"{path.relative_to(ROOT)} is missing shared telemetry fields: {', '.join(missing)}"
            )


def validate_fixture_links(errors: list[str]) -> None:
    hardware = load_json(FIXTURE_ROOT / "hardware-model.example.json")
    telemetry = load_json(FIXTURE_ROOT / "telemetry.example.json")
    tool = load_json(FIXTURE_ROOT / "tool.example.json")
    event = load_json(FIXTURE_ROOT / "event.example.json")

    if telemetry["device_id"] != hardware["device_id"]:
        errors.append("Telemetry device_id does not match the hardware model")
    if telemetry["hardware_model_id"] != hardware["hardware_model_id"]:
        errors.append("Telemetry hardware_model_id does not match the hardware model")
    if tool["device_id"] != hardware["device_id"]:
        errors.append("Tool call device_id does not match the hardware model")
    if event["device_id"] != hardware["device_id"]:
        errors.append("Lifecycle event device_id does not match the hardware model")
    if event["trace_id"] != tool["trace_id"]:
        errors.append("Lifecycle event trace_id does not match the related tool call")
    if event["related_tool_call_id"] != tool["tool_call_id"]:
        errors.append(
            "Lifecycle event related_tool_call_id does not match the tool call"
        )

    components = {
        component["component_id"]: {pin["pin_id"] for pin in component["pins"]}
        for component in hardware["components"]
    }
    for connection in hardware["connections"]:
        for side in ("from", "to"):
            component_id = connection[f"{side}_component_id"]
            pin_id = connection[f"{side}_pin"]
            if component_id not in components:
                errors.append(
                    f"Connection {connection['connection_id']} references unknown component {component_id}"
                )
            elif pin_id not in components[component_id]:
                errors.append(
                    f"Connection {connection['connection_id']} references unknown pin "
                    f"{component_id}.{pin_id}"
                )


def changed_files(base_ref: str) -> list[str]:
    if not base_ref or set(base_ref) == {"0"}:
        return []

    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{base_ref}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if exists.returncode != 0:
        return []

    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref, "HEAD", "--"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def validate_migration_note(base_ref: str, errors: list[str]) -> None:
    changed = changed_files(base_ref)
    schema_changes = [
        path for path in changed if path.startswith("nexus-contracts/v1/schemas/")
    ]
    if not schema_changes:
        return

    note_changes = [
        path
        for path in changed
        if path.startswith("nexus-contracts/migrations/")
        and path.endswith(".md")
        and not path.endswith("/README.md")
    ]
    if not note_changes:
        errors.append(
            "Frozen v1 schemas changed without a migration note in the same commit range"
        )
        return

    required_sections = ("Version", "Compatibility", "Owner", "Rollout", "Rollback")
    for note in note_changes:
        text = (ROOT / note).read_text(encoding="utf-8")
        missing = [
            section
            for section in required_sections
            if section.lower() not in text.lower()
        ]
        if missing:
            errors.append(f"{note} is missing migration details: {', '.join(missing)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-ref", default="", help="Git base SHA used to enforce migration notes"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []

    validate_schemas_and_fixtures(errors)
    validate_cross_stack_fields(errors)
    validate_fixture_links(errors)
    validate_migration_note(args.base_ref, errors)

    if errors:
        print("NeXus contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("NeXus contracts: PASS")
    print("Contract version: 1.0.0")
    print(f"Schemas validated: {len(SCHEMA_FIXTURES)}")
    print(f"Fixtures validated: {len(SCHEMA_FIXTURES)}")
    print(f"Stack mirrors checked: {len(STACK_CONTRACT_FILES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
