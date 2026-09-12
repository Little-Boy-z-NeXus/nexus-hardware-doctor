from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "nexus_configure_nebius.py"
SPEC = importlib.util.spec_from_file_location("nexus_configure_nebius", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_prepare_creates_complete_env_without_api_key(tmp_path: Path) -> None:
    template = tmp_path / ".env.example"
    template.write_text("# local\nNEXUS_ENV=old\nNEXUS_NEBIUS_API_KEY=\n", encoding="utf-8")
    env_file = tmp_path / ".env"

    result = MODULE.configure_environment(
        env_file, template, prompt_for_key=False, prompt=lambda _: "must-not-run"
    )

    content = env_file.read_text(encoding="utf-8")
    assert result.created is True
    assert result.key_configured is False
    assert "NEXUS_DB_PATH=artifacts/nexus-u07.sqlite3" in content
    assert "NEXUS_SERIAL_DEVICE_ID=\n" in content
    assert "NEXUS_ENABLE_LIVE_MODEL=true" in content
    assert "NEXUS_NEBIUS_API_KEY=\n" in content
    assert content.startswith("# local\n")


def test_prompted_key_is_inserted_once(tmp_path: Path) -> None:
    template = tmp_path / ".env.example"
    template.write_text("NEXUS_NEBIUS_API_KEY=\n", encoding="utf-8")
    env_file = tmp_path / ".env"

    result = MODULE.configure_environment(
        env_file, template, prompt_for_key=True, prompt=lambda _: "secret-test-key"
    )

    content = env_file.read_text(encoding="utf-8")
    assert result.key_configured is True
    assert content.count("NEXUS_NEBIUS_API_KEY=") == 1
    assert "NEXUS_NEBIUS_API_KEY=secret-test-key" in content


def test_existing_valid_key_is_preserved_without_prompt(tmp_path: Path) -> None:
    template = tmp_path / ".env.example"
    template.write_text("", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("NEXUS_NEBIUS_API_KEY=already-local\nCUSTOM=keep\n", encoding="utf-8")

    def fail_prompt(_: str) -> str:
        raise AssertionError("existing key must not prompt")

    result = MODULE.configure_environment(
        env_file, template, prompt_for_key=True, prompt=fail_prompt
    )

    content = env_file.read_text(encoding="utf-8")
    assert result.created is False
    assert result.key_configured is True
    assert "NEXUS_NEBIUS_API_KEY=already-local" in content
    assert "CUSTOM=keep" in content


def test_duplicate_managed_assignments_are_removed(tmp_path: Path) -> None:
    template = tmp_path / ".env.example"
    template.write_text("", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NEXUS_ENV=one\nNEXUS_ENV=two\nNEXUS_NEBIUS_API_KEY=secret\n"
        "NEXUS_NEBIUS_API_KEY=stale\n",
        encoding="utf-8",
    )

    MODULE.configure_environment(env_file, template, prompt_for_key=False)

    content = env_file.read_text(encoding="utf-8")
    assert content.count("NEXUS_ENV=") == 1
    assert content.count("NEXUS_NEBIUS_API_KEY=") == 1
    assert "NEXUS_ENV=development" in content
    assert "NEXUS_NEBIUS_API_KEY=secret" in content


@pytest.mark.parametrize("invalid_key", ["", "contains space", "line\nbreak", "x" * 4097])
def test_invalid_prompted_key_is_rejected_without_writing(
    tmp_path: Path, invalid_key: str
) -> None:
    template = tmp_path / ".env.example"
    template.write_text("NEXUS_NEBIUS_API_KEY=\n", encoding="utf-8")
    env_file = tmp_path / ".env"

    with pytest.raises(MODULE.ConfigurationError, match="NEXUS_API_KEY_INVALID"):
        MODULE.configure_environment(
            env_file, template, prompt_for_key=True, prompt=lambda _: invalid_key
        )

    assert not env_file.exists()
