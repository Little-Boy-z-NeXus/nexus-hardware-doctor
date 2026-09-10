"""Run the supervised U05 motor baseline and save local evidence."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean

import serial
from serial.tools import list_ports

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXPECTED_MODEL = "nexus-s3-ina226-l298n-motor-rig-v1"
MIN_BUS_VOLTAGE_V = 9.5
MAX_BUS_VOLTAGE_V = 14.5
MAX_CURRENT_MA = 1500.0
MIN_CURRENT_RISE_MA = 30.0
DEFAULT_PWM_PERCENT = 30
DEFAULT_DURATION_MINUTES = 30
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BaselineState:
    idle_current_ma: float = 0.0
    samples: list[dict[str, float | int | bool | None]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    firmware_errors: list[str] = field(default_factory=list)
    start_monotonic: float = 0.0
    stop_monotonic: float = 0.0


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def detect_port() -> str | None:
    ports = list(list_ports.comports())
    for item in ports:
        if item.vid == 0x303A and item.pid == 0x1001:
            return item.device
    for item in ports:
        description = (item.description or "").lower()
        if "ch343" in description or "usb serial" in description:
            return item.device
    return None


def parse_telemetry(line: str) -> dict[str, object] | None:
    if not line.startswith("{"):
        return None

    def reject_constant(value: str) -> None:
        raise ValueError(value)

    try:
        payload = json.loads(line, parse_constant=reject_constant)
    except (json.JSONDecodeError, ValueError):
        return None
    if payload.get("hardware_model_id") != EXPECTED_MODEL:
        return None
    measurements = payload.get("measurements")
    return payload if isinstance(measurements, dict) else None


def measurement_failures(
    measurements: dict[str, object],
    *,
    requested_pwm: int,
    idle_current_ma: float,
    check_current_rise: bool = True,
) -> list[str]:
    failures: list[str] = []
    try:
        bus_voltage = float(measurements["bus_voltage_v"])
        current = float(measurements["current_ma"])
        pwm = int(measurements["pwm_percent"])
        driver_enabled = bool(measurements["driver_enabled"])
    except (KeyError, TypeError, ValueError):
        return ["Telemetry thiếu trường đo bắt buộc."]

    if not math.isfinite(bus_voltage) or not math.isfinite(current):
        failures.append("INA226 trả về số không hữu hạn.")
    if not MIN_BUS_VOLTAGE_V <= bus_voltage <= MAX_BUS_VOLTAGE_V:
        failures.append(
            f"Điện áp {bus_voltage:.3f} V nằm ngoài "
            f"{MIN_BUS_VOLTAGE_V:.1f}–{MAX_BUS_VOLTAGE_V:.1f} V."
        )
    if current < -5:
        failures.append(f"Dòng âm {current:.1f} mA; kiểm tra chiều VIN+/VIN−.")
    if current > MAX_CURRENT_MA:
        failures.append(f"Quá dòng {current:.1f} mA > {MAX_CURRENT_MA:.0f} mA.")
    if not driver_enabled:
        failures.append("Firmware báo driver_enabled=false khi baseline đang chạy.")
    if pwm != requested_pwm:
        failures.append(f"Firmware báo PWM {pwm}% thay vì {requested_pwm}%.")
    if check_current_rise and current < idle_current_ma + MIN_CURRENT_RISE_MA:
        failures.append(
            f"Dòng chỉ tăng {current - idle_current_ma:.1f} mA; chưa chứng minh motor nhận tải."
        )
    return failures


def open_serial(port: str) -> serial.Serial:
    device = serial.Serial(port=None, baudrate=115_200, timeout=0.25, write_timeout=1)
    device.dtr = False
    device.rts = False
    device.port = port
    device.open()
    device.reset_input_buffer()
    return device


def write_command(device: serial.Serial, command: str) -> None:
    device.write(f"{command}\n".encode("ascii"))
    device.flush()


def append_evidence(handle, kind: str, value: object) -> None:
    entry = {"occurred_at": utc_now(), "kind": kind, "value": value}
    handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    handle.flush()


def await_idle_sample(
    device: serial.Serial, evidence_handle, timeout_seconds: float = 15
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    write_command(device, "NEXUS BASELINE STOP")
    while time.monotonic() < deadline:
        line = device.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue
        append_evidence(evidence_handle, "serial", line)
        payload = parse_telemetry(line)
        if payload is None:
            continue
        measurements = payload["measurements"]
        if (
            isinstance(measurements, dict)
            and not measurements.get("driver_enabled")
            and MIN_BUS_VOLTAGE_V
            <= float(measurements.get("bus_voltage_v", 0))
            <= MAX_BUS_VOLTAGE_V
        ):
            return payload
    raise RuntimeError("Không nhận được telemetry idle hợp lệ trong 15 giây.")


def run_baseline(
    *, port: str, duration_seconds: int, pwm_percent: int, evidence_path: Path
) -> BaselineState:
    state = BaselineState()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with evidence_path.open("w", encoding="utf-8", buffering=1) as evidence_handle:
        append_evidence(
            evidence_handle,
            "test_config",
            {"port": port, "duration_seconds": duration_seconds, "pwm_percent": pwm_percent},
        )
        with open_serial(port) as device:
            try:
                idle_payload = await_idle_sample(device, evidence_handle)
                idle_measurements = idle_payload["measurements"]
                assert isinstance(idle_measurements, dict)
                state.idle_current_ma = float(idle_measurements["current_ma"])
                append_evidence(evidence_handle, "idle_telemetry", idle_payload)

                print(
                    f"[PASS] Nguồn {float(idle_measurements['bus_voltage_v']):.3f} V; "
                    f"dòng idle {state.idle_current_ma:.1f} mA."
                )
                write_command(device, f"NEXUS BASELINE START {pwm_percent}")
                state.start_monotonic = time.monotonic()
                deadline = state.start_monotonic + duration_seconds
                next_keepalive = state.start_monotonic
                next_progress = state.start_monotonic
                last_telemetry = state.start_monotonic

                while time.monotonic() < deadline:
                    now = time.monotonic()
                    if now >= next_keepalive:
                        write_command(device, "NEXUS BASELINE KEEPALIVE")
                        next_keepalive = now + 1

                    line = device.readline().decode("utf-8", errors="replace").strip()
                    if line:
                        append_evidence(evidence_handle, "serial", line)
                        if "[ERROR]" in line:
                            state.firmware_errors.append(line)
                            state.failures.append(f"Firmware error: {line}")
                            break
                        payload = parse_telemetry(line)
                        if payload is not None:
                            last_telemetry = time.monotonic()
                            measurements = payload["measurements"]
                            assert isinstance(measurements, dict)
                            sample = {
                                "bus_voltage_v": float(measurements["bus_voltage_v"]),
                                "current_ma": float(measurements["current_ma"]),
                                "power_mw": float(measurements["power_mw"]),
                                "pwm_percent": int(measurements["pwm_percent"]),
                                "driver_enabled": bool(measurements["driver_enabled"]),
                                "motor_rpm": measurements.get("motor_rpm"),
                            }
                            state.samples.append(sample)
                            failures = measurement_failures(
                                measurements,
                                requested_pwm=pwm_percent,
                                idle_current_ma=state.idle_current_ma,
                                check_current_rise=(
                                    time.monotonic() - state.start_monotonic >= 3
                                ),
                            )
                            if failures:
                                state.failures.extend(failures)
                                break

                    if time.monotonic() - last_telemetry > 5:
                        state.failures.append("Mất telemetry quá 5 giây.")
                        break

                    if now >= next_progress:
                        elapsed = int(now - state.start_monotonic)
                        print(
                            f"[RUNNING] {elapsed}/{duration_seconds} giây · "
                            "theo dõi nhiệt và nhấn Ctrl+C/ngắt 12V nếu bất thường"
                        )
                        next_progress = now + 60
            except KeyboardInterrupt:
                state.failures.append("Người vận hành đã dừng bài test.")
            finally:
                try:
                    write_command(device, "NEXUS BASELINE STOP")
                    time.sleep(0.25)
                    write_command(device, "NEXUS BASELINE STOP")
                except serial.SerialException:
                    pass
                state.stop_monotonic = time.monotonic()
                append_evidence(evidence_handle, "result", state_to_dict(state))
    return state


def state_to_dict(state: BaselineState) -> dict[str, object]:
    duration = max(0.0, state.stop_monotonic - state.start_monotonic)
    return {
        "duration_seconds": round(duration, 2),
        "idle_current_ma": state.idle_current_ma,
        "sample_count": len(state.samples),
        "failures": state.failures,
        "firmware_errors": state.firmware_errors,
    }


def write_report(
    report_path: Path,
    state: BaselineState,
    *,
    duration_seconds: int,
    pwm_percent: int,
    evidence_path: Path,
    physical_checks: dict[str, bool],
) -> bool:
    electrical_pass = not state.failures and len(state.samples) >= max(1, duration_seconds - 5)
    physical_pass = all(physical_checks.values())
    passed = electrical_pass and physical_pass
    voltages = [float(sample["bus_voltage_v"]) for sample in state.samples]
    currents = [float(sample["current_ma"]) for sample in state.samples]
    duration_actual = max(0.0, state.stop_monotonic - state.start_monotonic)

    def stats(values: list[float]) -> str:
        if not values:
            return "không có mẫu"
        return f"min {min(values):.3f} · avg {fmean(values):.3f} · max {max(values):.3f}"

    checklist = "\n".join(
        f"- [{'x' if value else ' '}] {label}" for label, value in physical_checks.items()
    )
    failures = "\n".join(f"- {item}" for item in state.failures) or "- Không có"
    report = f"""# U05 — Hardware baseline report

