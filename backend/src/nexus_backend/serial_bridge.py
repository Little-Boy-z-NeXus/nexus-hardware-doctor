"""Realtime serial bridge and deterministic MVP hardware diagnostics."""

from __future__ import annotations

import json
import math
import os
import threading
from collections import deque
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import TextIO

import serial
from pydantic import ValidationError
from serial.tools import list_ports

from nexus_backend.contracts import TelemetrySample

EXPECTED_HARDWARE_MODEL_ID = "nexus-s3-ina226-l298n-motor-rig-v1"
DEFAULT_BAUD_RATE = 115_200
MIN_BUS_VOLTAGE_V = 9.5
MAX_CURRENT_MA = 1_500.0
MAX_PWM_PERCENT = 80
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MEASUREMENT_DIAGNOSTIC_CODES = (
    "INA226_REFERENCE_INVALID",
    "MOTOR_SUPPLY_NOT_DETECTED",
    "MOTOR_UNDERVOLTAGE",
    "MOTOR_OVERCURRENT",
    "INA226_POLARITY_REVERSED",
    "PWM_SAFETY_LIMIT_EXCEEDED",
)

SnapshotSink = Callable[[dict[str, object]], None]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def reject_non_json_number(value: str) -> None:
    raise ValueError(f"{value} is not valid JSON")


