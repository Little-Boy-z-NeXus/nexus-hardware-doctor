"""Resolve the Hardware-as-Code profile selected by the firmware build.

This small dependency-free loader keeps Windows helper scripts on the same BOM as
PlatformIO. The backend performs the complete JSON Schema validation; helpers use
only validated fields and fail closed when the selection cannot be resolved.
"""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLATFORMIO_INI = REPOSITORY_ROOT / "firmware" / "platformio.ini"


class HardwareRuntimeError(RuntimeError):
    """The active Hardware-as-Code profile cannot be resolved safely."""


def active_profile_path() -> Path:
    configured = os.getenv("NEXUS_HARDWARE_PROFILE_PATH", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()

    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(PLATFORMIO_INI, encoding="utf-8"):
        raise HardwareRuntimeError("firmware/platformio.ini is unavailable")
    environments = parser.get("platformio", "default_envs", fallback="").split()
    if len(environments) != 1:
        raise HardwareRuntimeError("PlatformIO must select exactly one default hardware adapter")
    section = f"env:{environments[0]}"
    configured = parser.get(section, "custom_nexus_hardware_profile", fallback="").strip()
    if not configured:
        raise HardwareRuntimeError(f"{section} has no custom_nexus_hardware_profile")
    return (PLATFORMIO_INI.parent / configured).resolve()


def load_active_profile() -> dict[str, Any]:
    path = active_profile_path()
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HardwareRuntimeError(f"Cannot read active hardware profile: {path}") from exc
    if not isinstance(profile, dict):
        raise HardwareRuntimeError("Active hardware profile must be one JSON object")
    required = {"profile_id", "controller", "transport", "roles", "components", "safety"}
    missing = required - profile.keys()
    if missing:
        raise HardwareRuntimeError(
            "Active hardware profile is incomplete: " + ", ".join(sorted(missing))
        )
    return profile


def controller_gpio_pin_ids(profile: dict[str, Any]) -> set[str]:
    controller_id = profile["roles"]["controller"]
    result: set[str] = set()
    for connection in profile.get("connections", []):
        if connection["signal_type"] not in {"digital", "pwm", "analog"}:
            continue
        for endpoint in (connection["from"], connection["to"]):
            if endpoint["component_id"] == controller_id:
                result.add(endpoint["pin_id"])
    return result
