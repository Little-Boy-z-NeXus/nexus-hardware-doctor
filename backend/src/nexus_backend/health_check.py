"""Deterministic pre-power hardware health checks for the frozen MVP graph."""

from __future__ import annotations

import math
from copy import deepcopy

from nexus_backend.hardware import load_hardware_model
from nexus_backend.validation import ContractValidationError

HEALTH_CHECK_VERSION = "1.0.0"
PROFILE_KEYS = {"pin_profiles", "connection_readings", "required_connections"}
PIN_DIRECTIONS = {"input", "output", "bidirectional", "power_in", "power_out", "ground"}
SIGNAL_TYPES = {"i2c", "digital", "pwm", "power", "ground"}


def _finding(
    rule_id: str,
    severity: str,
    summary: str,
    evidence: dict,
    remediation: str,
) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "summary": summary,
        "evidence": deepcopy(evidence),
        "remediation": remediation,
    }


def _report(findings: list[dict]) -> dict:
    if any(item["severity"] == "error" for item in findings):
        status = "fail"
    elif findings:
        status = "warning"
    else:
        status = "pass"
    return {
        "health_check_version": HEALTH_CHECK_VERSION,
        "status": status,
        "finding_count": len(findings),
        "findings": findings,
    }


def _component_metadata_findings(payload: object) -> list[dict]:
    """Return actionable metadata findings before strict contract validation."""
    if not isinstance(payload, dict):
        return [_finding(
            "COMPONENT_METADATA_MISSING",
            "error",
            "Hardware model không phải JSON object",
            {"path": "/"},
            "Gửi hardware_model v1 đầy đủ trước khi cấp nguồn.",
        )]
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        return [_finding(
            "COMPONENT_METADATA_MISSING",
            "error",
            "Thiếu danh sách component",
            {"path": "/components"},
            "Khai báo controller, sensor, driver và motor cùng pin/capability của chúng.",
        )]

    findings = []
    required = ("component_id", "component_type", "model", "pins", "capabilities")
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            missing = list(required)
            component_id = f"component-{index}"
        else:
            missing = [
                field for field in required
                if field not in component
                or component[field] is None
                or (isinstance(component[field], (str, list)) and not component[field])
            ]
            component_id = component.get("component_id") or f"component-{index}"
        if missing:
            findings.append(_finding(
                "COMPONENT_METADATA_MISSING",
                "error",
                f"Component {component_id} thiếu metadata bắt buộc",
                {"path": f"/components/{index}", "component_id": component_id,
                 "missing_fields": missing},
                "Bổ sung component_id, component_type, model, pins và capabilities.",
            ))
    return findings


def _profile(profile: object) -> tuple[dict, dict, list[dict]]:
    if profile is None:
        profile = {}
    if not isinstance(profile, dict) or set(profile) - PROFILE_KEYS:
        raise ValueError("profile chỉ chấp nhận pin_profiles, connection_readings và required_connections")

    pin_profiles = {}
    for index, item in enumerate(profile.get("pin_profiles", [])):
        if not isinstance(item, dict):
            raise TypeError(f"pin_profiles[{index}] phải là object")
        required = {"component_id", "pin_id"}
        allowed = required | {"direction", "min_voltage_v", "max_voltage_v", "nominal_voltage_v"}
        if not required <= set(item) or set(item) - allowed:
            raise ValueError(f"pin_profiles[{index}] có field thiếu hoặc không được hỗ trợ")
        endpoint = (item["component_id"], item["pin_id"])
        if not all(isinstance(value, str) and value for value in endpoint) or endpoint in pin_profiles:
            raise ValueError(f"pin_profiles[{index}] có endpoint trống hoặc trùng")
        if "direction" in item and item["direction"] not in PIN_DIRECTIONS:
            raise ValueError(f"pin_profiles[{index}].direction không hợp lệ")
        for field in ("min_voltage_v", "max_voltage_v", "nominal_voltage_v"):
            if field in item:
                value = item[field]
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0):
                    raise ValueError(f"pin_profiles[{index}].{field} phải là số hữu hạn >= 0")
        if item.get("min_voltage_v", 0) > item.get("max_voltage_v", math.inf):
            raise ValueError(f"pin_profiles[{index}] có dải điện áp đảo ngược")
        pin_profiles[endpoint] = deepcopy(item)

    readings = {}
    for index, item in enumerate(profile.get("connection_readings", [])):
        if not isinstance(item, dict) or set(item) != {"connection_id", "voltage_v"}:
            raise ValueError(f"connection_readings[{index}] phải có connection_id và voltage_v")
        voltage = item["voltage_v"]
        if (not isinstance(item["connection_id"], str) or not item["connection_id"]
                or isinstance(voltage, bool) or not isinstance(voltage, (int, float))
                or not math.isfinite(voltage) or voltage < 0
                or item["connection_id"] in readings):
            raise ValueError(f"connection_readings[{index}] không hợp lệ hoặc bị trùng")
        readings[item["connection_id"]] = float(voltage)

    required_connections = profile.get("required_connections", [])
    if not isinstance(required_connections, list):
        raise TypeError("required_connections phải là list")
    required_fields = {
        "from_component_id", "from_pin", "to_component_id", "to_pin", "signal_type",
    }
    for index, item in enumerate(required_connections):
        if (not isinstance(item, dict) or set(item) != required_fields
                or not all(isinstance(item[field], str) and item[field] for field in required_fields)
                or item["signal_type"] not in SIGNAL_TYPES):
            raise ValueError(f"required_connections[{index}] không hợp lệ")
    return pin_profiles, readings, deepcopy(required_connections)