class SerialBridge:
    """Own one ESP32 serial connection and expose a thread-safe live snapshot."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        configured_port: str | None = None,
        baud_rate: int = DEFAULT_BAUD_RATE,
        retry_seconds: float = 2.0,
        persist_logs: bool | None = None,
        log_directory: str | Path | None = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("NEXUS_SERIAL_ENABLED", "true").lower() not in {"0", "false", "no"}
        )
        self.configured_port = configured_port or os.getenv("NEXUS_SERIAL_PORT")
        self.baud_rate = baud_rate
        self.retry_seconds = retry_seconds
        self.persist_logs = (
            persist_logs
            if persist_logs is not None
            else os.getenv("NEXUS_LOG_ENABLED", "true").lower() not in {"0", "false", "no"}
        )
        configured_log_directory = log_directory or os.getenv("NEXUS_LOG_DIR") or "logs"
        self.log_directory = Path(configured_log_directory)
        if not self.log_directory.is_absolute():
            self.log_directory = REPOSITORY_ROOT / self.log_directory
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._sink: SnapshotSink | None = None
        self._latest_sequence: int | None = None
        self._latest_telemetry: dict[str, object] | None = None
        self._logs: deque[dict[str, object]] = deque(maxlen=160)
        self._diagnostics: dict[str, dict[str, object]] = {}
        self._log_sequence = 0
        self._log_file: TextIO | None = None
        self._log_path: Path | None = None
        self._connection: dict[str, object] = {
            "status": "disabled" if not self.enabled else "searching",
            "port": self.configured_port,
            "baud_rate": self.baud_rate,
            "last_seen_at": None,
            "log_file": None,
            "message": (
                "Serial bridge đã tắt bằng cấu hình."
                if not self.enabled
                else "Đang tìm GOOUUU ESP32-S3 qua USB..."
            ),
        }

    def set_sink(self, sink: SnapshotSink | None) -> None:
        self._sink = sink

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="nexus-serial-bridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._close_log_file()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            active = [item for item in self._diagnostics.values() if item["active"]]
            severity = "error" if any(item["severity"] == "error" for item in active) else (
                "warning" if active else "healthy"
            )
            return deepcopy(
                {
                    "connection": self._connection,
                    "telemetry": self._latest_telemetry,
                    "logs": list(self._logs),
                    "diagnostics": sorted(
                        self._diagnostics.values(),
                        key=lambda item: (not item["active"], item["last_seen_at"]),
                        reverse=False,
                    ),
                    "health": {
                        "status": severity,
                        "active_issue_count": len(active),
                    },
                    "hardware": {
                        "hardware_model_id": EXPECTED_HARDWARE_MODEL_ID,
                        "controller": "GOOUUU Tech ESP32-S3-N16R8",
                        "sensor": "INA226 (R100 shunt)",
                        "driver": "L298N",
                        "motor": "JGB37-520 12V + Hall encoder",
                        "power": "12V DC (không dùng pin vuông 9V)",
                        "limits": {
                            "min_bus_voltage_v": MIN_BUS_VOLTAGE_V,
                            "max_current_ma": MAX_CURRENT_MA,
                            "max_pwm_percent": MAX_PWM_PERCENT,
                        },
                    },
                }
            )

    def ingest_line(self, raw_line: str, *, port: str | None = None) -> None:
        """Parse one firmware line; public for deterministic tests and replay."""
        line = raw_line.strip()
        if not line:
            return

        level = self._infer_log_level(line)
        self._append_log(level, line, source="firmware")
        with self._lock:
            self._connection["last_seen_at"] = utc_now()
            if port:
                self._connection["port"] = port

        if "i2cWriteReadNonStop returned Error" in line or any(
            code in line
            for code in (
                "INA226_I2C_NO_ACK",
                "INA226_I2C_READ_FAILED",
                "INA226_CALIBRATION_FAILED",
                "INA226_INVALID_READING",
            )
        ):
            self._diagnose(
                "INA226_I2C_FAILURE",
                "error",
                "ina226",
                "Không đọc được INA226",
                "ESP32 không đọc hoặc cấu hình được INA226; firmware đã bỏ mẫu lỗi thay vì gửi số giả lên UI.",
                "Tắt nguồn motor; kiểm tra INA226 GND→ESP32 GND, VCC→3V3, SDA→GPIO1, SCL→GPIO2 rồi reset board.",
            )
            self._notify()
            return

        if "INA226_ID_MISMATCH" in line:
            self._diagnose(
                "INA226_ID_MISMATCH",
                "error",
                "ina226",
                "Module không phản hồi như INA226",
                "ESP32 nhận I2C ACK nhưng mã nhà sản xuất hoặc mã chip không đúng INA226.",
                "Đọc mã in trên IC; dùng đúng module INA226 tại địa chỉ 0x40 rồi reset board.",
            )
            self._notify()
            return

        if not line.startswith("{"):
            self._notify()
            return

        try:
            payload = json.loads(line, parse_constant=reject_non_json_number)
            sample = TelemetrySample.model_validate(payload)
            measurements = sample.measurements
            numeric_values = (
                measurements.bus_voltage_v,
                measurements.current_ma,
                measurements.power_mw,
            )
            if not all(math.isfinite(value) for value in numeric_values):
                raise ValueError("telemetry contains a non-finite number")
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            self._diagnose(
                "TELEMETRY_INVALID",
                "error",
                "esp32",
                "Gói telemetry không hợp lệ",
                f"Backend đã bỏ qua dòng lỗi để UI không hiển thị số sai: {str(exc)[:180]}",
                "Reset ESP32. Nếu thấy nan, kiểm tra lại INA226 rồi nạp firmware NeXus mới nhất.",
            )
            self._notify()
            return

        if sample.hardware_model_id != EXPECTED_HARDWARE_MODEL_ID:
            self._diagnose(
                "HARDWARE_MODEL_MISMATCH",
                "error",
                "esp32",
                "Firmware không đúng bộ phần cứng MVP",
                f"Nhận {sample.hardware_model_id}, cần {EXPECTED_HARDWARE_MODEL_ID}.",
                "Nạp firmware trong thư mục firmware của repository này vào GOOUUU ESP32-S3-N16R8.",
            )
            self._notify()
            return

        previous_sequence = self._latest_sequence
        self._latest_sequence = sample.sequence
        with self._lock:
            self._latest_telemetry = sample.model_dump(mode="json")
            self._connection.update(
                status="connected",
                message=f"Đang nhận telemetry realtime từ {self._connection.get('port') or 'ESP32'}.",
            )

        self._resolve("SERIAL_DEVICE_NOT_FOUND")
        self._resolve("SERIAL_PORT_BUSY")
        self._resolve("SERIAL_PORT_ERROR")
        self._resolve("TELEMETRY_TIMEOUT")
        self._resolve("TELEMETRY_INVALID")
        self._resolve("INA226_I2C_FAILURE")
        self._resolve("INA226_ID_MISMATCH")
        self._resolve("HARDWARE_MODEL_MISMATCH")
        self._evaluate_measurements(sample)

        if previous_sequence is not None and sample.sequence > previous_sequence + 1:
            self._diagnose(
                "TELEMETRY_SEQUENCE_GAP",
                "warning",
                "esp32",
                "Đã mất một số gói telemetry",
                f"Sequence nhảy từ {previous_sequence} lên {sample.sequence}.",
                "Kiểm tra cáp USB và đóng Serial Monitor khác. Nếu chỉ xảy ra một lần khi reset board thì có thể bỏ qua.",
            )
        else:
            self._resolve("TELEMETRY_SEQUENCE_GAP")
        self._notify()

    def _evaluate_measurements(self, sample: TelemetrySample) -> None:
        values = sample.measurements

        if values.bus_voltage_v <= 0.1 and abs(values.current_ma) > 5:
            self._diagnose(
                "INA226_REFERENCE_INVALID",
                "error",
                "ina226",
                "Số đo INA226 không hợp lý",
                f"Điện áp là {values.bus_voltage_v:.2f} V nhưng dòng vẫn là {values.current_ma:.1f} mA.",
                "Kiểm tra GND chung; nối VBUS của INA226 với VIN− (phía tải), nguồn +→VIN+, VIN−→L298N +12V.",
            )
        else:
            self._resolve("INA226_REFERENCE_INVALID")

        if values.bus_voltage_v <= 0.1:
            self._diagnose(
                "MOTOR_SUPPLY_NOT_DETECTED",
                "warning",
                "power",
                "Chưa thấy nguồn 12V của motor",
                "INA226 đang đọc xấp xỉ 0 V. Điều này bình thường nếu nguồn motor đang tắt.",
                "Nếu nguồn đã bật, kiểm tra VBUS INA226 đã được nối/jumper sang VIN− và GND đã dùng chung.",
            )
        else:
            self._resolve("MOTOR_SUPPLY_NOT_DETECTED")

        if values.driver_enabled and 0.1 < values.bus_voltage_v < MIN_BUS_VOLTAGE_V:
            self._diagnose(
                "MOTOR_UNDERVOLTAGE",
                "error",
                "power",
                "Nguồn motor quá thấp để chạy an toàn",
                f"Đang đo {values.bus_voltage_v:.2f} V, thấp hơn ngưỡng MVP {MIN_BUS_VOLTAGE_V:.1f} V.",
                "Tắt driver và dùng nguồn DC 12V đủ dòng; không dùng pin vuông 9V.",
            )
        else:
            self._resolve("MOTOR_UNDERVOLTAGE")

        if abs(values.current_ma) > MAX_CURRENT_MA:
            self._diagnose(
                "MOTOR_OVERCURRENT",
                "error",
                "motor",
                "Dòng motor vượt giới hạn",
                f"Đang đo {values.current_ma:.0f} mA, vượt ngưỡng {MAX_CURRENT_MA:.0f} mA.",
                "Tắt motor ngay; kiểm tra kẹt trục, chập OUT1/OUT2 và khả năng cấp dòng của L298N.",
            )
        else:
            self._resolve("MOTOR_OVERCURRENT")

        if values.current_ma < -5:
            self._diagnose(
                "INA226_POLARITY_REVERSED",
                "warning",
                "ina226",
                "INA226 có thể đang đấu ngược chiều",
                f"Dòng điện đang âm ({values.current_ma:.1f} mA).",
                "Kiểm tra lại nguồn + đi vào VIN+ và điện ra L298N đi từ VIN−.",
            )
        else:
            self._resolve("INA226_POLARITY_REVERSED")

        if values.pwm_percent > MAX_PWM_PERCENT:
            self._diagnose(
                "PWM_SAFETY_LIMIT_EXCEEDED",
                "error",
                "l298n",
                "PWM vượt giới hạn an toàn",
                f"Firmware báo PWM {values.pwm_percent}%, giới hạn MVP là {MAX_PWM_PERCENT}%.",
                "Tắt driver và nạp lại firmware có safety clamp của NeXus.",
            )
        else:
            self._resolve("PWM_SAFETY_LIMIT_EXCEEDED")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            port = self.configured_port or self._detect_port()
            if not port:
                self._set_connection(
                    "searching",
                    None,
                    "Chưa tìm thấy GOOUUU ESP32-S3. Đang tự động thử lại...",
                )
                if not self._is_active("SERIAL_DEVICE_NOT_FOUND"):
                    self._diagnose(
                        "SERIAL_DEVICE_NOT_FOUND",
                        "warning",
                        "esp32",
                        "Chưa tìm thấy ESP32 qua USB",
                        "Backend chưa thấy cổng USB VID:PID 303A:1001 của board.",
                        "Cắm cáp USB data vào board, chờ Windows tạo COM rồi giữ ứng dụng đang chạy để tự kết nối.",
                    )
                self._notify()
                self._stop_event.wait(self.retry_seconds)
                continue

            try:
                with serial.Serial(port, self.baud_rate, timeout=1) as device:
                    self._set_connection(
                        "connected",
                        port,
                        f"Đã mở {port}; đang chờ telemetry từ ESP32.",
                    )
                    self._resolve("SERIAL_DEVICE_NOT_FOUND")
                    self._resolve("SERIAL_PORT_BUSY")
                    self._resolve("SERIAL_PORT_ERROR")
                    self._append_log("info", f"Đã kết nối serial {port} @ {self.baud_rate} baud.", source="backend")
                    last_line = monotonic()
                    timeout_reported = False
                    while not self._stop_event.is_set():
                        raw = device.readline()
                        if raw:
                            last_line = monotonic()
                            timeout_reported = False
                            self.ingest_line(raw.decode("utf-8", errors="replace"), port=port)
                        elif monotonic() - last_line >= 4 and not timeout_reported:
                            timeout_reported = True
                            self._diagnose(
                                "TELEMETRY_TIMEOUT",
                                "error",
                                "esp32",
                                "ESP32 đã kết nối nhưng không gửi dữ liệu",
                                f"{port} mở được nhưng không có dòng mới trong 4 giây.",
                                "Nhấn RESET trên board. Nếu vẫn im lặng, nạp firmware NeXus mới nhất và kiểm tra baud 115200.",
                            )
                            self._notify()
            except serial.SerialException as exc:
                message = str(exc)
                is_busy = "Access is denied" in message or "PermissionError" in message
                code = "SERIAL_PORT_BUSY" if is_busy else "SERIAL_PORT_ERROR"
                title = "Cổng COM đang bị ứng dụng khác giữ" if is_busy else "Mất kết nối serial"
                action = (
                    "Đóng PlatformIO Serial Monitor/Arduino Serial Monitor rồi giữ NeXus đang chạy; backend sẽ tự kết nối lại."
                    if is_busy
                    else "Rút/cắm lại cáp USB; backend sẽ tự tìm lại cổng COM."
                )
                self._set_connection("error", port, title)
                self._diagnose(code, "error", "esp32", title, message[:220], action)
                self._notify()
                self._stop_event.wait(self.retry_seconds)

        self._set_connection("disconnected", None, "Serial bridge đã dừng.")

    def _detect_port(self) -> str | None:
        ports = list(list_ports.comports())
        for item in ports:
            if item.vid == 0x303A and item.pid == 0x1001:
                return item.device
        for item in ports:
            description = (item.description or "").lower()
            if "ch343" in description or "usb serial" in description:
                return item.device
        return None

    def _set_connection(self, status: str, port: str | None, message: str) -> None:
        with self._lock:
            self._connection.update(status=status, port=port, message=message)
        if status in {"searching", "error", "disconnected"}:
            for code in MEASUREMENT_DIAGNOSTIC_CODES:
                self._resolve(code)
        self._notify()

    def _append_log(self, level: str, message: str, *, source: str) -> None:
        with self._lock:
            self._log_sequence += 1
            entry = {
                "id": f"log-{self._log_sequence}",
                "occurred_at": utc_now(),
                "level": level,
                "source": source,
                "message": message[:2_000],
            }
            self._logs.append(entry)
            self._persist_log_entry(entry)

    def _persist_log_entry(self, entry: dict[str, object]) -> None:
        if not self.persist_logs:
            return

        try:
            if self._log_file is None:
                self.log_directory.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
                self._log_path = self.log_directory / f"hardware-live-{timestamp}.ndjson"
                self._log_file = self._log_path.open("a", encoding="utf-8", buffering=1)
                self._connection["log_file"] = str(self._log_path)
            self._log_file.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._log_file.flush()
        except OSError as exc:
            self.persist_logs = False
            self._connection["log_file"] = None
            self._connection["message"] = f"Không thể lưu log xuống máy: {exc}"

    def _close_log_file(self) -> None:
        with self._lock:
            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
            self._log_file = None

    def _diagnose(
        self,
        code: str,
        severity: str,
        component_id: str,
        title: str,
        message: str,
        action: str,
    ) -> None:
        now = utc_now()
        with self._lock:
            previous = self._diagnostics.get(code)
            continuing = previous is not None and bool(previous["active"])
            self._diagnostics[code] = {
                "code": code,
                "severity": severity,
                "component_id": component_id,
                "title": title,
                "message": message,
                "action": action,
                "first_seen_at": previous["first_seen_at"] if continuing else now,
                "last_seen_at": now,
                "occurrences": int(previous["occurrences"]) + 1 if continuing else 1,
                "active": True,
            }

    def _resolve(self, code: str) -> None:
        with self._lock:
            if code in self._diagnostics:
                self._diagnostics[code]["active"] = False

    def _is_active(self, code: str) -> bool:
        with self._lock:
            return code in self._diagnostics and bool(self._diagnostics[code]["active"])

    def _notify(self) -> None:
        sink = self._sink
        if sink:
            sink(self.snapshot())

    @staticmethod
    def _infer_log_level(line: str) -> str:
        lowered = line.lower()
        if "[e]" in lowered or "[error]" in lowered or "error" in lowered or "nan" in lowered:
            return "error"
        if "[w]" in lowered or "[warning]" in lowered or "warn" in lowered:
            return "warning"
        return "telemetry" if line.startswith("{") else "info"
