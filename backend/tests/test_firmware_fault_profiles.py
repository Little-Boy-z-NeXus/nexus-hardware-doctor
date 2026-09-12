from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_fault_profiles_are_allowlisted_and_test_build_only() -> None:
    source = (ROOT / "firmware" / "src" / "main.cpp").read_text(encoding="utf-8")
    platformio = (ROOT / "firmware" / "platformio.ini").read_text(encoding="utf-8")

    assert "NEXUS_ENABLE_FAULT_INJECTION" in source
    assert all(
        profile in source
        for profile in (
            "PWM_ZERO",
            "PWM_FREQUENCY_LOW",
            "CURRENT_OFFSET",
            "OUT2_OPEN_MANUAL",
        )
    )
    assert "NEXUS FAULT RESET" in source
    assert "nexus-goouuu-esp32-s3-n16r8-fault-test" in platformio
    assert platformio.count("-D NEXUS_ENABLE_FAULT_INJECTION=1") == 1


def test_fault_acceptance_requires_real_manual_out2_confirmation() -> None:
    runner = (ROOT / "scripts" / "nexus_n05_fault_acceptance.py").read_text(
        encoding="utf-8"
    )
    launcher = (ROOT / "nexus-run-n05-fault-acceptance.cmd").read_text(encoding="utf-8")

    assert "--manual-out2-confirmed" in runner
    assert "--manual-out2-confirmed" in launcher
    assert "Turn OFF 12 V" in launcher
    assert "reconnect OUT2/M-" in launcher
    assert "OUT2-open preflight failed" in runner
    assert 'result.terminal.get("response_type") != "result"' in runner
    assert "OPEN_OUTPUT_MAX_DELTA_MA = 10.0" in runner
    assert "for _attempt in range(2)" in runner
