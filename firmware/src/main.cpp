#include <Arduino.h>
#include <Adafruit_INA219.h>

namespace {
constexpr uint8_t kMotorEnablePin = 25;
constexpr uint8_t kMotorIn1Pin = 26;
constexpr uint8_t kMotorIn2Pin = 27;
constexpr uint8_t kMaxPwmPercent = NEXUS_MAX_PWM_PERCENT;

Adafruit_INA219 currentSensor;
uint8_t pwmPercent = 0;
bool driverEnabled = false;

void applySafeMotorState(uint8_t requestedPercent, bool enable) {
  pwmPercent = min(requestedPercent, kMaxPwmPercent);
  driverEnabled = enable;

  digitalWrite(kMotorIn1Pin, driverEnabled ? HIGH : LOW);
  digitalWrite(kMotorIn2Pin, LOW);
  analogWrite(kMotorEnablePin, driverEnabled ? map(pwmPercent, 0, 100, 0, 255) : 0);
}

void emitTelemetry() {
  Serial.printf(
      "{\"device_id\":\"%s\",\"bus_voltage_v\":%.3f,\"current_ma\":%.2f,"
      "\"pwm_percent\":%u,\"driver_enabled\":%s}\n",
      NEXUS_DEVICE_ID,
      currentSensor.getBusVoltage_V(),
      currentSensor.getCurrent_mA(),
      pwmPercent,
      driverEnabled ? "true" : "false");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(kMotorEnablePin, OUTPUT);
  pinMode(kMotorIn1Pin, OUTPUT);
  pinMode(kMotorIn2Pin, OUTPUT);
  currentSensor.begin();
  applySafeMotorState(0, false);
}

void loop() {
  // Command transport is intentionally deferred to the firmware backlog item.
  // The safety clamp remains local even after MQTT or serial commands are added.
  emitTelemetry();
  delay(1000);
}
