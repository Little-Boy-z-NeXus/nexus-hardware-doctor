#include <Arduino.h>
#include <Adafruit_INA219.h>
#include <Wire.h>

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

Adafruit_INA219 currentSensor;
uint8_t pwmPercent = 0;
bool driverEnabled = false;
uint32_t telemetrySequence = 0;

void applySafeMotorState(uint8_t requestedPercent, bool enable) {
  pwmPercent = min(requestedPercent, kMaxPwmPercent);
  driverEnabled = enable;

  digitalWrite(kMotorIn1Pin, driverEnabled ? HIGH : LOW);
  digitalWrite(kMotorIn2Pin, LOW);
  analogWrite(kMotorEnablePin, driverEnabled ? map(pwmPercent, 0, 100, 0, 255) : 0);
}

void emitTelemetry() {
  const float busVoltageV = currentSensor.getBusVoltage_V();
  const float currentMa = currentSensor.getCurrent_mA();
  const float powerMw = busVoltageV * currentMa;
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
  pinMode(kMotorEnablePin, OUTPUT);
  pinMode(kMotorIn1Pin, OUTPUT);
  pinMode(kMotorIn2Pin, OUTPUT);
  pinMode(kEncoderAPin, INPUT);
  pinMode(kEncoderBPin, INPUT);
  Wire.begin(kInaSdaPin, kInaSclPin);
  currentSensor.begin();
  applySafeMotorState(0, false);
}

void loop() {
  // Command transport is intentionally deferred to the firmware backlog item.
  // The safety clamp remains local even after MQTT or serial commands are added.
  emitTelemetry();
  delay(1000);
}
