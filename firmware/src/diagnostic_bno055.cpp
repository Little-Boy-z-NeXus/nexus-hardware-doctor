#include <Arduino.h>
#include <Adafruit_BNO055.h>
#include <Wire.h>

#include <cmath>

#include "nexus_hardware_profile.generated.h"

#ifndef NEXUS_BNO055_I2C_ADDRESS
#define NEXUS_BNO055_I2C_ADDRESS 0x29
#endif

namespace {
constexpr uint32_t kI2cClockHz = 50000;
constexpr uint32_t kSampleIntervalMs = 500;
constexpr uint8_t kPreferredAddress = NEXUS_BNO055_I2C_ADDRESS;
constexpr uint8_t kAlternateAddress =
    NEXUS_BNO055_I2C_ADDRESS == 0x28 ? 0x29 : 0x28;

Adafruit_BNO055 preferredSensor(55, kPreferredAddress, &Wire);
Adafruit_BNO055 alternateSensor(56, kAlternateAddress, &Wire);
Adafruit_BNO055* sensor = nullptr;
uint8_t activeAddress = 0;
uint32_t lastSampleMs = 0;

bool probe(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission(true) == 0;
}

void printStatus(const char* stage) {
  if (sensor == nullptr) {
    return;
  }
  uint8_t systemStatus = 0;
  uint8_t selfTest = 0;
  uint8_t systemError = 0;
  sensor->getSystemStatus(&systemStatus, &selfTest, &systemError);
  Serial.printf(
      "[NEXUS][BNO055_DIAGNOSTIC][%s] address=0x%02X mode=0x%02X "
      "sys=%u self_test=0x%02X error=%u\n",
      stage, activeAddress, static_cast<unsigned>(sensor->getMode()),
      systemStatus, selfTest, systemError);
}
}  // namespace

void setup() {
  Serial.begin(NEXUS_SERIAL_BAUD_RATE);
  delay(300);
  Wire.begin(NEXUS_I2C_SDA_PIN, NEXUS_I2C_SCL_PIN);
  Wire.setClock(kI2cClockHz);
  Serial.printf(
      "[NEXUS][BNO055_DIAGNOSTIC][BOOT] SDA=GPIO%d SCL=GPIO%d clock=%luHz\n",
      NEXUS_I2C_SDA_PIN, NEXUS_I2C_SCL_PIN,
      static_cast<unsigned long>(kI2cClockHz));

  const bool preferredAck = probe(kPreferredAddress);
  const bool alternateAck = probe(kAlternateAddress);
  Serial.printf(
      "[NEXUS][BNO055_DIAGNOSTIC][SCAN] 0x%02X=%s 0x%02X=%s\n",
      kPreferredAddress, preferredAck ? "ACK" : "NO_ACK", kAlternateAddress,
      alternateAck ? "ACK" : "NO_ACK");

  if (preferredAck && preferredSensor.begin(OPERATION_MODE_ACCONLY)) {
    sensor = &preferredSensor;
    activeAddress = kPreferredAddress;
  } else if (alternateAck &&
             alternateSensor.begin(OPERATION_MODE_ACCONLY)) {
    sensor = &alternateSensor;
    activeAddress = kAlternateAddress;
  }

  if (sensor == nullptr) {
    Serial.println(
        "[NEXUS][BNO055_DIAGNOSTIC][FAIL] chip did not initialize");
    return;
  }

  sensor->setExtCrystalUse(false);
  sensor->setMode(OPERATION_MODE_ACCONLY);
  delay(100);
  printStatus("READY");
}

void loop() {
  const uint32_t now = millis();
  if (sensor == nullptr || now - lastSampleMs < kSampleIntervalMs) {
    delay(1);
    return;
  }
  lastSampleMs = now;

  if (!probe(activeAddress)) {
    Serial.println(
        "[NEXUS][BNO055_DIAGNOSTIC][NO_ACK] check VCC/GND/SDA/SCL");
    return;
  }

  const imu::Vector<3> acceleration =
      sensor->getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER);
  const float norm =
      std::sqrt(acceleration.x() * acceleration.x() +
                acceleration.y() * acceleration.y() +
                acceleration.z() * acceleration.z());
  Serial.printf(
      "[NEXUS][BNO055_DIAGNOSTIC][SAMPLE] mode=0x%02X "
      "accel=(%.3f,%.3f,%.3f)m/s2 norm=%.3f\n",
      static_cast<unsigned>(sensor->getMode()), acceleration.x(),
      acceleration.y(), acceleration.z(), norm);
}
