import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from nexus_backend.contracts import HardwareModel, LifecycleEvent, TelemetrySample, ToolCall

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "nexus-contracts" / "v1" / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "contract", "mutate", "error_type"),
    [
        (
            "hardware-model.example.json",
            HardwareModel,
            lambda payload: payload["safety_limits"].update(max_pwm_percent=101),
            "less_than_equal",
        ),
        (
            "telemetry.example.json",
            TelemetrySample,
            lambda payload: payload["quality"].update(signal_quality_percent=101),
            "less_than_equal",
        ),
        (
            "tool.example.json",
            ToolCall,
            lambda payload: payload.update(tool_name="delete_device"),
            "literal_error",
        ),
        (
            "event.example.json",
            LifecycleEvent,
            lambda payload: payload.update(undocumented_field=True),
            "extra_forbidden",
        ),
    ],
)
def test_invalid_contract_payload_is_rejected(
    fixture_name: str,
    contract: type[BaseModel],
    mutate,
    error_type: str,
) -> None:
    payload = deepcopy(load_fixture(fixture_name))
    mutate(payload)

    with pytest.raises(ValidationError) as captured:
        contract.model_validate(payload)

    assert error_type in {error["type"] for error in captured.value.errors()}
