#include <Arduino.h>
#include <ArduinoJson.h>
#include <INA226.h>
#include <Wire.h>

#include <cmath>

#include "nexus_contract_v1.h"

namespace {
constexpr uint8_t kInaSdaPin = 1;
constexpr uint8_t kInaSclPin = 2;
constexpr uint8_t kMotorEnablePin = 12;
constexpr uint8_t kMotorIn1Pin = 13;
constexpr uint8_t kMotorIn2Pin = 14;
constexpr uint8_t kEncoderAPin = 16;
constexpr uint8_t kEncoderBPin = 17;
constexpr uint8_t kMaxPwmPercent = NEXUS_MAX_PWM_PERCENT;
constexpr float kMinBusVoltageV = NEXUS_MIN_BUS_VOLTAGE_MV / 1000.0f;
constexpr float kMaxBusVoltageV = NEXUS_MAX_BUS_VOLTAGE_MV / 1000.0f;
constexpr float kMaxCurrentMa = NEXUS_MAX_CURRENT_MA;
constexpr uint8_t kIna226Address = 0x40;
constexpr float kIna226ShuntOhms = 0.1f;
constexpr float kIna226CurrentLsbMa = 0.1f;
constexpr uint16_t kIna226ManufacturerId = 0x5449;
constexpr uint16_t kIna226DieIdMask = 0xFFF0;
constexpr uint16_t kIna226DieId = 0x2260;
constexpr char kDeviceProtocolVersion[] = "1.0.0";
constexpr size_t kMaxCommandLength = 512;
constexpr size_t kRequestCacheSize = 4;
constexpr uint32_t kDefaultCommandTimeoutMs = 4000;
constexpr uint32_t kMaxCommandTimeoutMs = 5000;
constexpr uint32_t kMaxMotorTestDurationMs = 3000;
constexpr uint32_t kTelemetryIntervalMs = 1000;
#ifdef NEXUS_ENABLE_BASELINE_CONTROL
constexpr uint32_t kBaselineKeepaliveTimeoutMs = 4000;
#endif

struct MeasurementSnapshot {
  bool valid = false;
  float busVoltageV = 0.0f;
  float currentMa = 0.0f;
  float powerMw = 0.0f;
  uint8_t pwm = 0;
  bool enabled = false;
};

struct ParsedCommand {
  String requestId;
  String command;
  String pinId;
  int pwmPercent = -1;
  uint32_t durationMs = 0;
  uint32_t timeoutMs = kDefaultCommandTimeoutMs;
  bool enabledArgument = false;
  uint32_t fingerprint = 0;
};

struct CachedResponse {
  bool used = false;
  String requestId;
  uint32_t fingerprint = 0;
  String terminalResponse;
};

INA226 currentSensor(kIna226Address, &Wire);
uint8_t pwmPercent = 0;
bool driverEnabled = false;
bool currentSensorReady = false;
uint32_t telemetrySequence = 0;
uint32_t lastSensorInitAttemptMs = 0;
uint32_t lastTelemetryMs = 0;
String serialCommandBuffer;
bool discardOversizedCommand = false;
CachedResponse responseCache[kRequestCacheSize];
size_t nextCacheIndex = 0;
#ifdef NEXUS_ENABLE_BASELINE_CONTROL
uint32_t lastBaselineKeepaliveMs = 0;
#endif

void applySafeMotorState(uint8_t requestedPercent, bool enable) {
  pwmPercent = min(requestedPercent, kMaxPwmPercent);
  driverEnabled = enable && pwmPercent > 0;

  digitalWrite(kMotorIn1Pin, driverEnabled ? HIGH : LOW);
  digitalWrite(kMotorIn2Pin, LOW);
  analogWrite(kMotorEnablePin, driverEnabled ? map(pwmPercent, 0, 100, 0, 255) : 0);
}

bool initializeCurrentSensor() {
  lastSensorInitAttemptMs = millis();
  currentSensorReady = currentSensor.begin();
  if (!currentSensorReady) {
    Serial.println(
        "[NEXUS][ERROR][INA226_I2C_NO_ACK] Check GND, 3V3, SDA=GPIO1 and SCL=GPIO2");
    return false;
  }

  const uint16_t manufacturerId = currentSensor.getManufacturerID();
  const bool manufacturerReadOk = currentSensor.getLastError() == 0;
  const uint16_t dieId = currentSensor.getDieID();
  const bool dieReadOk = currentSensor.getLastError() == 0;
  if (!manufacturerReadOk || !dieReadOk || manufacturerId != kIna226ManufacturerId ||
      (dieId & kIna226DieIdMask) != kIna226DieId) {
    Serial.printf(
        "[NEXUS][ERROR][INA226_ID_MISMATCH] Expected manufacturer=0x%04X die=0x226x; "
        "received manufacturer=0x%04X die=0x%04X\n",
        kIna226ManufacturerId,
        manufacturerId,
        dieId);
    currentSensorReady = false;
    return false;
  }

  const int calibrationError = currentSensor.configure(kIna226ShuntOhms, kIna226CurrentLsbMa);
  if (calibrationError != INA226_ERR_NONE || currentSensor.getLastError() != 0) {
    Serial.printf(
        "[NEXUS][ERROR][INA226_CALIBRATION_FAILED] code=0x%04X shunt=%.3fOhm "
        "current_lsb=%.3fmA\n",
        static_cast<unsigned int>(calibrationError),
        kIna226ShuntOhms,
        kIna226CurrentLsbMa);
    currentSensorReady = false;
    return false;
  }

  const bool configurationReady =
      currentSensor.setAverage(INA226_16_SAMPLES) &&
      currentSensor.setBusVoltageConversionTime(INA226_1100_us) &&
      currentSensor.setShuntVoltageConversionTime(INA226_1100_us) &&
      currentSensor.setModeShuntBusContinuous();
  if (!configurationReady || currentSensor.getLastError() != 0) {
    Serial.println(
        "[NEXUS][ERROR][INA226_I2C_READ_FAILED] Configuration write failed; sensor will retry");
    currentSensorReady = false;
    return false;
  }

  Serial.println(
      "[NEXUS][INFO][INA226_READY] INA226 verified on SDA=GPIO1 SCL=GPIO2 "
      "address=0x40 shunt=R100 calibration=512");
  return true;
}

bool readMeasurements(MeasurementSnapshot& snapshot, bool logFailure = true) {
  snapshot.pwm = pwmPercent;
  snapshot.enabled = driverEnabled;
  if (!currentSensorReady) {
    return false;
  }

  const float busVoltageV = currentSensor.getBusVoltage();
  const bool busReadOk = currentSensor.getLastError() == 0;
  const float shuntVoltageMv = currentSensor.getShuntVoltage_mV();
  const bool shuntReadOk = currentSensor.getLastError() == 0;
  const float currentMa = currentSensor.getCurrent_mA();
  const bool currentReadOk = currentSensor.getLastError() == 0;
  const float powerMw = busVoltageV * currentMa;

  if (!busReadOk || !shuntReadOk || !currentReadOk) {
    if (logFailure) {
      Serial.printf(
          "[NEXUS][ERROR][INA226_I2C_READ_FAILED] bus_ok=%s shunt_ok=%s current_ok=%s; "
          "sample discarded\n",
          busReadOk ? "true" : "false",
          shuntReadOk ? "true" : "false",
          currentReadOk ? "true" : "false");
    }
    currentSensorReady = false;
    return false;
  }

  if (!std::isfinite(busVoltageV) || !std::isfinite(shuntVoltageMv) ||
      !std::isfinite(currentMa) || !std::isfinite(powerMw)) {
    if (logFailure) {
      Serial.println(
          "[NEXUS][ERROR][INA226_INVALID_READING] Non-finite reading; sample discarded");
    }
    currentSensorReady = false;
    return false;
  }

  snapshot.valid = true;
  snapshot.busVoltageV = busVoltageV;
  snapshot.currentMa = currentMa;
  snapshot.powerMw = powerMw;
  return true;
}

void addSnapshot(JsonObject target, const MeasurementSnapshot& snapshot) {
  if (snapshot.valid) {
    target["bus_voltage_v"] = snapshot.busVoltageV;
    target["current_ma"] = snapshot.currentMa;
    target["power_mw"] = snapshot.powerMw;
  } else {
    target["bus_voltage_v"] = nullptr;
    target["current_ma"] = nullptr;
    target["power_mw"] = nullptr;
  }
  target["pwm_percent"] = snapshot.pwm;
  target["driver_enabled"] = snapshot.enabled;
}

void emitTelemetry() {
  MeasurementSnapshot snapshot;
  if (!readMeasurements(snapshot)) {
    return;
  }

  const uint32_t sequence = telemetrySequence++;
  Serial.printf(
      "{\"schema_version\":\"%s\",\"device_id\":\"%s\","
      "\"hardware_model_id\":\"%s\",\"sample_id\":\"%s-%lu\","
      "\"recorded_at\":null,\"sequence\":%lu,\"measurements\":{"
      "\"bus_voltage_v\":%.3f,\"current_ma\":%.2f,\"power_mw\":%.2f,"
      "\"pwm_percent\":%u,\"driver_enabled\":%s,\"motor_rpm\":null},"
      "\"quality\":{\"signal_quality_percent\":100.0,\"source\":\"device\"}}\n",
      nexus::contract::v1::kSchemaVersion,
      NEXUS_DEVICE_ID,
      NEXUS_HARDWARE_MODEL_ID,
      NEXUS_DEVICE_ID,
      static_cast<unsigned long>(sequence),
      static_cast<unsigned long>(sequence),
      snapshot.busVoltageV,
      snapshot.currentMa,
      snapshot.powerMw,
      snapshot.pwm,
      snapshot.enabled ? "true" : "false");
}

bool validRequestId(const char* value) {
  if (value == nullptr) {
    return false;
  }
  const size_t length = strlen(value);
  if (length == 0 || length > 64) {
    return false;
  }
  for (size_t index = 0; index < length; ++index) {
    const char current = value[index];
    if (!isalnum(static_cast<unsigned char>(current)) && current != '-' && current != '_' &&
        current != '.' && current != ':') {
      return false;
    }
  }
  return true;
}

bool hasOnlyKeys(JsonObjectConst object, const char* const* allowed, size_t count) {
  for (JsonPairConst pair : object) {
    bool found = false;
    for (size_t index = 0; index < count; ++index) {
      if (strcmp(pair.key().c_str(), allowed[index]) == 0) {
        found = true;
        break;
      }
    }
    if (!found) {
      return false;
    }
  }
  return true;
}

uint32_t fingerprintCommand(const ParsedCommand& parsed) {
  uint32_t hash = 2166136261UL;
  const int inputPwm = parsed.command == "enable_driver" ? -1 : parsed.pwmPercent;
  const String canonical = parsed.command + "|" + parsed.pinId + "|" +
                           String(inputPwm) + "|" + String(parsed.durationMs) + "|" +
                           String(parsed.timeoutMs) + "|" + String(parsed.enabledArgument);
  for (size_t index = 0; index < canonical.length(); ++index) {
    hash ^= static_cast<uint8_t>(canonical[index]);
    hash *= 16777619UL;
  }
  return hash;
}

bool commandKnown(const String& command) {
  return command == "read_voltage" || command == "read_current" || command == "read_gpio" ||
         command == "enable_driver" || command == "run_motor_test" || command == "set_pwm" ||
         command == "reset_driver" || command == "recalibrate_sensor";
}

bool parseCommand(const String& line, ParsedCommand& parsed, String& errorCode,
                  String& errorMessage) {
  JsonDocument document;
  const DeserializationError jsonError = deserializeJson(document, line);
  if (jsonError) {
    errorCode = "INVALID_JSON";
    errorMessage = jsonError.c_str();
    return false;
  }
  if (!document.is<JsonObject>()) {
    errorCode = "INVALID_ENVELOPE";
    errorMessage = "Command must be a JSON object";
    return false;
  }

  const JsonObjectConst root = document.as<JsonObjectConst>();
  const char* const rootKeys[] = {
      "protocol_version", "request_id", "command", "arguments", "timeout_ms"};
  if (!hasOnlyKeys(root, rootKeys, 5)) {
    errorCode = "UNKNOWN_FIELD";
    errorMessage = "Command envelope contains an unknown field";
    return false;
  }
  if (String(root["protocol_version"] | "") != kDeviceProtocolVersion) {
    errorCode = "UNSUPPORTED_PROTOCOL";
    errorMessage = "protocol_version must be 1.0.0";
    return false;
  }

  const char* requestId = root["request_id"] | nullptr;
  if (!validRequestId(requestId)) {
    errorCode = "INVALID_REQUEST_ID";
    errorMessage = "request_id must be 1..64 safe ASCII characters";
    return false;
  }
  parsed.requestId = requestId;

  const char* command = root["command"] | nullptr;
  if (command == nullptr || !commandKnown(command)) {
    errorCode = "UNKNOWN_COMMAND";
    errorMessage = "Command is not in the device allowlist";
    return false;
  }
  parsed.command = command;

  if (!root["arguments"].is<JsonObjectConst>()) {
    errorCode = "INVALID_ARGUMENTS";
    errorMessage = "arguments must be an object";
    return false;
  }
  const JsonObjectConst arguments = root["arguments"].as<JsonObjectConst>();

  if (!root["timeout_ms"].isNull()) {
    if (!root["timeout_ms"].is<uint32_t>()) {
      errorCode = "INVALID_TIMEOUT";
      errorMessage = "timeout_ms must be an integer";
      return false;
    }
    parsed.timeoutMs = root["timeout_ms"].as<uint32_t>();
  }
  if (parsed.timeoutMs < 100 || parsed.timeoutMs > kMaxCommandTimeoutMs) {
    errorCode = "INVALID_TIMEOUT";
    errorMessage = "timeout_ms must be between 100 and 5000";
    return false;
  }

  const char* const pwmKeys[] = {"pwm_percent"};
  const char* const motorTestKeys[] = {"duration_ms", "pwm_percent"};
  const char* const gpioKeys[] = {"pin_id"};
  const char* const enableKeys[] = {"enabled"};

  if (parsed.command == "read_voltage" || parsed.command == "read_current" ||
      parsed.command == "reset_driver" || parsed.command == "recalibrate_sensor") {
    if (arguments.size() != 0) {
      errorCode = "INVALID_ARGUMENTS";
      errorMessage = "This command takes no arguments";
      return false;
    }
  } else if (parsed.command == "read_gpio") {
    if (!hasOnlyKeys(arguments, gpioKeys, 1) || !arguments["pin_id"].is<const char*>()) {
      errorCode = "INVALID_ARGUMENTS";
      errorMessage = "read_gpio requires only string pin_id";
      return false;
    }
    parsed.pinId = arguments["pin_id"].as<const char*>();
    if (parsed.pinId != "gpio_12" && parsed.pinId != "gpio_13" &&
        parsed.pinId != "gpio_14" && parsed.pinId != "gpio_16" &&
        parsed.pinId != "gpio_17") {
      errorCode = "GPIO_NOT_ALLOWED";
      errorMessage = "pin_id is outside the read-only MVP pin allowlist";
      return false;
    }
  } else if (parsed.command == "enable_driver") {
    if (!hasOnlyKeys(arguments, enableKeys, 1) || !arguments["enabled"].is<bool>()) {
      errorCode = "INVALID_ARGUMENTS";
      errorMessage = "enable_driver requires only boolean enabled";
      return false;
    }
    parsed.enabledArgument = arguments["enabled"].as<bool>();
    parsed.pwmPercent = pwmPercent;
  } else if (parsed.command == "set_pwm") {
    if (!hasOnlyKeys(arguments, pwmKeys, 1) || !arguments["pwm_percent"].is<int>()) {
      errorCode = "INVALID_ARGUMENTS";
      errorMessage = "set_pwm requires only integer pwm_percent";
      return false;
    }
    parsed.pwmPercent = arguments["pwm_percent"].as<int>();
  } else if (parsed.command == "run_motor_test") {
    if (!hasOnlyKeys(arguments, motorTestKeys, 2) ||
        !arguments["duration_ms"].is<uint32_t>()) {
      errorCode = "INVALID_ARGUMENTS";
      errorMessage = "run_motor_test requires duration_ms and optional pwm_percent";
      return false;
    }
    parsed.durationMs = arguments["duration_ms"].as<uint32_t>();
    if (!arguments["pwm_percent"].isNull()) {
      if (!arguments["pwm_percent"].is<int>()) {
        errorCode = "INVALID_ARGUMENTS";
        errorMessage = "pwm_percent must be an integer";
        return false;
      }
      parsed.pwmPercent = arguments["pwm_percent"].as<int>();
    } else {
      parsed.pwmPercent = 20;
    }
  }

  if (parsed.pwmPercent > kMaxPwmPercent || parsed.pwmPercent < -1) {
    errorCode = "PWM_LIMIT_EXCEEDED";
    errorMessage = "pwm_percent exceeds the local 0..80 safety limit";
    return false;
  }
  if (parsed.command == "run_motor_test" &&
      (parsed.durationMs < 100 || parsed.durationMs > kMaxMotorTestDurationMs)) {
    errorCode = "DURATION_LIMIT_EXCEEDED";
    errorMessage = "duration_ms must be between 100 and 3000";
    return false;
  }
  if (parsed.command == "run_motor_test" && parsed.pwmPercent < 1) {
    errorCode = "INVALID_ARGUMENTS";
    errorMessage = "run_motor_test pwm_percent must be between 1 and 80";
    return false;
  }
  if (parsed.command == "run_motor_test" && parsed.timeoutMs < parsed.durationMs + 100) {
    errorCode = "TIMEOUT_TOO_SHORT";
    errorMessage = "timeout_ms must exceed duration_ms by at least 100 ms";
    return false;
  }

  parsed.fingerprint = fingerprintCommand(parsed);
  return true;
}

String serializeDocument(JsonDocument& document) {
  String output;
  serializeJson(document, output);
  return output;
}

void printJsonLine(const String& line) {
  Serial.println(line);
}

void emitAck(const ParsedCommand& parsed, bool accepted, bool duplicate = false) {
  JsonDocument document;
  document["protocol_version"] = kDeviceProtocolVersion;
  document["response_type"] = "ack";
  document["request_id"] = parsed.requestId;
  document["command"] = parsed.command;
  document["accepted"] = accepted;
  document["duplicate"] = duplicate;
  document["writes_enabled"] =
#ifdef NEXUS_ENABLE_COMMAND_WRITES
      true;
#else
      false;
#endif
  printJsonLine(serializeDocument(document));
}

String buildErrorResponse(const ParsedCommand& parsed, const String& code, const String& message,
                          bool hardwareEffect = false) {
  JsonDocument document;
  document["protocol_version"] = kDeviceProtocolVersion;
  document["response_type"] = "error";
  if (!parsed.requestId.isEmpty()) {
    document["request_id"] = parsed.requestId;
  } else {
    document["request_id"] = nullptr;
  }
  if (!parsed.command.isEmpty()) {
    document["command"] = parsed.command;
  } else {
    document["command"] = nullptr;
  }
  document["completed_at_ms"] = millis();
  JsonObject error = document["error"].to<JsonObject>();
  error["code"] = code;
  error["message"] = message;
  error["hardware_effect"] = hardwareEffect;
  return serializeDocument(document);
}

CachedResponse* findCached(const String& requestId) {
  for (CachedResponse& entry : responseCache) {
    if (entry.used && entry.requestId == requestId) {
      return &entry;
    }
  }
  return nullptr;
}

void cacheResponse(const ParsedCommand& parsed, const String& response) {
  CachedResponse& entry = responseCache[nextCacheIndex];
  entry.used = true;
  entry.requestId = parsed.requestId;
  entry.fingerprint = parsed.fingerprint;
  entry.terminalResponse = response;
  nextCacheIndex = (nextCacheIndex + 1) % kRequestCacheSize;
}

bool readingsAllowMotion(const MeasurementSnapshot& before, String& code, String& message) {
  if (!before.valid) {
    code = "SENSOR_NOT_READY";
    message = "A valid INA226 reading is required before motor motion";
    return false;
  }
  if (before.busVoltageV < kMinBusVoltageV || before.busVoltageV > kMaxBusVoltageV) {
    code = "BUS_VOLTAGE_UNSAFE";
    message = "Motor bus voltage is outside the verified 9.5..13.0 V MVP window";
    return false;
  }
  if (fabs(before.currentMa) > kMaxCurrentMa) {
    code = "CURRENT_LIMIT_EXCEEDED";
    message = "Measured current exceeds the 1500 mA MVP limit";
    return false;
  }
  return true;
}

String executeCommand(const ParsedCommand& parsed) {
  const uint32_t startedAt = millis();
  MeasurementSnapshot before;
  readMeasurements(before, false);

  JsonDocument document;
  document["protocol_version"] = kDeviceProtocolVersion;
  document["response_type"] = "result";
  document["request_id"] = parsed.requestId;
  document["command"] = parsed.command;
  document["completed_at_ms"] = millis();
  document["elapsed_ms"] = 0;
  document["hardware_effect"] = false;
  JsonObject result = document["result"].to<JsonObject>();

  if (parsed.command == "read_voltage") {
    if (!before.valid) {
      return buildErrorResponse(parsed, "SENSOR_NOT_READY", "INA226 has no valid reading");
    }
    result["bus_voltage_v"] = before.busVoltageV;
  } else if (parsed.command == "read_current") {
    if (!before.valid) {
      return buildErrorResponse(parsed, "SENSOR_NOT_READY", "INA226 has no valid reading");
    }
    result["current_ma"] = before.currentMa;
  } else if (parsed.command == "read_gpio") {
    int pin = -1;
    if (parsed.pinId == "gpio_12") pin = kMotorEnablePin;
    if (parsed.pinId == "gpio_13") pin = kMotorIn1Pin;
    if (parsed.pinId == "gpio_14") pin = kMotorIn2Pin;
    if (parsed.pinId == "gpio_16") pin = kEncoderAPin;
    if (parsed.pinId == "gpio_17") pin = kEncoderBPin;
    result["pin_id"] = parsed.pinId;
    result["level"] = digitalRead(pin) == HIGH ? 1 : 0;
  } else if (parsed.command == "reset_driver") {
    applySafeMotorState(0, false);
    document["hardware_effect"] = before.pwm != 0 || before.enabled;
    result["reset"] = true;
  } else if (parsed.command == "recalibrate_sensor") {
    if (driverEnabled) {
      return buildErrorResponse(
          parsed, "DRIVER_MUST_BE_STOPPED", "Stop the motor before recalibrating INA226");
    }
    const bool ready = initializeCurrentSensor();
    if (!ready) {
      return buildErrorResponse(parsed, "CALIBRATION_FAILED", "INA226 recalibration failed");
    }
    result["calibrated"] = true;
    result["shunt_ohms"] = kIna226ShuntOhms;
    result["current_lsb_ma"] = kIna226CurrentLsbMa;
  } else {
#ifndef NEXUS_ENABLE_COMMAND_WRITES
    return buildErrorResponse(
        parsed,
        "COMMAND_WRITES_DISABLED",
        "Upload the command-test environment for supervised physical writes");
#else
    String safetyCode;
    String safetyMessage;
    if (parsed.command == "enable_driver" && parsed.enabledArgument &&
        parsed.pwmPercent == 0) {
      return buildErrorResponse(
          parsed, "PWM_REQUIRED", "Stage a non-zero PWM before enabling the driver");
    }
    const bool enabling = parsed.command == "run_motor_test" ||
                          (parsed.command == "enable_driver" && parsed.enabledArgument) ||
                          (parsed.command == "set_pwm" && driverEnabled && parsed.pwmPercent > 0);
    if (enabling && !readingsAllowMotion(before, safetyCode, safetyMessage)) {
      applySafeMotorState(0, false);
      return buildErrorResponse(parsed, safetyCode, safetyMessage);
    }

    if (parsed.command == "set_pwm") {
      applySafeMotorState(static_cast<uint8_t>(parsed.pwmPercent), driverEnabled);
      document["hardware_effect"] = before.enabled && before.pwm != pwmPercent;
      result["pwm_percent"] = pwmPercent;
      result["driver_enabled"] = driverEnabled;
    } else if (parsed.command == "enable_driver") {
      if (parsed.enabledArgument && parsed.pwmPercent > 0) {
        applySafeMotorState(static_cast<uint8_t>(parsed.pwmPercent), true);
      } else {
        applySafeMotorState(static_cast<uint8_t>(parsed.pwmPercent), false);
      }
      document["hardware_effect"] = before.enabled != driverEnabled;
      result["driver_enabled"] = driverEnabled;
      result["pwm_percent"] = pwmPercent;
    } else if (parsed.command == "run_motor_test") {
      applySafeMotorState(static_cast<uint8_t>(parsed.pwmPercent), true);
      document["hardware_effect"] = true;
      bool failed = false;
      String failureCode;
      String failureMessage;
      uint32_t lastSafetyRead = startedAt;
      while (millis() - startedAt < parsed.durationMs) {
        if (millis() - startedAt >= parsed.timeoutMs) {
          failed = true;
          failureCode = "COMMAND_TIMEOUT";
          failureMessage = "Motor test exceeded timeout_ms";
          break;
        }
        if (millis() - lastSafetyRead >= 100) {
          lastSafetyRead = millis();
          MeasurementSnapshot during;
          if (!readMeasurements(during, false) ||
              !readingsAllowMotion(during, failureCode, failureMessage)) {
            failed = true;
            if (failureCode.isEmpty()) {
              failureCode = "MOTOR_TEST_SAFETY_STOP";
              failureMessage = "Sensor failed during motor test";
            }
            break;
          }
        }
        delay(5);
      }
      applySafeMotorState(0, false);
      if (failed) {
        return buildErrorResponse(parsed, failureCode, failureMessage, true);
      }
      result["duration_ms"] = parsed.durationMs;
      result["test_pwm_percent"] = parsed.pwmPercent;
      result["stopped_after_test"] = true;
    }
#endif
  }

  MeasurementSnapshot after;
  readMeasurements(after, false);
  addSnapshot(document["before"].to<JsonObject>(), before);
  addSnapshot(document["after"].to<JsonObject>(), after);
  document["completed_at_ms"] = millis();
  document["elapsed_ms"] = millis() - startedAt;
  return serializeDocument(document);
}

void processJsonCommand(const String& line) {
  ParsedCommand parsed;
  String errorCode;
  String errorMessage;
  if (!parseCommand(line, parsed, errorCode, errorMessage)) {
    if (!parsed.requestId.isEmpty()) {
      emitAck(parsed, false);
    }
    printJsonLine(buildErrorResponse(parsed, errorCode, errorMessage));
    return;
  }

  CachedResponse* cached = findCached(parsed.requestId);
  if (cached != nullptr) {
    if (cached->fingerprint != parsed.fingerprint) {
      emitAck(parsed, false);
      printJsonLine(buildErrorResponse(
          parsed, "REQUEST_ID_CONFLICT", "request_id was already used for another command"));
      return;
    }
    emitAck(parsed, true, true);
    printJsonLine(cached->terminalResponse);
    return;
  }

  emitAck(parsed, true);
  const String response = executeCommand(parsed);
  cacheResponse(parsed, response);
  printJsonLine(response);
}

#ifdef NEXUS_ENABLE_BASELINE_CONTROL
void processBaselineCommand(const String& command) {
  if (command == "NEXUS BASELINE STOP") {
    applySafeMotorState(0, false);
    Serial.println("[NEXUS][INFO][BASELINE_MOTOR_STOPPED] Motor output is disabled");
    return;
  }

  if (command == "NEXUS BASELINE KEEPALIVE") {
    if (driverEnabled) {
      lastBaselineKeepaliveMs = millis();
    }
    return;
  }

  constexpr char kStartPrefix[] = "NEXUS BASELINE START ";
  if (command.startsWith(kStartPrefix)) {
    const String pwmText = command.substring(sizeof(kStartPrefix) - 1);
    const int requestedPwm = pwmText.toInt();
    if (requestedPwm < 1 || requestedPwm > kMaxPwmPercent ||
        String(requestedPwm) != pwmText) {
      Serial.printf(
          "[NEXUS][ERROR][BASELINE_COMMAND_REJECTED] PWM must be 1..%u percent\n",
          kMaxPwmPercent);
      applySafeMotorState(0, false);
      return;
    }

    lastBaselineKeepaliveMs = millis();
    applySafeMotorState(static_cast<uint8_t>(requestedPwm), true);
    Serial.printf(
        "[NEXUS][INFO][BASELINE_MOTOR_STARTED] pwm_percent=%d keepalive_timeout_ms=%lu\n",
        requestedPwm,
        static_cast<unsigned long>(kBaselineKeepaliveTimeoutMs));
    return;
  }

  Serial.println(
      "[NEXUS][WARNING][BASELINE_COMMAND_UNKNOWN] Use START <PWM>, KEEPALIVE or STOP");
}

void enforceBaselineFailsafe() {
  if (driverEnabled && millis() - lastBaselineKeepaliveMs > kBaselineKeepaliveTimeoutMs) {
    applySafeMotorState(0, false);
    Serial.println(
        "[NEXUS][ERROR][BASELINE_FAILSAFE_STOP] Keepalive expired; motor output disabled");
  }
}
#endif

void processSerialLine(String line) {
  line.trim();
  if (line.isEmpty()) {
    return;
  }
  if (line.startsWith("{")) {
    processJsonCommand(line);
    return;
  }
#ifdef NEXUS_ENABLE_BASELINE_CONTROL
  processBaselineCommand(line);
#else
  ParsedCommand empty;
  printJsonLine(buildErrorResponse(
      empty, "INVALID_JSON", "Commands must use the NeXus device JSON protocol"));
#endif
}

void serviceSerialInput() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r') {
      continue;
    }
    if (incoming == '\n') {
      if (discardOversizedCommand) {
        ParsedCommand empty;
        printJsonLine(buildErrorResponse(
            empty, "COMMAND_TOO_LARGE", "Command exceeded 512 bytes and was discarded"));
      } else {
        processSerialLine(serialCommandBuffer);
      }
      serialCommandBuffer = "";
      discardOversizedCommand = false;
      continue;
    }
    if (discardOversizedCommand) {
      continue;
    }
    if (serialCommandBuffer.length() < kMaxCommandLength) {
      serialCommandBuffer += incoming;
    } else {
      serialCommandBuffer = "";
      discardOversizedCommand = true;
    }
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  serialCommandBuffer.reserve(kMaxCommandLength);
  delay(300);
  Serial.println(
      "[NEXUS][INFO][BOOT] GOOUUU ESP32-S3-N16R8 / INA226 R100 / L298N / JGB37-520");
  Serial.printf(
      "[NEXUS][INFO][DEVICE_COMMAND_PROTOCOL] version=%s writes_enabled=%s\n",
      kDeviceProtocolVersion,
#ifdef NEXUS_ENABLE_COMMAND_WRITES
      "true"
#else
      "false"
#endif
  );
#ifdef NEXUS_ENABLE_BASELINE_CONTROL
  Serial.println(
      "[NEXUS][WARNING][BASELINE_CONTROL_ENABLED] USB-only supervised hardware test mode");
#endif
  pinMode(kMotorEnablePin, OUTPUT);
  pinMode(kMotorIn1Pin, OUTPUT);
  pinMode(kMotorIn2Pin, OUTPUT);
  pinMode(kEncoderAPin, INPUT);
  pinMode(kEncoderBPin, INPUT);
  Wire.begin(kInaSdaPin, kInaSclPin);
  applySafeMotorState(0, false);
  initializeCurrentSensor();
  lastTelemetryMs = millis();
}

void loop() {
  serviceSerialInput();
#ifdef NEXUS_ENABLE_BASELINE_CONTROL
  enforceBaselineFailsafe();
#endif
  if (!currentSensorReady && millis() - lastSensorInitAttemptMs >= 5000) {
    initializeCurrentSensor();
  }
  if (currentSensorReady && millis() - lastTelemetryMs >= kTelemetryIntervalMs) {
    lastTelemetryMs = millis();
    emitTelemetry();
  }
  delay(5);
}
