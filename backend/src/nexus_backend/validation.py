"""Validate uncoerced JSON against the canonical, packaged v1 contracts."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_NAMES = frozenset({"hardware-model", "telemetry", "tool", "event"})
MAX_JSON_BYTES = 1_048_576
MAX_JSON_NODES = 20_000
MAX_JSON_DEPTH = 20
MAX_STRING_LENGTH = 8192
MAX_ERRORS = 20


class ContractValidationError(ValueError):
    """A bounded list of validation failures suitable for an HTTP 422 response."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors[:MAX_ERRORS]
        super().__init__("Contract validation failed")


def json_pointer(parts) -> str:
    """Return a JSON pointer without copying field values into error messages."""
    segments = []
    for part in parts:
        segment = str(part)
        if not _valid_utf8(segment):
            segment = "[invalid-unicode-key]"
        segments.append("/" + segment.replace("~", "~0").replace("/", "~1"))
    return "".join(segments)


def _valid_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check_json(payload: object) -> None:
    # Check iteratively before serialization/schema traversal to bound hostile nesting.
    pending = [(payload, (), 0)]
    nodes = 0
    while pending:
        value, path, depth = pending.pop()
        nodes += 1
        message = None
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            message = "JSON exceeds the supported size or nesting limit"
        elif isinstance(value, dict):
            if len(value) > MAX_JSON_NODES:
                message = "JSON exceeds the supported size or nesting limit"
            elif any(not isinstance(key, str) for key in value):
                message = "JSON object keys must be strings"
            elif any(not _valid_utf8(key) for key in value):
                message = "JSON field names must contain valid UTF-8 text"
            elif any(len(key) > 128 for key in value):
                message = "JSON field names must be at most 128 characters"
            else:
                pending.extend((item, (*path, key), depth + 1) for key, item in value.items())
        elif isinstance(value, list):
            if len(value) > MAX_JSON_NODES:
                message = "JSON exceeds the supported size or nesting limit"
            else:
                pending.extend(
                    (item, (*path, index), depth + 1) for index, item in enumerate(value)
                )
        elif isinstance(value, float) and not math.isfinite(value):
            message = "Numbers must be finite"
        elif isinstance(value, str):
            if not _valid_utf8(value):
                message = "Strings must contain valid UTF-8 text"
            elif len(value) > MAX_STRING_LENGTH:
                message = f"Strings must be at most {MAX_STRING_LENGTH} characters"
        elif value is not None and type(value) not in (str, int, float, bool):
            message = "Value must be a JSON value"
        if message:
            raise ContractValidationError([{"path": json_pointer(path), "message": message}])
    try:
        encoded = json.dumps(
            payload, allow_nan=False, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    except (ValueError, UnicodeError, OverflowError) as exc:
        raise ContractValidationError([{"path": "", "message": "Invalid JSON value"}]) from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ContractValidationError([{"path": "", "message": "JSON exceeds 1 MiB"}])


@lru_cache(maxsize=len(CONTRACT_NAMES))
def _validator(name: str) -> Draft202012Validator:
    if name not in CONTRACT_NAMES:
        raise ValueError("Unknown contract name")
    filename = f"{name}.schema.json"
    # Wheels contain the same canonical files via Hatch force-include, without
    # maintaining another source copy. Editable checkouts use the repository files.
    resource = files("nexus_backend").joinpath("schemas", filename)
    if resource.is_file():
        schema = json.loads(resource.read_text(encoding="utf-8"))
    else:
        schema_path = Path(__file__).resolve().parents[3] / "nexus-contracts/v1/schemas" / filename
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract(name: str, payload: dict) -> dict:
    """Return an isolated canonical JSON value; never coerce raw strings/numbers."""
    _check_json(payload)
    errors = []
    messages = {
        "additionalProperties": "Unknown fields are not allowed",
        "required": "A required field is missing",
        "type": "Value has the wrong JSON type",
        "const": "Unsupported contract version or constant value",
        "enum": "Value is not supported by this contract",
        "format": "Value has an invalid format",
        "pattern": "Value does not match the required identifier format",
        "oneOf": "Value does not match an allowed JSON type or format",
    }
    for error in _validator(name).iter_errors(payload):
        errors.append({
            "path": json_pointer(error.absolute_path),
            "message": messages.get(error.validator, "Value violates a contract constraint"),
        })
        if len(errors) == MAX_ERRORS:
            break
    if errors:
        raise ContractValidationError(errors)
    return deepcopy(payload)