def _model_direction_conflict(signal_type: str, source_mode: str, target_mode: str) -> bool:
    if signal_type == "i2c":
        return source_mode != "i2c" or target_mode != "i2c"
    if signal_type == "digital":
        return source_mode not in {"output", "pwm"} or target_mode != "input"
    if signal_type == "pwm":
        return source_mode not in {"output", "pwm"} or target_mode not in {"input", "pwm"}
    if signal_type == "power":
        return source_mode not in {"power", "output"} or target_mode not in {"power", "input"}
    return source_mode not in {"ground", "output"} or target_mode not in {"ground", "power"}


def _profile_direction_conflict(source: dict | None, target: dict | None) -> bool:
    if not source or not target:
        return False
    source_direction = source.get("direction")
    target_direction = target.get("direction")
    return (
        source_direction == target_direction
        and source_direction in {"input", "output", "power_in", "power_out"}
    )


def run_health_check(hardware_model: object, profile: object = None) -> dict:
    """Evaluate the graph without touching hardware and return actionable findings."""
    findings = _component_metadata_findings(hardware_model)
    if findings:
        return _report(findings)

    try:
        model = load_hardware_model(hardware_model)
    except ContractValidationError as exc:
        for error in exc.errors:
            rule_id = (
                "REQUIRED_CONNECTION_MISSING"
                if error["path"].startswith("/connections/")
                else "HARDWARE_MODEL_INVALID"
            )
            findings.append(_finding(
                rule_id,
                "error",
                "Hardware model không hợp lệ",
                {"path": error["path"], "message": error["message"]},
                "Sửa hardware model theo schema v1 và chạy lại Health Check.",
            ))
        return _report(findings)

    pin_profiles, readings, required_connections = _profile(profile)
    pins = {
        (component["component_id"], pin["pin_id"]): pin
        for component in model["components"]
        for pin in component["pins"]
    }
    connections = {
        (
            item["from_component_id"], item["from_pin"],
            item["to_component_id"], item["to_pin"], item["signal_type"],
        ): item
        for item in model["connections"]
    }

    for required in required_connections:
        signature = tuple(required[field] for field in (
            "from_component_id", "from_pin", "to_component_id", "to_pin", "signal_type",
        ))
        if signature not in connections:
            findings.append(_finding(
                "REQUIRED_CONNECTION_MISSING",
                "error",
                "Thiếu kết nối bắt buộc",
                required,
                "Đấu đúng hai endpoint theo pin map, kiểm tra continuity rồi chạy lại.",
            ))

    for connection in model["connections"]:
        source_key = (connection["from_component_id"], connection["from_pin"])
        target_key = (connection["to_component_id"], connection["to_pin"])
        source_pin, target_pin = pins[source_key], pins[target_key]
        source_profile, target_profile = pin_profiles.get(source_key), pin_profiles.get(target_key)
        if (_model_direction_conflict(
                connection["signal_type"], source_pin["mode"], target_pin["mode"])
                or _profile_direction_conflict(source_profile, target_profile)):
            findings.append(_finding(
                "PIN_DIRECTION_CONFLICT",
                "error",
                "Hai đầu dây có hướng tín hiệu không tương thích",
                {"connection_id": connection["connection_id"],
                 "source_mode": source_profile.get("direction") if source_profile else source_pin["mode"],
                 "target_mode": target_profile.get("direction") if target_profile else target_pin["mode"]},
                "Đổi pin nguồn thành output và pin nhận thành input; I2C phải nối đúng SDA/SCL.",
            ))

        voltage = readings.get(connection["connection_id"])
        if voltage is None and source_profile:
            voltage = source_profile.get("nominal_voltage_v")
        if voltage is None or not target_profile:
            continue
        minimum = target_profile.get("min_voltage_v", 0)
        maximum = target_profile.get("max_voltage_v", math.inf)
        if minimum <= voltage <= maximum:
            continue
        is_power = connection["signal_type"] in {"power", "ground"}
        findings.append(_finding(
            "POWER_SUPPLY_INCOMPATIBLE" if is_power else "VOLTAGE_LIMIT_EXCEEDED",
            "error",
            "Nguồn cấp không tương thích" if is_power else "Điện áp vượt giới hạn pin",
            {"connection_id": connection["connection_id"], "observed_voltage_v": voltage,
             "target_min_voltage_v": minimum,
             "target_max_voltage_v": None if math.isinf(maximum) else maximum,
             "target_component_id": target_key[0], "target_pin": target_key[1]},
            "Tắt nguồn và dùng level shifter/regulator hoặc nguồn đúng định mức trước khi nối lại.",
        ))

    return _report(findings)
