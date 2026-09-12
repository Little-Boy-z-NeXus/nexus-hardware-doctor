"""Print the serial port matching the active Hardware-as-Code profile."""

import json
import subprocess

from nexus_hardware_runtime import load_active_profile


def main() -> int:
    profile = load_active_profile()
    discovery = profile["transport"].get("discovery", {})
    usb_ids = {
        (item["vid"].removeprefix("0x").upper(), item["pid"].removeprefix("0x").upper())
        for item in discovery.get("usb", [])
    }
    descriptions = [item.lower() for item in discovery.get("description_contains", [])]
    result = subprocess.run(
        ["pio", "device", "list", "--json-output"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return 1

    try:
        ports = sorted(json.loads(result.stdout), key=lambda port: port["port"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return 1

    for port in ports:
        hardware_id = port.get("hwid", "").upper()
        for vid, pid in usb_ids:
            if f"VID:PID={vid}:{pid}" in hardware_id or f"VID_{vid}&PID_{pid}" in hardware_id:
                print(port["port"])
                return 0

    for port in ports:
        description = port.get("description", "").lower()
        if any(fragment in description for fragment in descriptions):
            print(port["port"])
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
