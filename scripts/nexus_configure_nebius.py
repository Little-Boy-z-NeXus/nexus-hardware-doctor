"""Prepare the local U07 environment and optionally capture the Nebius API key."""

from __future__ import annotations

import argparse
import getpass
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_TEMPLATE = REPOSITORY_ROOT / ".env.example"
API_KEY_NAME = "NEXUS_NEBIUS_API_KEY"

# U07's frozen, non-secret MVP profile. The API key is handled separately and is never logged.
MANAGED_VALUES: tuple[tuple[str, str], ...] = (
    ("NEXUS_ENV", "development"),
    ("NEXUS_DB_PATH", "artifacts/nexus-u07.sqlite3"),
    ("NEXUS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
    ("NEXUS_NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
    (API_KEY_NAME, ""),
    ("NEXUS_NVIDIA_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b"),
    ("NEXUS_NEBIUS_ENABLE_THINKING", "true"),
    ("NEXUS_NEBIUS_MAX_OUTPUT_TOKENS", "4096"),
    ("NEXUS_ENABLE_LIVE_MODEL", "true"),
    ("NEXUS_MQTT_URL", "mqtt://localhost:1883"),
    ("NEXUS_SERIAL_ENABLED", "true"),
    ("NEXUS_SERIAL_PORT", ""),
    ("NEXUS_SERIAL_DEVICE_ID", ""),
    ("NEXUS_LOG_ENABLED", "true"),
    ("NEXUS_LOG_DIR", "logs"),
)


class ConfigurationError(RuntimeError):
    """A safe, actionable local-configuration failure."""


@dataclass(frozen=True)
class ConfigurationResult:
    env_file: Path
    created: bool
    key_configured: bool


def _assignment_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=(.*)$")


def _read_assignment(lines: list[str], name: str) -> str | None:
    pattern = _assignment_pattern(name)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None


def _valid_api_key(value: str) -> bool:
    return 1 <= len(value) <= 4096 and all(33 <= ord(character) <= 126 for character in value)


def _normalize_existing_key(value: str | None) -> str:
    if value is None:
        return ""
    candidate = value.strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1]
    return candidate if _valid_api_key(candidate) else ""


def _upsert_managed_values(source: str, values: tuple[tuple[str, str], ...]) -> str:
    lines = source.splitlines()
    positions: dict[str, int] = {}
    managed_names = {name for name, _ in values}
    retained: list[str] = []

    for line in lines:
        matched_name = next(
            (name for name in managed_names if _assignment_pattern(name).match(line)), None
        )
        if matched_name is None:
            retained.append(line)
            continue
        if matched_name not in positions:
            positions[matched_name] = len(retained)
            retained.append(line)

    for name, value in values:
        assignment = f"{name}={value}"
        if name in positions:
            retained[positions[name]] = assignment
        else:
            if retained and retained[-1] != "":
                retained.append("")
            positions[name] = len(retained)
            retained.append(assignment)

    return "\n".join(retained).rstrip() + "\n"


def configure_environment(
    env_file: Path,
    template: Path,
    *,
    prompt_for_key: bool,
    prompt: Callable[[str], str] = getpass.getpass,
) -> ConfigurationResult:
    created = not env_file.exists()
    if created:
        if not template.is_file():
            raise ConfigurationError("NEXUS_CONFIG_TEMPLATE_MISSING")
        source = template.read_text(encoding="utf-8-sig")
    else:
        source = env_file.read_text(encoding="utf-8-sig")

    api_key = _normalize_existing_key(_read_assignment(source.splitlines(), API_KEY_NAME))
    if not api_key and prompt_for_key:
        api_key = prompt("Paste Nebius API key (input is hidden): ").strip()
        if not _valid_api_key(api_key):
            raise ConfigurationError("NEXUS_API_KEY_INVALID")

    configured_values = tuple(
        (name, api_key if name == API_KEY_NAME else value) for name, value in MANAGED_VALUES
    )
    rendered = _upsert_managed_values(source, configured_values)
    env_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = env_file.with_name(f".{env_file.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
        os.replace(temporary, env_file)
    finally:
        temporary.unlink(missing_ok=True)

    return ConfigurationResult(env_file=env_file, created=created, key_configured=bool(api_key))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the ignored local .env for the frozen NeXus U07 MVP."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--prompt-for-key", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = configure_environment(
            args.env_file.resolve(),
            args.template.resolve(),
            prompt_for_key=args.prompt_for_key,
        )
    except (ConfigurationError, OSError, UnicodeError) as exc:
        code = str(exc) if isinstance(exc, ConfigurationError) else "NEXUS_CONFIG_WRITE_FAILED"
        print(f"[NEXUS][CONFIG][FAIL] {code}")
        return 1

    status = "READY" if result.key_configured else "PREPARED"
    print(f"[NEXUS][CONFIG][{status}] Local environment is configured.")
    print(f"NEXUS_API_KEY_CONFIGURED={'true' if result.key_configured else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