- Kết quả: **{'PASS' if passed else 'CHƯA ĐẠT'}**
- Thời gian UTC: `{utc_now()}`
- Cấu hình: INA226 R100 → L298N → JGB37-520, nguồn 12 V
- PWM: `{pwm_percent}%`
- Thời lượng yêu cầu: `{duration_seconds}` giây
- Thời lượng thực tế: `{duration_actual:.1f}` giây
- Số mẫu hợp lệ: `{len(state.samples)}`
- Evidence NDJSON: `{evidence_path}`

## Kết quả điện

- Bus voltage (V): {stats(voltages)}
- Current (mA): {stats(currents)}
- Dòng idle: {state.idle_current_ma:.1f} mA

## Checklist vật lý do người vận hành xác nhận

{checklist}

## Lỗi

{failures}

## Điều kiện kết luận

Chỉ đánh dấu U05 là Đã làm khi bài test đủ 30 phút, báo cáo PASS, dây đã dán nhãn,
có ngắt nguồn 12 V nhanh, không có mùi/tiếng/nhiệt bất thường và video baseline đã lưu.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return passed


def ask_yes(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes", "co", "có"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="COM port; mặc định tự tìm ESP32-S3")
    parser.add_argument("--minutes", type=int, default=DEFAULT_DURATION_MINUTES)
    parser.add_argument("--seconds", type=int, help="Chỉ dùng cho kiểm tra ngắn khi phát triển")
    parser.add_argument("--pwm", type=int, default=DEFAULT_PWM_PERCENT)
    parser.add_argument("--yes", action="store_true", help="Bỏ prompt; không tạo U05 PASS vật lý")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    duration_seconds = args.seconds if args.seconds is not None else args.minutes * 60
    if duration_seconds < 10:
        print("[ERROR] Thời lượng tối thiểu là 10 giây.")
        return 2
    if not 1 <= args.pwm <= 80:
        print("[ERROR] PWM phải nằm trong 1..80%.")
        return 2

    preflight = {
        "Dây nguồn/tín hiệu đã dán nhãn": False,
        "ENA jumper đã tháo; GPIO12 nối ENA": False,
        "Trục motor thông thoáng và motor được cố định": False,
        "Có thể ngắt nguồn 12 V ngay lập tức": False,
        "Người vận hành ở cạnh bộ phần cứng trong suốt bài test": False,
    }
    if args.yes:
        print("[WARNING] Chế độ --yes chỉ kiểm tra điện; không xác nhận an toàn vật lý.")
    else:
        print("NeXus U05 chỉ chạy khi toàn bộ checklist dưới đây được xác nhận.")
        for label in preflight:
            preflight[label] = ask_yes(label)
        if not all(preflight.values()):
            print("[STOP] Checklist chưa đủ; motor không được khởi động.")
            return 3

    port = args.port or detect_port()
    if not port:
        print("[ERROR] Không tìm thấy GOOUUU ESP32-S3 qua USB.")
        return 4

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    evidence_path = REPOSITORY_ROOT / "artifacts" / "U05" / f"baseline-{timestamp}.ndjson"
    report_path = REPOSITORY_ROOT / "artifacts" / "U05" / f"baseline-{timestamp}.md"
    print(f"[NeXus] Bắt đầu baseline trên {port}, PWM {args.pwm}%, {duration_seconds} giây.")
    print("[SAFETY] Ctrl+C hoặc ngắt 12 V ngay nếu motor kẹt, nóng, rung hoặc có mùi lạ.")

    try:
        state = run_baseline(
            port=port,
            duration_seconds=duration_seconds,
            pwm_percent=args.pwm,
            evidence_path=evidence_path,
        )
    except (OSError, RuntimeError, serial.SerialException) as exc:
        print(f"[ERROR] Baseline không chạy được: {exc}")
        return 5

    physical_checks = dict(preflight)
    if not args.yes:
        physical_checks["Motor và L298N không quá nhiệt sau khi dừng"] = ask_yes(
            "Sau khi dừng: motor và L298N không quá nhiệt/mùi lạ"
        )
        physical_checks["Video baseline đã được quay và lưu"] = ask_yes(
            "Video đã quay đủ nguồn 12 V, UI realtime, motor chạy và nút ngắt"
        )

    passed = write_report(
        report_path,
        state,
        duration_seconds=duration_seconds,
        pwm_percent=args.pwm,
        evidence_path=evidence_path,
        physical_checks=physical_checks,
    )
    print(f"[{'PASS' if passed else 'NOT READY'}] Báo cáo: {report_path}")
    print(f"[EVIDENCE] Log: {evidence_path}")
    return 0 if passed else 6


if __name__ == "__main__":
    sys.exit(main())
