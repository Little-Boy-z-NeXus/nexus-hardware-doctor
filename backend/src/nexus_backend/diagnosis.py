"""Strict diagnosis proposals and an explicitly simulated rule-based planner."""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from importlib.resources import files

from jsonschema import Draft202012Validator

from .context import build_context
from .provider import NebiusProvider, ProviderConfig, ProviderError
from .validation import ContractValidationError, validate_contract

PROMPT_VERSION = "diagnosis-v2"
IDENTIFIER = {"type": "string", "minLength": 1, "maxLength": 128,
              "pattern": "^[A-Za-z0-9_.:-]+$"}
NUMBER = {"type": "number", "minimum": 0, "maximum": 1}
HYPOTHESIS_IDS = ["normal", "power", "pwm", "driver", "wiring", "overvoltage",
                  "calibration", "sensor", "tool_error", "motor"]
TOOL_ARGUMENTS = {
    "get_hardware_graph": ({}, []),
    "get_telemetry": ({}, []),
    "read_gpio": ({"pin_id": IDENTIFIER}, ["pin_id"]),
    "enable_driver": ({"enabled": {"type": "boolean"}}, ["enabled"]),
    "set_pwm": ({"pwm_percent": {"type": "integer", "minimum": 0, "maximum": 100}},
                ["pwm_percent"]),
    "run_motor_test": ({
        "duration_ms": {"type": "integer", "minimum": 100, "maximum": 10000},
        "pwm_percent": {"type": "integer", "minimum": 0, "maximum": 100},
    }, ["duration_ms"]),
}


def _tool_schema(name, properties, required):
    return {"type": "object", "additionalProperties": False,
            "required": ["tool_name", "arguments"], "properties": {
                "tool_name": {"const": name},
                "arguments": {"type": "object", "additionalProperties": False,
                              "properties": properties, "required": required},
            }}


PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["hypotheses", "next_tool", "confidence", "user_message", "stop_condition"],
    "properties": {
        "hypotheses": {"type": "array", "minItems": 1, "maxItems": 10, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "label", "confidence", "evidence_ids"],
            "properties": {
                "id": IDENTIFIER,
                "label": {"type": "string", "minLength": 1, "maxLength": 120},
                "confidence": NUMBER,
                "evidence_ids": {"type": "array", "maxItems": 20, "uniqueItems": True,
                                 "items": IDENTIFIER},
            },
        }},
        "next_tool": {"anyOf": [{"type": "null"}] + [
            _tool_schema(name, *arguments) for name, arguments in TOOL_ARGUMENTS.items()
        ]},
        "confidence": NUMBER,
        "user_message": {"type": "string", "minLength": 1, "maxLength": 280},
        "stop_condition": {"enum": ["continue", "diagnosed", "needs_manual",
                                    "insufficient_evidence"]},
    },
}
_VALIDATOR = Draft202012Validator(PLAN_SCHEMA)


