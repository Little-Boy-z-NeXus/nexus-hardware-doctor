import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from nexus_backend.contracts import HardwareModel, LifecycleEvent, TelemetrySample, ToolCall

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "nexus-contracts" / "v1" / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "contract"),
    [
        ("hardware-model.example.json", HardwareModel),
        ("telemetry.example.json", TelemetrySample),
        ("tool.example.json", ToolCall),
        ("event.example.json", LifecycleEvent),
    ],
)
def test_v1_fixture_matches_backend_model(
    fixture_name: str,
    contract: type[BaseModel],
) -> None:
    payload = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))

    parsed = contract.model_validate(payload)

    assert parsed.schema_version == "1.0.0"
