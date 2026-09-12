"""Assemble a local, checksummed N08 recovery bundle from the safe firmware build."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "firmware" / ".pio" / "build" / "nexus-goouuu-esp32-s3-n16r8"
BUNDLE = ROOT / "artifacts" / "N08" / "recovery-kit"
FILES = ("bootloader.bin", "partitions.bin", "firmware.bin", "firmware.elf")


class RecoveryKitError(RuntimeError):
    """The safe build or another mandatory recovery asset is missing."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assemble(build: Path = BUILD, bundle: Path = BUNDLE) -> dict:
    missing = [name for name in FILES if not (build / name).is_file()]
    wiring = ROOT / "docs" / "nexus-wiring-jgb37-520.svg"
    if missing or not wiring.is_file():
        detail = ", ".join(missing) or str(wiring)
        raise RecoveryKitError(f"Missing recovery input: {detail}")
    bundle.mkdir(parents=True, exist_ok=True)
    entries = []
    for name in FILES:
        target = bundle / name
        shutil.copy2(build / name, target)
        entries.append({"name": name, "bytes": target.stat().st_size, "sha256": sha256(target)})
    wiring_target = bundle / wiring.name
    shutil.copy2(wiring, wiring_target)
    entries.append({
        "name": wiring_target.name,
        "bytes": wiring_target.stat().st_size,
        "sha256": sha256(wiring_target),
    })
    manifest = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "firmware_environment": "nexus-goouuu-esp32-s3-n16r8",
        "writes_enabled": False,
        "hardware_model_id": "nexus-s3-ina226-l298n-motor-rig-v1",
        "files": entries,
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (bundle / "README-FIRST.txt").write_text(
        "NeXus N08 recovery kit\n"
        "1. Keep 12 V motor power OFF while changing USB/wiring.\n"
        "2. From the repository, double-click nexus-run-n08-recovery-drill.cmd.\n"
        "3. Do not use these raw binaries with another board or flash layout.\n"
        "4. Verify manifest SHA-256 before copying the bundle to a backup USB drive.\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    try:
        manifest = assemble()
    except (OSError, RecoveryKitError) as exc:
        print(f"[NEXUS][ERROR][RECOVERY_KIT] {exc}")
        return 1
    print(f"[NEXUS][PASS] Recovery bundle: {BUNDLE}")
    for item in manifest["files"]:
        print(f"  {item['sha256']}  {item['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