class PlanValidationError(ValueError):
    def __init__(self):
        super().__init__("The diagnosis plan or its evidence is invalid.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PlanValidationError()
        result[key] = value
    return result


def validate_plan(raw) -> dict:
    """Validate exact proposal shape without trusting provider-side JSON mode."""
    try:
        if isinstance(raw, str):
            if len(raw.encode()) > 32768:
                raise PlanValidationError()
            raw = json.loads(raw, object_pairs_hook=_unique_object)
        serialized = json.dumps(raw, allow_nan=False)
        if len(serialized.encode()) > 32768 or not _VALIDATOR.is_valid(raw):
            raise PlanValidationError()
        ids = [hypothesis["id"] for hypothesis in raw["hypotheses"]]
        if len(ids) != len(set(ids)):
            raise PlanValidationError()
        if (raw["stop_condition"] == "continue") != (raw["next_tool"] is not None):
            raise PlanValidationError()
        if raw["next_tool"]:
            arguments = raw["next_tool"]["arguments"]
            if any(type(arguments[key]) is not int
                   for key in ("pwm_percent", "duration_ms") if key in arguments):
                raise PlanValidationError()
        for item in [raw["user_message"]] + [h["label"] for h in raw["hypotheses"]]:
            item.encode("utf-8")
            if (not item.strip() or any(ord(char) < 32 for char in item)
                    or re.search(r"</?think>|chain.of.thought|reasoning_content", item,
                                 re.IGNORECASE)):
                raise PlanValidationError()
        return deepcopy(raw)
    except (ValueError, TypeError, RecursionError, KeyError, AttributeError):
        raise PlanValidationError() from None


_FACT_NUMBERS = {"reference_current_ma", "driver_output_voltage_v", "source_voltage_v",
                 "pin_max_voltage_v"}
_FACT_BOOLS = {"motor_output_connected", "sensor_timed_out"}


def prepare_inputs(context: dict, observations: list[dict]) -> tuple[dict, list[dict]]:
    """Project supported measured facts; dataset labels and unknown fields never reach a model."""
    try:
        if not isinstance(observations, list) or len(observations) > 64:
            raise PlanValidationError()
        clean = build_context(context["hardware_model"], context.get("telemetry", []),
                              context["symptom"], max_samples=20)
        available = context.get("available_tools", clean["available_tools"])
        if (not isinstance(available, list) or len(available) > len(TOOL_ARGUMENTS)
                or any(tool not in TOOL_ARGUMENTS for tool in available)):
            raise PlanValidationError()
        clean["available_tools"] = list(dict.fromkeys(available))
        normalized = []
        seen = set()
        for observation in observations:
            evidence_id = observation["evidence_id"]
            if (not isinstance(evidence_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", evidence_id)
                    or evidence_id in seen):
                raise PlanValidationError()
            seen.add(evidence_id)
            status = observation["status"]
            source = observation.get("source")
            if status not in ("succeeded", "failed", "blocked"):
                raise PlanValidationError()
            if source not in ("device", "simulator", "replay", "declared_configuration"):
                raise PlanValidationError()
            if observation.get("device_id", clean["device_id"]) != clean["device_id"]:
                raise PlanValidationError()
            data = observation.get("data", {})
            if not isinstance(data, dict):
                raise PlanValidationError()
            if source == "declared_configuration":
                config_read = (
                    observation.get("tool_name") == "get_hardware_graph"
                    and data.keys() <= {"hardware_model", "scope"}
                    and data.get("scope", "declared_configuration") == "declared_configuration"
                )
                failed_read = status in ("failed", "blocked") and not data
                if not config_read and not failed_read:
                    raise PlanValidationError()
            facts = {}
            for key in _FACT_NUMBERS & data.keys():
                value = data[key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise PlanValidationError()
                facts[key] = value
            for key in _FACT_BOOLS & data.keys():
                if type(data[key]) is not bool:
                    raise PlanValidationError()
                facts[key] = data[key]
            if "sample" in data:
                sample = validate_contract("telemetry", data["sample"])
                if (sample["device_id"] != clean["device_id"]
                        or sample["hardware_model_id"] != clean["hardware_model_id"]
                        or sample["quality"]["source"] != source):
                    raise PlanValidationError()
                facts["sample"] = sample
            # Keep only supported tool identities and bounded status, never raw exceptions.
            item = {"evidence_id": evidence_id, "status": status, "source": source,
                    "data": facts}
            if observation.get("tool_name") in TOOL_ARGUMENTS:
                item["tool_name"] = observation["tool_name"]
            normalized.append(item)
        return clean, normalized
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, ContractValidationError):
        raise PlanValidationError() from None


def _validate_evidence(plan: dict, context: dict, observations: list[dict]) -> dict:
    known = {sample["sample_id"] for sample in context["telemetry"]}
    failed = set()
    for obs in observations:
        if obs["status"] == "succeeded":
            known.add(obs["evidence_id"])
            if "sample" in obs["data"]:
                known.add(obs["data"]["sample"]["sample_id"])
        elif obs["status"] == "failed":
            failed.add(obs["evidence_id"])
    for hypothesis in plan["hypotheses"]:
        allowed = known | (failed if hypothesis["id"] == "tool_error" else set())
        if not set(hypothesis["evidence_ids"]).issubset(allowed):
            raise PlanValidationError()
    if plan["stop_condition"] == "diagnosed":
        best = max(plan["hypotheses"], key=lambda hypothesis: hypothesis["confidence"])
        if not best["evidence_ids"] or best["id"] == "tool_error":
            raise PlanValidationError()
    if plan["next_tool"] and plan["next_tool"]["tool_name"] not in context["available_tools"]:
        raise PlanValidationError()
    return plan


class NebiusPlanner:
    """Live planner; requires explicit configuration and never executes proposed tools."""

    source = "nebius"

    def __init__(self, provider: NebiusProvider | None = None):
        self.provider = provider or NebiusProvider(ProviderConfig.from_env())
        self.last_attempts: list[dict] = []

    @classmethod
    def from_env(cls) -> NebiusPlanner:
        return cls(NebiusProvider(ProviderConfig.from_env()))

    async def plan(self, context: dict, observations: list[dict]) -> dict:
        self.last_attempts = []
        clean, observed = prepare_inputs(context, observations)
        schema = deepcopy(PLAN_SCHEMA)
        schema["properties"]["hypotheses"]["items"]["properties"]["id"] = {
            **IDENTIFIER, "enum": HYPOTHESIS_IDS,
        }
        # Describe only tools actually available for this run. Full local validation
        # remains authoritative even when provider-side constraints are supported.
        schema["properties"]["next_tool"]["anyOf"] = [{"type": "null"}] + [
            _tool_schema(name, *TOOL_ARGUMENTS[name]) for name in clean["available_tools"]
        ]
        evidence_ids = {sample["sample_id"] for sample in clean["telemetry"]}
        for observation in observed:
            if observation["status"] in {"succeeded", "failed"}:
                evidence_ids.add(observation["evidence_id"])
            if observation["status"] == "succeeded" and "sample" in observation["data"]:
                evidence_ids.add(observation["data"]["sample"]["sample_id"])
        evidence_schema = schema["properties"]["hypotheses"]["items"]["properties"]["evidence_ids"]
        if evidence_ids:
            evidence_schema["items"] = {**evidence_schema["items"], "enum": sorted(evidence_ids)}
            evidence_schema["minItems"] = 1
        else:
            evidence_schema["maxItems"] = 0
        prompt = files("nexus_backend").joinpath(f"prompts/{PROMPT_VERSION}.txt").read_text()
        prompt += "\nOutput JSON schema for this run:\n" + json.dumps(schema, allow_nan=False)
        messages = [{"role": "system", "content": prompt}, {
            "role": "user", "content": json.dumps({
                "untrusted_diagnostic_data": {
                    "symptom": clean["symptom"], "observations": observed,
                    "telemetry": clean["telemetry"], "available_tools": clean["available_tools"],
                    "hardware_context": {key: value for key, value in clean.items()
                                         if key not in {"symptom", "telemetry", "available_tools"}},
                },
            }, allow_nan=False),
        }]
        request_validator = Draft202012Validator(schema)
        for attempt in range(2):
            try:
                content = await self.provider.complete(messages, schema)
                plan = validate_plan(content)
                self.provider.reject_secret_echo(plan)
                if not request_validator.is_valid(plan):
                    raise PlanValidationError()
                return _validate_evidence(plan, clean, observed)
            except (PlanValidationError, ProviderError) as error:
                if isinstance(error, ProviderError) and error.code != "invalid_response":
                    raise
                if attempt == 1:
                    raise ProviderError("invalid_response") from None
                # One bounded correction; never feed back raw output, reasoning or secrets.
                messages[0]["content"] += (
                    "\nThe previous response failed local validation. Return a complete, short "
                    "JSON object. Use only schema-listed IDs, available tools and evidence. "
                    "Every hypothesis must cite evidence when evidence exists. A failed "
                    "observation supports only tool_error and a non-diagnosed stop. "
                    "next_tool null requires a stop other than continue. With a tool, use "
                    "continue. Keep user_message below 280 characters."
                )
            finally:
                if self.provider.last_completion:
                    self.last_attempts.append(deepcopy(self.provider.last_completion))


class MockPlanner:
    """Rule-based simulation, never evidence of a Nemotron call or physical diagnosis."""

    source = "simulator"

    async def plan(self, context: dict, observations: list[dict]) -> dict:
        clean, observed = prepare_inputs(context, observations)
        samples = clean["telemetry"][:]
        facts = {}
        fact_evidence = {}
        failures = []
        for observation in observed:
            if observation["status"] == "failed":
                failures.append(observation["evidence_id"])
            if observation["status"] != "succeeded":
                continue
            for key, value in observation["data"].items():
                facts[key] = value
                fact_evidence[key] = observation["evidence_id"]
            if "sample" in observation["data"]:
                samples.append(observation["data"]["sample"])
        latest = samples[-1] if samples else None
        evidence = [latest["sample_id"]] if latest else []
        scores = {"power": 0.15, "pwm": 0.15, "driver": 0.15, "wiring": 0.15}
        labels = {"power": "Insufficient power", "pwm": "PWM configuration",
                  "driver": "Driver disabled or output fault", "wiring": "Motor wiring fault",
                  "normal": "No electrical fault observed", "calibration": "Sensor calibration",
                  "sensor": "Sensor unavailable", "tool_error": "Diagnostic tool failed",
                  "overvoltage": "Declared voltage exceeds pin rating"}
        evidence_by_id = {name: evidence for name in scores}
        next_tool = None
        stop = "needs_manual"
        message = "Simulation: readings do not isolate the fault; inspect the rig manually."
        if latest:
            reading = latest["measurements"]
            limits = clean["hardware_model"]["safety_limits"]
            if reading["bus_voltage_v"] < limits["min_bus_voltage_v"]:
                scores["power"] = 0.95
                message = "Simulation: measured supply is below the declared minimum."
            elif not reading["driver_enabled"]:
                scores["driver"] = 0.92
                next_tool = {"tool_name": "enable_driver", "arguments": {"enabled": True}}
                message = "Simulation: the driver is disabled; propose a policy-checked enable."
            elif reading["pwm_percent"] == 0:
                scores["pwm"] = 0.93
                pwm = min(20, limits["max_pwm_percent"])
                if pwm > 0:
                    next_tool = {"tool_name": "set_pwm", "arguments": {"pwm_percent": pwm}}
                message = "Simulation: PWM is zero; propose a bounded, policy-checked PWM change."
            elif abs(reading["current_ma"]) < 50:
                scores.update(wiring=0.65, driver=0.6)
                message = "Simulation: low current with enabled drive needs wiring/output checks."
            else:
                scores["normal"] = 0.75
                evidence_by_id["normal"] = evidence
                stop = "diagnosed"
                message = "Simulation: electrical readings are active; motor motion is unverified."
        else:
            stop = "insufficient_evidence"
            message = "Simulation: no telemetry is available to diagnose this rig."
            if not observed and "get_telemetry" in clean["available_tools"]:
                next_tool = {"tool_name": "get_telemetry", "arguments": {}}

        if latest and "reference_current_ma" in facts:
            reference = facts["reference_current_ma"]
            if abs(latest["measurements"]["current_ma"] - reference) > max(50, abs(reference)*0.1):
                scores["calibration"] = 0.96
                evidence_by_id["calibration"] = evidence + [fact_evidence["reference_current_ma"]]
                next_tool, stop = None, "needs_manual"
                message = "Simulation: sensor current disagrees with the supplied reference."
        if latest and "driver_output_voltage_v" in facts:
            reading = latest["measurements"]
            if (reading["driver_enabled"] and reading["pwm_percent"] > 0
                    and facts["driver_output_voltage_v"] < 0.5):
                scores["driver"] = 0.97
                evidence_by_id["driver"] = evidence + [fact_evidence["driver_output_voltage_v"]]
                next_tool, stop = None, "needs_manual"
                message = "Simulation: the enabled driver has no measured output."
        if facts.get("motor_output_connected") is False:
            scores["wiring"] = 0.98
            evidence_by_id["wiring"] = [fact_evidence["motor_output_connected"]]
            next_tool, stop = None, "needs_manual"
            message = "Simulation: supplied continuity evidence indicates disconnected motor wiring."
        if ("source_voltage_v" in facts and "pin_max_voltage_v" in facts
                and facts["source_voltage_v"] > facts["pin_max_voltage_v"]):
            scores["overvoltage"] = 0.99
            evidence_by_id["overvoltage"] = list(dict.fromkeys([
                fact_evidence["source_voltage_v"], fact_evidence["pin_max_voltage_v"],
            ]))
            next_tool, stop = None, "needs_manual"
            message = "Simulation: declared source voltage exceeds the supplied pin rating."
        if facts.get("sensor_timed_out") is True:
            scores["sensor"] = 0.99
            evidence_by_id["sensor"] = [fact_evidence["sensor_timed_out"]]
            next_tool, stop = None, "insufficient_evidence"
            message = "Simulation: the sensor timed out; obtain a fresh measurement."
        if failures:
            scores["tool_error"] = 1.0
            evidence_by_id["tool_error"] = failures[-1:]
            next_tool, stop = None, "needs_manual"
            message = "Simulation: a diagnostic tool failed; investigate before continuing."
        if next_tool and next_tool["tool_name"] not in clean["available_tools"]:
            next_tool = None
        if next_tool:
            stop = "continue"
        hypotheses = [{"id": name, "label": labels[name], "confidence": score,
                       "evidence_ids": evidence_by_id.get(name, [])}
                      for name, score in sorted(scores.items(), key=lambda item: -item[1])]
        return _validate_evidence(validate_plan({
            "hypotheses": hypotheses, "next_tool": next_tool,
            "confidence": hypotheses[0]["confidence"], "user_message": message,
            "stop_condition": stop,
        }), clean, observed)
