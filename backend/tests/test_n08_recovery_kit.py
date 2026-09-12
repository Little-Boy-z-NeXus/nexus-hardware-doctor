import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    path = ROOT / "scripts" / name
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kit = load("nexus_n08_prepare_recovery_kit.py")
drill = load("nexus_n08_recovery_drill.py")


def test_recovery_bundle_has_checksums_and_safe_manifest(tmp_path, monkeypatch) -> None:
    build = tmp_path / "build"
    build.mkdir()
    for name in kit.FILES:
        (build / name).write_bytes(("nexus-" + name).encode())
    wiring = tmp_path / "wiring.svg"
    wiring.write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(kit, "ROOT", tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    wiring.rename(docs / "nexus-wiring-jgb37-520.svg")

    bundle = tmp_path / "bundle"
    manifest = kit.assemble(build, bundle)

    assert manifest["writes_enabled"] is False
    assert len(manifest["files"]) == 5
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])
    assert json.loads((bundle / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_recovery_telemetry_requires_safe_real_device_state() -> None:
    sample = {
        "hardware_model_id": drill.EXPECTED_MODEL,
        "measurements": {
            "bus_voltage_v": 12.1,
            "current_ma": 26.2,
            "pwm_percent": 0,
            "driver_enabled": False,
        },
        "quality": {"source": "device"},
    }
    assert drill.valid_recovery_sample(sample)
    for key, value in (
        ("bus_voltage_v", 0),
        ("current_ma", 1501),
        ("pwm_percent", 1),
        ("driver_enabled", True),
    ):
        changed = json.loads(json.dumps(sample))
        changed["measurements"][key] = value
        assert not drill.valid_recovery_sample(changed)
    sample["quality"]["source"] = "replay"
    assert not drill.valid_recovery_sample(sample)
