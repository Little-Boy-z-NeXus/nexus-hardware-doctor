#include <Arduino.h>
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
constexpr uint8_t kIna226Address = 0x40;
constexpr float kIna226ShuntOhms = 0.1f;       // R100 on the confirmed MVP module.
constexpr float kIna226CurrentLsbMa = 0.1f;    // 100 uA/bit; calibration register = 512.
constexpr uint16_t kIna226ManufacturerId = 0x5449;
constexpr uint16_t kIna226DieIdMask = 0xFFF0;
constexpr uint16_t kIna226DieId = 0x2260;

INA226 currentSensor(kIna226Address, &Wire);
uint8_t pwmPercent = 0;
bool driverEnabled = false;
bool currentSensorReady = false;
uint32_t telemetrySequence = 0;
uint32_t lastSensorInitAttemptMs = 0;

void applySafeMotorState(uint8_t requestedPercent, bool enable) {
  pwmPercent = min(requestedPercent, kMaxPwmPercent);
  driverEnabled = enable;

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

  const int calibrationError =
      currentSensor.configure(kIna226ShuntOhms, kIna226CurrentLsbMa);
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

void emitTelemetry() {
  const float busVoltageV = currentSensor.getBusVoltage();
  const bool busReadOk = currentSensor.getLastError() == 0;
  const float shuntVoltageMv = currentSensor.getShuntVoltage_mV();
  const bool shuntReadOk = currentSensor.getLastError() == 0;
  const float currentMa = currentSensor.getCurrent_mA();
  const bool currentReadOk = currentSensor.getLastError() == 0;
  const float powerMw = busVoltageV * currentMa;

  if (!busReadOk || !shuntReadOk || !currentReadOk) {
    Serial.printf(
        "[NEXUS][ERROR][INA226_I2C_READ_FAILED] bus_ok=%s shunt_ok=%s current_ok=%s; "
        "sample discarded\n",
        busReadOk ? "true" : "false",
        shuntReadOk ? "true" : "false",
        currentReadOk ? "true" : "false");
    currentSensorReady = false;
    return;
  }

  if (!std::isfinite(busVoltageV) || !std::isfinite(shuntVoltageMv) ||
      !std::isfinite(currentMa) || !std::isfinite(powerMw)) {
    Serial.println(
        "[NEXUS][ERROR][INA226_INVALID_READING] Non-finite reading; sample discarded");
    currentSensorReady = false;
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
      busVoltageV,
      currentMa,
      powerMw,
      pwmPercent,
      driverEnabled ? "true" : "false");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(
      "[NEXUS][INFO][BOOT] GOOUUU ESP32-S3-N16R8 / INA226 R100 / L298N / JGB37-520");
  pinMode(kMotorEnablePin, OUTPUT);
  pinMode(kMotorIn1Pin, OUTPUT);
  pinMode(kMotorIn2Pin, OUTPUT);
  pinMode(kEncoderAPin, INPUT);
  pinMode(kEncoderBPin, INPUT);
  Wire.begin(kInaSdaPin, kInaSclPin);
  applySafeMotorState(0, false);
  initializeCurrentSensor();
}

void loop() {
  // Command transport is intentionally deferred to the firmware backlog item.
  // The safety clamp remains local even after MQTT or serial commands are added.
  if (!currentSensorReady && millis() - lastSensorInitAttemptMs >= 5000) {
    initializeCurrentSensor();
  }
  if (currentSensorReady) {
    emitTelemetry();
  }
  delay(1000);
}
