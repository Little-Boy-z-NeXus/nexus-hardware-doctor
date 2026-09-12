import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "firmware" / "protocol" / "v1"


def load_json(name: str) -> dict:
    return json.loads((PROTOCOL / name).read_text(encoding="utf-8"))


def errors(schema: dict, value: object) -> list:
    return list(Draft202012Validator(schema).iter_errors(value))


def test_all_documented_device_protocol_examples_validate() -> None:
    command_schema = load_json("command.schema.json")
    response_schema = load_json("response.schema.json")
    examples = load_json("examples.json")

    assert examples["commands"]
    assert examples["responses"]
    assert all(not errors(command_schema, item) for item in examples["commands"])
    assert all(not errors(response_schema, item) for item in examples["responses"])


def test_invalid_command_and_hardware_arguments_fail_closed() -> None:
    schema = load_json("command.schema.json")
    example = load_json("examples.json")["commands"][1]

    unknown = deepcopy(example)
    unknown["command"] = "write_any_gpio"
    too_much_pwm = deepcopy(example)
    too_much_pwm["arguments"]["pwm_percent"] = 81
    extra_argument = deepcopy(example)
    extra_argument["arguments"]["duration_ms"] = 500

    assert errors(schema, unknown)
    assert errors(schema, too_much_pwm)
    assert errors(schema, extra_argument)


def test_motor_test_has_bounded_duration_and_explicit_timeout() -> None:
    schema = load_json("command.schema.json")
    example = load_json("examples.json")["commands"][2]

    too_long = deepcopy(example)
    too_long["arguments"]["duration_ms"] = 3001
    missing_timeout = deepcopy(example)
    del missing_timeout["timeout_ms"]

    assert errors(schema, too_long)
    assert errors(schema, missing_timeout)


def test_firmware_implements_protocol_allowlist_and_idempotency_guards() -> None:
    source = (ROOT / "firmware" / "src" / "main.cpp").read_text(encoding="utf-8")
    commands = load_json("command.schema.json")["properties"]["command"]["enum"]

    assert all(f'command == "{name}"' in source for name in commands)
    assert "REQUEST_ID_CONFLICT" in source
    assert "duplicate" in source
    assert "NEXUS_ENABLE_COMMAND_WRITES" in source
    assert 'root["request_id"].is<const char*>()' in source
    assert 'root["request_id"].as<const char*>()' in source
    assert 'root["request_id"] | nullptr' not in source
