"""Print the serial port for the NeXus GOOUUU ESP32-S3 board."""

import json
import subprocess


def main() -> int:
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
        if "VID:PID=303A:1001" in hardware_id or "VID_303A&PID_1001" in hardware_id:
            print(port["port"])
            return 0

    for port in ports:
        description = port.get("description", "").lower()
        if "ch343" in description or "usb serial" in description:
            print(port["port"])
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
