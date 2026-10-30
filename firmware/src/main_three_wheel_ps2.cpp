#include <Arduino.h>
#include <Wire.h>

#include <cmath>

#include "nexus_contract_v1.h"
#include "nexus_hardware_profile.generated.h"

#ifdef NEXUS_BNO055_ENABLED
#include <Adafruit_BNO055.h>
#include <Adafruit_Sensor.h>
#endif

#ifndef NEXUS_THREE_WHEEL_PS2_PROFILE
#error "main_three_wheel_ps2.cpp requires a hardware profile with firmware.control"
#endif

namespace {
constexpr uint8_t kInaSdaPin = NEXUS_I2C_SDA_PIN;
constexpr uint8_t kInaSclPin = NEXUS_I2C_SCL_PIN;
constexpr uint8_t kIna219Address = NEXUS_SENSOR_I2C_ADDRESS;
constexpr float kIna219ShuntOhms = NEXUS_SENSOR_SHUNT_OHMS;
constexpr float kIna219CurrentLsbMa = NEXUS_SENSOR_CURRENT_LSB_MA;
constexpr uint16_t kIna219Configuration = 0x3DDF;
constexpr uint16_t kIna219Calibration = 4096;
constexpr float kIna219BusLsbV = 0.004f;
constexpr float kIna219ShuntLsbMv = 0.01f;
constexpr float kMinBusVoltageV = NEXUS_MIN_BUS_VOLTAGE_MV / 1000.0f;
constexpr float kMaxBusVoltageV = NEXUS_MAX_BUS_VOLTAGE_MV / 1000.0f;
constexpr float kMaxCurrentMa = NEXUS_MAX_CURRENT_MA;
constexpr uint8_t kMaxPwmPercent = NEXUS_MAX_PWM_PERCENT;
constexpr uint32_t kTelemetryIntervalMs = NEXUS_TELEMETRY_INTERVAL_MS;
constexpr uint32_t kPs2PollIntervalMs = NEXUS_PS2_POLL_INTERVAL_MS;
constexpr uint32_t kPs2FailsafeTimeoutMs = NEXUS_PS2_FAILSAFE_TIMEOUT_MS;
constexpr uint8_t kJoystickDeadzone = NEXUS_JOYSTICK_DEADZONE;
constexpr float kEncoderCountsPerOutputRevolution =
    NEXUS_ENCODER_COUNTS_PER_OUTPUT_REVOLUTION;
constexpr uint32_t kRpmWindowMs = 250;
constexpr uint32_t kSensorReadIntervalMs = 100;
constexpr uint32_t kSensorRetryIntervalMs = 5000;
constexpr uint32_t kProfileHeartbeatMs = 10000;
constexpr uint32_t kEncoderMissingReportMs = 1000;
constexpr uint16_t kPs2SelectMask = 0x0001;
constexpr uint16_t kPs2StartMask = 0x0008;
constexpr uint8_t kPs2TransferDelayUs = 8;
constexpr float kSqrt3Over2 = 0.8660254f;
constexpr uint8_t kArmCenteredPackets = NEXUS_ARM_CENTERED_PACKETS;
// Limit the PWM change on each PS2 packet so all three motors do not demand
// their full start current at the same instant.  Safety stops still bypass the
// ramp and disable every output immediately.
constexpr int kMotorRampStepPercent = 4;
constexpr float kBalancePidKp = NEXUS_BALANCE_PID_KP;
constexpr float kBalancePidKi = NEXUS_BALANCE_PID_KI;
constexpr float kBalancePidKd = NEXUS_BALANCE_PID_KD;
constexpr int kBalancePidMaxCorrectionPercent =
    NEXUS_BALANCE_PID_MAX_CORRECTION_PERCENT;
constexpr uint32_t kImuReadIntervalMs = 100;
constexpr uint32_t kImuRetryIntervalMs = 5000;
#ifdef NEXUS_BNO055_ENABLED
constexpr uint8_t kBno055PreferredAddress = NEXUS_BNO055_I2C_ADDRESS;
constexpr uint8_t kBno055AlternateAddress =
    NEXUS_BNO055_I2C_ADDRESS == 0x28 ? 0x29 : 0x28;
#endif

struct MotorConfig {
  uint8_t enablePin;
  uint8_t in1Pin;
  uint8_t in2Pin;
  uint8_t encoderAPin;
  uint8_t encoderBPin;
  const char* name;
};

constexpr MotorConfig kMotors[3] = {
    {NEXUS_MOTOR_1_ENABLE_PIN, NEXUS_MOTOR_1_IN1_PIN, NEXUS_MOTOR_1_IN2_PIN,
     NEXUS_MOTOR_1_ENCODER_A_PIN, NEXUS_MOTOR_1_ENCODER_B_PIN, "front_left"},
    {NEXUS_MOTOR_2_ENABLE_PIN, NEXUS_MOTOR_2_IN1_PIN, NEXUS_MOTOR_2_IN2_PIN,
     NEXUS_MOTOR_2_ENCODER_A_PIN, NEXUS_MOTOR_2_ENCODER_B_PIN, "front_right"},
    {NEXUS_MOTOR_3_ENABLE_PIN, NEXUS_MOTOR_3_IN1_PIN, NEXUS_MOTOR_3_IN2_PIN,
     NEXUS_MOTOR_3_ENCODER_A_PIN, NEXUS_MOTOR_3_ENCODER_B_PIN, "rear"},
};

struct PowerMeasurement {
  bool valid = false;
  float busVoltageV = 0.0f;
  float currentMa = 0.0f;
  float powerMw = 0.0f;
};

struct Ps2State {
  bool connected = false;
  uint16_t buttons = 0;
  uint8_t leftX = 128;
  uint8_t leftY = 128;
  uint8_t rightX = 128;
  uint8_t rightY = 128;
};

struct ImuMeasurement {
  bool valid = false;
  float headingDeg = 0.0f;
  float rollDeg = 0.0f;
  float pitchDeg = 0.0f;
  float accelXMps2 = 0.0f;
  float accelYMps2 = 0.0f;
  float accelZMps2 = 0.0f;
};

class DfRobotIna219 {
 public:
  explicit DfRobotIna219(uint8_t address) : address_(address) {}

  bool begin() {
    if (!writeRegister(0x00, 0x8000)) {
      return false;
    }
    delay(2);
    return writeRegister(0x05, kIna219Calibration) &&
           writeRegister(0x00, kIna219Configuration) && verifyConfiguration();
  }

  bool verifyConfiguration() {
    uint16_t configuration = 0;
    uint16_t calibration = 0;
    return readRegister(0x00, configuration) &&
           readRegister(0x05, calibration) &&
           configuration == kIna219Configuration &&
           calibration == kIna219Calibration;
  }

  bool read(float& busVoltageV, float& shuntVoltageMv, float& currentMa,
            float& sensorPowerMw) {
    uint16_t busRaw = 0;
    uint16_t shuntRaw = 0;
    uint16_t currentRaw = 0;
    uint16_t powerRaw = 0;
    if (!readRegister(0x02, busRaw) || !readRegister(0x01, shuntRaw) ||
        !readRegister(0x04, currentRaw) || !readRegister(0x03, powerRaw)) {
      return false;
    }
    busVoltageV = static_cast<float>(busRaw >> 3) * kIna219BusLsbV;
    shuntVoltageMv =
        static_cast<float>(static_cast<int16_t>(shuntRaw)) * kIna219ShuntLsbMv;
    currentMa = static_cast<float>(static_cast<int16_t>(currentRaw)) *
                kIna219CurrentLsbMa;
    sensorPowerMw = static_cast<float>(powerRaw) *
                    (20.0f * kIna219CurrentLsbMa);
    return true;
  }

 private:
  bool writeRegister(uint8_t registerAddress, uint16_t value) {
    Wire.beginTransmission(address_);
    Wire.write(registerAddress);
    Wire.write(static_cast<uint8_t>(value >> 8));
    Wire.write(static_cast<uint8_t>(value & 0xFF));
    return Wire.endTransmission(true) == 0;
  }

  bool readRegister(uint8_t registerAddress, uint16_t& value) {
    Wire.beginTransmission(address_);
    Wire.write(registerAddress);
    if (Wire.endTransmission(false) != 0 ||
        Wire.requestFrom(static_cast<int>(address_), 2, 1) != 2) {
      return false;
    }
    value = static_cast<uint16_t>(Wire.read()) << 8;
    value |= static_cast<uint16_t>(Wire.read());
    return true;
  }

  uint8_t address_;
};

DfRobotIna219 currentSensor(kIna219Address);
#ifdef NEXUS_BNO055_ENABLED
Adafruit_BNO055 imuSensorPreferred(55, kBno055PreferredAddress, &Wire);
Adafruit_BNO055 imuSensorAlternate(56, kBno055AlternateAddress, &Wire);
Adafruit_BNO055* activeImuSensor = nullptr;
uint8_t activeBno055Address = 0;
#endif
volatile uint32_t encoderEdges[3] = {0, 0, 0};
volatile uint32_t encoderAEdges[3] = {0, 0, 0};
volatile uint32_t encoderBEdges[3] = {0, 0, 0};
volatile uint8_t encoderLastState[3] = {0, 0, 0};
float motorRpm[3] = {0.0f, 0.0f, 0.0f};
int8_t motorCommandPercent[3] = {0, 0, 0};
int8_t requestedMotorCommandPercent[3] = {0, 0, 0};
float balanceCorrectionPercent[3] = {0.0f, 0.0f, 0.0f};
float balanceIntegral[3] = {0.0f, 0.0f, 0.0f};
float balancePreviousError[3] = {0.0f, 0.0f, 0.0f};
uint32_t motorCommandStartedMs[3] = {0, 0, 0};
bool encoderFaultReported[3] = {false, false, false};
bool currentSensorReady = false;
bool powerSafetyBlocked = true;
bool emergencyStopLatched = false;
bool driveArmed = false;
bool balancePidActive = false;
bool ps2FailsafeActive = true;
bool ps2FailureReported = false;
bool ps2AnalogModeFailureReported = false;
bool powerFailureReported = false;
bool encoderOpenLoopReported = false;
bool imuReady = false;
bool imuFailureReported = false;
bool imuDataFailureReported = false;
uint8_t imuZeroGravitySamples = 0;
uint32_t telemetrySequence = 0;
uint32_t lastSensorInitAttemptMs = 0;
uint32_t lastSensorReadMs = 0;
uint32_t lastTelemetryMs = 0;
uint32_t lastProfileHeartbeatMs = 0;
uint32_t lastRpmWindowMs = 0;
uint32_t lastPs2PollMs = 0;
uint32_t lastPs2PacketMs = 0;
uint32_t lastImuReadMs = 0;
uint32_t lastImuInitAttemptMs = 0;
uint16_t previousPs2Buttons = 0;
uint8_t centeredPacketCount = 0;
#ifdef NEXUS_PS2_DIAGNOSTIC
uint32_t lastPs2DiagnosticMs = 0;
uint16_t lastPs2DiagnosticButtons = 0xFFFF;
uint8_t lastPs2DiagnosticAxes[4] = {0, 0, 0, 0};
#endif
PowerMeasurement latestPower;
ImuMeasurement latestImu;
Ps2State ps2;
String deviceId;

void IRAM_ATTR handleEncoderChange(uint8_t index) {
  const uint8_t state =
      (digitalRead(kMotors[index].encoderAPin) == HIGH ? 0x02 : 0x00) |
      (digitalRead(kMotors[index].encoderBPin) == HIGH ? 0x01 : 0x00);
  const uint8_t changed = state ^ encoderLastState[index];
  if ((changed & 0x02) != 0) {
    ++encoderAEdges[index];
    ++encoderEdges[index];
  }
  if ((changed & 0x01) != 0) {
    ++encoderBEdges[index];
    ++encoderEdges[index];
  }
  encoderLastState[index] = state;
}

void IRAM_ATTR handleEncoder1() { handleEncoderChange(0); }
void IRAM_ATTR handleEncoder2() { handleEncoderChange(1); }
void IRAM_ATTR handleEncoder3() { handleEncoderChange(2); }

void setMotor(uint8_t index, int commandPercent) {
  commandPercent = constrain(commandPercent, -static_cast<int>(kMaxPwmPercent),
                             static_cast<int>(kMaxPwmPercent));
  const int8_t previous = motorCommandPercent[index];
  motorCommandPercent[index] = static_cast<int8_t>(commandPercent);

  if (commandPercent == 0) {
    analogWrite(kMotors[index].enablePin, 0);
    digitalWrite(kMotors[index].in1Pin, LOW);
    digitalWrite(kMotors[index].in2Pin, LOW);
    motorCommandStartedMs[index] = 0;
    return;
  }

  digitalWrite(kMotors[index].in1Pin, commandPercent > 0 ? HIGH : LOW);
  digitalWrite(kMotors[index].in2Pin, commandPercent > 0 ? LOW : HIGH);
  analogWrite(kMotors[index].enablePin,
              map(abs(commandPercent), 0, 100, 0, 255));
  if (previous == 0) {
    motorCommandStartedMs[index] = millis();
  }
}

void stopAllMotors() {
  for (uint8_t index = 0; index < 3; ++index) {
    requestedMotorCommandPercent[index] = 0;
    balanceCorrectionPercent[index] = 0.0f;
    balanceIntegral[index] = 0.0f;
    balancePreviousError[index] = 0.0f;
    setMotor(index, 0);
  }
  balancePidActive = false;
}

bool anyMotorEnabled() {
  return motorCommandPercent[0] != 0 || motorCommandPercent[1] != 0 ||
         motorCommandPercent[2] != 0;
}

bool probeIna219Signal(bool logFailure) {
  const bool sdaHigh = digitalRead(kInaSdaPin) == HIGH;
  const bool sclHigh = digitalRead(kInaSclPin) == HIGH;
  if (!sdaHigh || !sclHigh) {
    if (logFailure) {
      if (!sdaHigh) {
        Serial.printf("[NEXUS][ERROR][I2C_SDA_STUCK_LOW] SDA=GPIO%d is LOW\n",
                      kInaSdaPin);
      }
      if (!sclHigh) {
        Serial.printf("[NEXUS][ERROR][I2C_SCL_STUCK_LOW] SCL=GPIO%d is LOW\n",
                      kInaSclPin);
      }
    }
    return false;
  }

  Wire.beginTransmission(kIna219Address);
  const uint8_t error = Wire.endTransmission(true);
  if (error != 0) {
    if (logFailure) {
      Serial.printf(
          "[NEXUS][ERROR][INA219_I2C_NO_ACK] address=0x%02X error=%u "
          "SDA=GPIO%d SCL=GPIO%d\n",
          kIna219Address, error, kInaSdaPin, kInaSclPin);
    }
    return false;
  }
  return true;
}

bool verifyIna219Configuration(bool logFailure) {
  const bool configurationOk = currentSensor.verifyConfiguration();
  if (!configurationOk && logFailure) {
    Serial.printf(
        "[NEXUS][ERROR][INA219_CONFIGURATION_MISMATCH] address=0x%02X "
        "expected_config=0x%04X expected_calibration=%u; motors stopped\n",
        kIna219Address, kIna219Configuration, kIna219Calibration);
  }
  return configurationOk;
}

bool initializeCurrentSensor() {
  lastSensorInitAttemptMs = millis();
  currentSensorReady = false;
  if (!probeIna219Signal(true) || !currentSensor.begin() ||
      !verifyIna219Configuration(true)) {
    stopAllMotors();
    return false;
  }

  currentSensorReady = true;
  Serial.printf(
      "[NEXUS][INFO][INA219_READY] model=SEN0291 address=0x%02X "
      "SDA=GPIO%d SCL=GPIO%d shunt=%.3fOhm current_lsb=%.1fmA\n",
      kIna219Address, kInaSdaPin, kInaSclPin, kIna219ShuntOhms,
      kIna219CurrentLsbMa);
  return true;
}

bool readPowerMeasurement(PowerMeasurement& measurement, bool logFailure) {
  if (!currentSensorReady || !probeIna219Signal(logFailure) ||
      !verifyIna219Configuration(logFailure)) {
    currentSensorReady = false;
    measurement.valid = false;
    stopAllMotors();
    return false;
  }

  float busVoltageV = 0.0f;
  float shuntVoltageMv = 0.0f;
  float currentMa = 0.0f;
  float sensorPowerMw = 0.0f;
  const bool registersOk = currentSensor.read(
      busVoltageV, shuntVoltageMv, currentMa, sensorPowerMw);
  const float powerMw = busVoltageV * currentMa;
  const float currentFromShuntMa = shuntVoltageMv / kIna219ShuntOhms;
  const float toleranceMa = fmaxf(10.0f, fabsf(currentFromShuntMa) * 0.25f);

  if (!registersOk || !std::isfinite(busVoltageV) ||
      !std::isfinite(shuntVoltageMv) || !std::isfinite(currentMa) ||
      !std::isfinite(sensorPowerMw) || !std::isfinite(powerMw) ||
      fabsf(currentMa - currentFromShuntMa) > toleranceMa) {
    if (logFailure) {
      Serial.printf(
          "[NEXUS][ERROR][INA219_SIGNAL_INVALID] registers_ok=%s "
          "register_ma=%.2f shunt_ma=%.2f sensor_power_mw=%.2f; motors stopped\n",
          registersOk ? "true" : "false", currentMa, currentFromShuntMa,
          sensorPowerMw);
    }
    currentSensorReady = false;
    measurement.valid = false;
    stopAllMotors();
    return false;
  }

  measurement.valid = true;
  measurement.busVoltageV = busVoltageV;
  measurement.currentMa = currentMa;
  measurement.powerMw = powerMw;
  return true;
}

bool probeI2cAddress(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission(true) == 0;
}

bool initializeImu() {
  lastImuInitAttemptMs = millis();
  imuReady = false;
  latestImu.valid = false;
#ifdef NEXUS_BNO055_ENABLED
  activeImuSensor = nullptr;
  activeBno055Address = 0;
  if (probeI2cAddress(kBno055PreferredAddress) &&
      imuSensorPreferred.begin(OPERATION_MODE_IMUPLUS)) {
    activeImuSensor = &imuSensorPreferred;
    activeBno055Address = kBno055PreferredAddress;
  } else if (probeI2cAddress(kBno055AlternateAddress) &&
             imuSensorAlternate.begin(OPERATION_MODE_IMUPLUS)) {
    activeImuSensor = &imuSensorAlternate;
    activeBno055Address = kBno055AlternateAddress;
  }
  if (activeImuSensor == nullptr) {
    if (!imuFailureReported) {
      Serial.printf(
          "[NEXUS][ERROR][BNO055_I2C_NO_ACK] addresses=0x%02X/0x%02X "
          "SDA=GPIO%d SCL=GPIO%d; check shared I2C, 3V3, GND and ADR\n",
          kBno055PreferredAddress, kBno055AlternateAddress, kInaSdaPin,
          kInaSclPin);
      imuFailureReported = true;
    }
    return false;
  }
  // Clone BNO055 breakouts do not always populate a working 32.768 kHz
  // crystal.  The internal oscillator is the portable baseline and avoids a
  // sensor that ACKs correctly while every fused output remains at zero.
  activeImuSensor->setExtCrystalUse(false);
  activeImuSensor->setMode(OPERATION_MODE_IMUPLUS);
  delay(50);

  uint8_t systemStatus = 0;
  uint8_t selfTest = 0;
  uint8_t systemError = 0;
  uint8_t calibrationSystem = 0;
  uint8_t calibrationGyro = 0;
  uint8_t calibrationAccel = 0;
  uint8_t calibrationMag = 0;
  Adafruit_BNO055::adafruit_bno055_rev_info_t revision{};
  activeImuSensor->getSystemStatus(&systemStatus, &selfTest, &systemError);
  activeImuSensor->getCalibration(&calibrationSystem, &calibrationGyro,
                                  &calibrationAccel, &calibrationMag);
  activeImuSensor->getRevInfo(&revision);
  imuReady = true;
  imuFailureReported = false;
  imuDataFailureReported = false;
  imuZeroGravitySamples = 0;
  Serial.printf(
      "[NEXUS][INFO][BNO055_READY] address=0x%02X SDA=GPIO%d SCL=GPIO%d "
      "clock=internal fusion=imuplus mode=0x%02X sys=%u self_test=0x%02X error=%u "
      "calibration=%u/%u/%u/%u sw_rev=%u\n",
      activeBno055Address, kInaSdaPin, kInaSclPin,
      static_cast<unsigned>(activeImuSensor->getMode()), systemStatus, selfTest,
      systemError, calibrationSystem, calibrationGyro, calibrationAccel,
      calibrationMag, revision.sw_rev);
  return true;
#else
  return false;
#endif
}

bool readImuMeasurement() {
  if (!imuReady) {
    latestImu.valid = false;
    return false;
  }
#ifdef NEXUS_BNO055_ENABLED
  if (activeImuSensor == nullptr || !probeI2cAddress(activeBno055Address)) {
    imuReady = false;
    latestImu.valid = false;
    if (!imuFailureReported) {
      Serial.println(
          "[NEXUS][ERROR][BNO055_SIGNAL_LOST] IMU stopped acknowledging on I2C; "
          "check SDA/SCL, 3V3 and GND");
      imuFailureReported = true;
    }
    return false;
  }

  sensors_event_t orientation{};
  sensors_event_t acceleration{};
  sensors_event_t rawAcceleration{};
  const bool orientationOk =
      activeImuSensor->getEvent(&orientation, Adafruit_BNO055::VECTOR_EULER);
  const bool accelerationOk =
      activeImuSensor->getEvent(&acceleration,
                                Adafruit_BNO055::VECTOR_LINEARACCEL);
  const bool rawAccelerationOk = activeImuSensor->getEvent(
      &rawAcceleration, Adafruit_BNO055::VECTOR_ACCELEROMETER);
  const bool valuesOk =
      orientationOk && accelerationOk && rawAccelerationOk &&
      std::isfinite(orientation.orientation.x) &&
      std::isfinite(orientation.orientation.y) &&
      std::isfinite(orientation.orientation.z) &&
      std::isfinite(acceleration.acceleration.x) &&
      std::isfinite(acceleration.acceleration.y) &&
      std::isfinite(acceleration.acceleration.z) &&
      std::isfinite(rawAcceleration.acceleration.x) &&
      std::isfinite(rawAcceleration.acceleration.y) &&
      std::isfinite(rawAcceleration.acceleration.z);
  if (!valuesOk) {
    latestImu.valid = false;
    return false;
  }

  const float rawAccelerationNorm =
      std::sqrt(rawAcceleration.acceleration.x * rawAcceleration.acceleration.x +
                rawAcceleration.acceleration.y * rawAcceleration.acceleration.y +
                rawAcceleration.acceleration.z * rawAcceleration.acceleration.z);
  if (rawAccelerationNorm < 1.0f) {
    if (imuZeroGravitySamples < UINT8_MAX) {
      ++imuZeroGravitySamples;
    }
    latestImu.valid = false;
    if (imuZeroGravitySamples >= 10 && !imuDataFailureReported) {
      uint8_t systemStatus = 0;
      uint8_t selfTest = 0;
      uint8_t systemError = 0;
      uint8_t calibrationSystem = 0;
      uint8_t calibrationGyro = 0;
      uint8_t calibrationAccel = 0;
      uint8_t calibrationMag = 0;
      activeImuSensor->getSystemStatus(&systemStatus, &selfTest, &systemError);
      activeImuSensor->getCalibration(&calibrationSystem, &calibrationGyro,
                                      &calibrationAccel, &calibrationMag);
      Serial.printf(
          "[NEXUS][ERROR][BNO055_DATA_STUCK] raw_accel=%.3f m/s2 mode=0x%02X "
          "sys=%u self_test=0x%02X error=%u calibration=%u/%u/%u/%u; "
          "sensor ACKs but measurement engine is not producing data\n",
          rawAccelerationNorm,
          static_cast<unsigned>(activeImuSensor->getMode()),
          systemStatus, selfTest, systemError, calibrationSystem,
          calibrationGyro, calibrationAccel, calibrationMag);
      imuDataFailureReported = true;
    }
    return false;
  }
  imuZeroGravitySamples = 0;
  imuDataFailureReported = false;

  latestImu.valid = true;
  latestImu.headingDeg = orientation.orientation.x;
  latestImu.rollDeg = orientation.orientation.y;
  latestImu.pitchDeg = orientation.orientation.z;
  latestImu.accelXMps2 = acceleration.acceleration.x;
  latestImu.accelYMps2 = acceleration.acceleration.y;
  latestImu.accelZMps2 = acceleration.acceleration.z;
  return true;
#else
  return false;
#endif
}

uint8_t transferPs2Byte(uint8_t outgoing) {
  uint8_t incoming = 0;
  for (uint8_t bit = 0; bit < 8; ++bit) {
    digitalWrite(NEXUS_PS2_CMD_PIN, (outgoing & 0x01) != 0 ? HIGH : LOW);
    delayMicroseconds(kPs2TransferDelayUs);
    digitalWrite(NEXUS_PS2_CLK_PIN, LOW);
    delayMicroseconds(kPs2TransferDelayUs);
    if (digitalRead(NEXUS_PS2_DATA_PIN) == HIGH) {
      incoming |= static_cast<uint8_t>(1U << bit);
    }
    digitalWrite(NEXUS_PS2_CLK_PIN, HIGH);
    delayMicroseconds(kPs2TransferDelayUs);
    outgoing >>= 1;
  }
  return incoming;
}

void transactPs2(const uint8_t* command, uint8_t* response, size_t length) {
  digitalWrite(NEXUS_PS2_ATT_PIN, LOW);
  delayMicroseconds(15);
  for (size_t index = 0; index < length; ++index) {
    response[index] = transferPs2Byte(command[index]);
  }
  digitalWrite(NEXUS_PS2_ATT_PIN, HIGH);
  digitalWrite(NEXUS_PS2_CMD_PIN, HIGH);
  delayMicroseconds(15);
}

void configurePs2Receiver() {
  constexpr uint8_t enterConfig[5] = {0x01, 0x43, 0x00, 0x01, 0x00};
  constexpr uint8_t enableAnalog[9] = {0x01, 0x44, 0x00, 0x01, 0x03,
                                       0x00, 0x00, 0x00, 0x00};
  constexpr uint8_t exitConfig[9] = {0x01, 0x43, 0x00, 0x00, 0x5A,
                                     0x5A, 0x5A, 0x5A, 0x5A};
  uint8_t response[9] = {};
  for (uint8_t attempt = 0; attempt < 3; ++attempt) {
    transactPs2(enterConfig, response, sizeof(enterConfig));
    delay(10);
    transactPs2(enableAnalog, response, sizeof(enableAnalog));
    delay(10);
    transactPs2(exitConfig, response, sizeof(exitConfig));
    delay(20);
  }
  Serial.printf(
      "[NEXUS][INFO][PS2_INTERFACE_READY] DATA=GPIO%d CMD=GPIO%d ATTN=GPIO%d "
      "CLK=GPIO%d VCC=3V3 ACK=NC VIBR=NC\n",
      NEXUS_PS2_DATA_PIN, NEXUS_PS2_CMD_PIN, NEXUS_PS2_ATT_PIN,
      NEXUS_PS2_CLK_PIN);
}

bool pollPs2Receiver() {
  constexpr uint8_t pollCommand[9] = {0x01, 0x42, 0x00, 0x00, 0x00,
                                      0x00, 0x00, 0x00, 0x00};
  uint8_t response[9] = {};
  transactPs2(pollCommand, response, sizeof(pollCommand));
  const bool validAnalogMode = response[1] == 0x73 || response[1] == 0x79;
  if (!validAnalogMode || response[2] != 0x5A) {
    if (response[1] == 0x41 && response[2] == 0x5A &&
        !ps2AnalogModeFailureReported) {
      Serial.println(
          "[NEXUS][ERROR][PS2_ANALOG_MODE_REQUIRED] Receiver is in digital mode; "
          "motor control remains disarmed. Press ANALOG or check receiver setup");
      ps2AnalogModeFailureReported = true;
    }
    ps2.connected = false;
    return false;
  }

  ps2AnalogModeFailureReported = false;
  ps2.connected = true;
  ps2.buttons = static_cast<uint16_t>(~(static_cast<uint16_t>(response[3]) |
                                         (static_cast<uint16_t>(response[4]) << 8)));
  ps2.rightX = response[5];
  ps2.rightY = response[6];
  ps2.leftX = response[7];
  ps2.leftY = response[8];
  lastPs2PacketMs = millis();
  return true;
}

int axisPercent(uint8_t raw, bool invert = false) {
  int value = static_cast<int>(raw) - 128;
  if (invert) {
    value = -value;
  }
  if (abs(value) <= kJoystickDeadzone) {
    return 0;
  }
  const int magnitude = map(abs(value), kJoystickDeadzone + 1, 127, 1, 100);
  return constrain(value < 0 ? -magnitude : magnitude, -100, 100);
}

#ifdef NEXUS_PS2_DIAGNOSTIC
void appendPs2Button(String& names, uint16_t buttons, uint16_t mask,
                     const char* label) {
  if ((buttons & mask) == 0) {
    return;
  }
  if (!names.isEmpty()) {
    names += "+";
  }
  names += label;
}

void emitPs2Diagnostic(uint32_t now) {
  const bool axesChanged =
      abs(static_cast<int>(ps2.leftX) - lastPs2DiagnosticAxes[0]) > 1 ||
      abs(static_cast<int>(ps2.leftY) - lastPs2DiagnosticAxes[1]) > 1 ||
      abs(static_cast<int>(ps2.rightX) - lastPs2DiagnosticAxes[2]) > 1 ||
      abs(static_cast<int>(ps2.rightY) - lastPs2DiagnosticAxes[3]) > 1;
  const bool buttonsChanged = ps2.buttons != lastPs2DiagnosticButtons;
  const bool heartbeatDue = now - lastPs2DiagnosticMs >= 1000;
  if ((!axesChanged && !buttonsChanged && !heartbeatDue) ||
      now - lastPs2DiagnosticMs < 100) {
    return;
  }

  const int moveX = axisPercent(ps2.leftX);
  const int moveY = axisPercent(ps2.leftY, true);
  const int rotation = axisPercent(ps2.rightX);
  float wheel[3] = {
      -kSqrt3Over2 * (moveX / 100.0f) + 0.5f * (moveY / 100.0f) +
          (rotation / 100.0f),
      kSqrt3Over2 * (moveX / 100.0f) + 0.5f * (moveY / 100.0f) +
          (rotation / 100.0f),
      -(moveY / 100.0f) + (rotation / 100.0f),
  };
  float peak = 1.0f;
  for (float value : wheel) {
    peak = fmaxf(peak, fabsf(value));
  }
  int preview[3] = {};
  for (uint8_t index = 0; index < 3; ++index) {
    preview[index] = static_cast<int>(
        lroundf((wheel[index] / peak) * kMaxPwmPercent));
  }

  String names;
  appendPs2Button(names, ps2.buttons, 0x0001, "SELECT");
  appendPs2Button(names, ps2.buttons, 0x0002, "L3");
  appendPs2Button(names, ps2.buttons, 0x0004, "R3");
  appendPs2Button(names, ps2.buttons, 0x0008, "START");
  appendPs2Button(names, ps2.buttons, 0x0010, "UP");
  appendPs2Button(names, ps2.buttons, 0x0020, "RIGHT");
  appendPs2Button(names, ps2.buttons, 0x0040, "DOWN");
  appendPs2Button(names, ps2.buttons, 0x0080, "LEFT");
  appendPs2Button(names, ps2.buttons, 0x0100, "L2");
  appendPs2Button(names, ps2.buttons, 0x0200, "R2");
  appendPs2Button(names, ps2.buttons, 0x0400, "L1");
  appendPs2Button(names, ps2.buttons, 0x0800, "R1");
  appendPs2Button(names, ps2.buttons, 0x1000, "TRIANGLE");
  appendPs2Button(names, ps2.buttons, 0x2000, "CIRCLE");
  appendPs2Button(names, ps2.buttons, 0x4000, "CROSS");
  appendPs2Button(names, ps2.buttons, 0x8000, "SQUARE");
  if (names.isEmpty()) {
    names = "NONE";
  }

  Serial.printf(
      "[NEXUS][PS2_TEST] buttons=0x%04X names=%s "
      "raw_lx=%u raw_ly=%u raw_rx=%u raw_ry=%u "
      "move_x=%d move_y=%d rotate=%d "
      "preview_front=%d preview_rear_left=%d preview_rear_right=%d "
      "motors_forced_off=true\n",
      ps2.buttons, names.c_str(), ps2.leftX, ps2.leftY, ps2.rightX,
      ps2.rightY, moveX, moveY, rotation, preview[0], preview[1],
      preview[2]);

  lastPs2DiagnosticMs = now;
  lastPs2DiagnosticButtons = ps2.buttons;
  lastPs2DiagnosticAxes[0] = ps2.leftX;
  lastPs2DiagnosticAxes[1] = ps2.leftY;
  lastPs2DiagnosticAxes[2] = ps2.rightX;
  lastPs2DiagnosticAxes[3] = ps2.rightY;
}
#endif

bool sticksAreCentered() {
  return axisPercent(ps2.leftX) == 0 && axisPercent(ps2.leftY) == 0 &&
         axisPercent(ps2.rightX) == 0 && axisPercent(ps2.rightY) == 0;
}

void resetBalanceCorrections() {
  for (uint8_t index = 0; index < 3; ++index) {
    balanceCorrectionPercent[index] = 0.0f;
    balanceIntegral[index] = 0.0f;
    balancePreviousError[index] = 0.0f;
  }
  balancePidActive = false;
}

void applyRequestedMotorOutputs() {
  for (uint8_t index = 0; index < 3; ++index) {
    const int requested = requestedMotorCommandPercent[index];
    if (requested == 0) {
      setMotor(index, 0);
      continue;
    }
    const int correctedMagnitude = constrain(
        static_cast<int>(lroundf(abs(requested) + balanceCorrectionPercent[index])),
        0, static_cast<int>(kMaxPwmPercent));
    int target = requested > 0 ? correctedMagnitude : -correctedMagnitude;
    const int current = motorCommandPercent[index];

    // Always reach zero before reversing an H-bridge. This avoids the large
    // current spike produced by changing direction under load.
    if ((current > 0 && target < 0) || (current < 0 && target > 0)) {
      target = 0;
    }

    int ramped = current;
    if (target > current) {
      ramped = min(current + kMotorRampStepPercent, target);
    } else if (target < current) {
      ramped = max(current - kMotorRampStepPercent, target);
    }
    setMotor(index, ramped);
  }
}

void applyTriangleDrive() {
  if (!driveArmed || !ps2.connected || ps2FailsafeActive || emergencyStopLatched ||
      powerSafetyBlocked || !latestPower.valid) {
    stopAllMotors();
    return;
  }

  const float x = axisPercent(ps2.leftX) / 100.0f;
  const float y = axisPercent(ps2.leftY, true) / 100.0f;
  const float rotation = axisPercent(ps2.rightX) / 100.0f;
  float wheel[3] = {
      -kSqrt3Over2 * x + 0.5f * y + rotation,
      kSqrt3Over2 * x + 0.5f * y + rotation,
      -y + rotation,
  };

  float peak = 1.0f;
  for (float value : wheel) {
    peak = fmaxf(peak, fabsf(value));
  }
  for (uint8_t index = 0; index < 3; ++index) {
    const int command = static_cast<int>(lroundf((wheel[index] / peak) *
                                                  kMaxPwmPercent));
    requestedMotorCommandPercent[index] = static_cast<int8_t>(command);
  }
  if (requestedMotorCommandPercent[0] == 0 &&
      requestedMotorCommandPercent[1] == 0 &&
      requestedMotorCommandPercent[2] == 0) {
    resetBalanceCorrections();
  }
  applyRequestedMotorOutputs();
}

void updateBalancePid(float elapsedSeconds) {
  if (!driveArmed || ps2FailsafeActive || emergencyStopLatched ||
      powerSafetyBlocked || elapsedSeconds <= 0.0f) {
    resetBalanceCorrections();
    return;
  }

  uint8_t activeMotors = 0;
  float totalRequestedMagnitude = 0.0f;
  float totalMeasuredRpm = 0.0f;
  for (uint8_t index = 0; index < 3; ++index) {
    if (requestedMotorCommandPercent[index] != 0) {
      ++activeMotors;
      totalRequestedMagnitude += abs(requestedMotorCommandPercent[index]);
      totalMeasuredRpm += motorRpm[index];
    }
  }

  if (activeMotors < 2 || totalRequestedMagnitude <= 0.0f ||
      totalMeasuredRpm < 1.0f) {
    resetBalanceCorrections();
    applyRequestedMotorOutputs();
    return;
  }

  const float rpmPerCommandPercent = totalMeasuredRpm / totalRequestedMagnitude;
  const float integralLimit =
      kBalancePidKi > 0.0f
          ? static_cast<float>(kBalancePidMaxCorrectionPercent) / kBalancePidKi
          : 0.0f;
  for (uint8_t index = 0; index < 3; ++index) {
    if (requestedMotorCommandPercent[index] == 0) {
      balanceCorrectionPercent[index] = 0.0f;
      balanceIntegral[index] = 0.0f;
      balancePreviousError[index] = 0.0f;
      continue;
    }
    const float targetRpm =
        abs(requestedMotorCommandPercent[index]) * rpmPerCommandPercent;
    const float error = targetRpm - motorRpm[index];
    balanceIntegral[index] =
        constrain(balanceIntegral[index] + error * elapsedSeconds,
                  -integralLimit, integralLimit);
    const float derivative =
        (error - balancePreviousError[index]) / elapsedSeconds;
    balancePreviousError[index] = error;
    balanceCorrectionPercent[index] = constrain(
        kBalancePidKp * error + kBalancePidKi * balanceIntegral[index] +
            kBalancePidKd * derivative,
        -static_cast<float>(kBalancePidMaxCorrectionPercent),
        static_cast<float>(kBalancePidMaxCorrectionPercent));
  }
  balancePidActive = true;
  applyRequestedMotorOutputs();
}

void updatePowerSafety() {
  const bool blocked = !latestPower.valid ||
                       latestPower.busVoltageV < kMinBusVoltageV ||
                       latestPower.busVoltageV > kMaxBusVoltageV;
  if (blocked != powerSafetyBlocked) {
    powerSafetyBlocked = blocked;
    if (blocked) {
      Serial.printf(
          "[NEXUS][ERROR][MOTOR_POWER_UNSAFE] bus_voltage_v=%.3f allowed=%.1f..%.1f; "
          "motors stopped\n",
          latestPower.busVoltageV, kMinBusVoltageV, kMaxBusVoltageV);
      driveArmed = false;
      centeredPacketCount = 0;
      stopAllMotors();
      powerFailureReported = true;
    } else {
      Serial.printf("[NEXUS][INFO][MOTOR_POWER_OK] bus_voltage_v=%.3f\n",
                    latestPower.busVoltageV);
      powerFailureReported = false;
    }
  }

  if (latestPower.valid && fabsf(latestPower.currentMa) > kMaxCurrentMa) {
    if (!emergencyStopLatched) {
      Serial.printf(
          "[NEXUS][ERROR][OVERCURRENT_ESTOP] current_ma=%.2f limit_ma=%.2f; "
          "SELECT latch engaged\n",
          latestPower.currentMa, kMaxCurrentMa);
    }
    emergencyStopLatched = true;
    driveArmed = false;
    stopAllMotors();
  }
}

void servicePs2() {
  const uint32_t now = millis();
  if (now - lastPs2PollMs < kPs2PollIntervalMs) {
    return;
  }
  lastPs2PollMs = now;
  const bool received = pollPs2Receiver();
  const bool timedOut = !received &&
                        (lastPs2PacketMs == 0 ||
                         now - lastPs2PacketMs > kPs2FailsafeTimeoutMs);
  if (timedOut) {
    ps2FailsafeActive = true;
    driveArmed = false;
    centeredPacketCount = 0;
    previousPs2Buttons = 0;
    stopAllMotors();
    if (!ps2FailureReported) {
      Serial.printf(
          "[NEXUS][ERROR][PS2_SIGNAL_LOST] No valid packet for %lu ms; all motors stopped. "
          "Check DATA/CMD/ATTN/CLK and receiver pairing\n",
          static_cast<unsigned long>(lastPs2PacketMs == 0 ? now
                                                          : now - lastPs2PacketMs));
      ps2FailureReported = true;
    }
    return;
  }
  if (!received) {
    return;
  }

  if (ps2FailsafeActive) {
    Serial.println("[NEXUS][INFO][PS2_SIGNAL_RECOVERED] Valid controller packet received");
  }
  ps2FailsafeActive = false;
  ps2FailureReported = false;

#ifdef NEXUS_PS2_DIAGNOSTIC
  driveArmed = false;
  emergencyStopLatched = true;
  stopAllMotors();
  emitPs2Diagnostic(now);
  previousPs2Buttons = ps2.buttons;
  return;
#endif

  const bool sticksCentered = sticksAreCentered();
  if (sticksCentered) {
    if (centeredPacketCount < kArmCenteredPackets) {
      ++centeredPacketCount;
    }
  } else {
    centeredPacketCount = 0;
  }

  const bool selectPressed =
      (ps2.buttons & kPs2SelectMask) != 0 &&
      (previousPs2Buttons & kPs2SelectMask) == 0;
  const bool startPressed =
      (ps2.buttons & kPs2StartMask) != 0 &&
      (previousPs2Buttons & kPs2StartMask) == 0;
  previousPs2Buttons = ps2.buttons;

  if (selectPressed) {
    if (!emergencyStopLatched) {
      Serial.println(
          "[NEXUS][WARNING][PS2_ESTOP_LATCHED] SELECT pressed; all motors stopped");
    }
    emergencyStopLatched = true;
    driveArmed = false;
    centeredPacketCount = 0;
    stopAllMotors();
  }

  const bool armConditionsMet =
      centeredPacketCount >= kArmCenteredPackets && latestPower.valid &&
      !powerSafetyBlocked &&
      fabsf(latestPower.currentMa) <= kMaxCurrentMa;
  if (startPressed && armConditionsMet) {
    emergencyStopLatched = false;
    driveArmed = true;
    Serial.println(
        "[NEXUS][INFO][PS2_DRIVE_ARMED] START edge received after centered "
        "analog packets and safe power; manual control enabled");
  } else if (startPressed && !armConditionsMet) {
    driveArmed = false;
    stopAllMotors();
    Serial.printf(
        "[NEXUS][WARNING][PS2_ARM_REJECTED] centered_packets=%u/%u "
        "power_valid=%s power_safe=%s current_ma=%.2f; motors remain stopped\n",
        centeredPacketCount, kArmCenteredPackets,
        latestPower.valid ? "true" : "false",
        powerSafetyBlocked ? "false" : "true", latestPower.currentMa);
  } else if (!driveArmed && !emergencyStopLatched && armConditionsMet) {
    // Normal startup and signal recovery do not require START. Requiring
    // centered sticks first prevents an unexpected jump when the receiver
    // reconnects while a joystick is displaced. START remains the deliberate
    // reset action after SELECT has latched an emergency stop.
    driveArmed = true;
    Serial.println(
        "[NEXUS][INFO][PS2_DRIVE_AUTO_ARMED] PS2 connected, sticks centered "
        "and motor power safe; manual control enabled without START");
  }

  if (driveArmed) {
    applyTriangleDrive();
  } else {
    stopAllMotors();
  }
}

void updateRpm() {
  const uint32_t now = millis();
  const uint32_t elapsedMs = now - lastRpmWindowMs;
  if (elapsedMs < kRpmWindowMs) {
    return;
  }

  uint32_t edges[3] = {};
  uint32_t aEdges[3] = {};
  uint32_t bEdges[3] = {};
  noInterrupts();
  for (uint8_t index = 0; index < 3; ++index) {
    edges[index] = encoderEdges[index];
    aEdges[index] = encoderAEdges[index];
    bEdges[index] = encoderBEdges[index];
    encoderEdges[index] = 0;
    encoderAEdges[index] = 0;
    encoderBEdges[index] = 0;
  }
  interrupts();

  bool encoderSafetyFault = false;
  for (uint8_t index = 0; index < 3; ++index) {
    motorRpm[index] =
        edges[index] * 60000.0f /
        (static_cast<float>(elapsedMs) * kEncoderCountsPerOutputRevolution);
    const bool commandedLongEnough =
        motorCommandPercent[index] != 0 && motorCommandStartedMs[index] != 0 &&
        now - motorCommandStartedMs[index] >= kEncoderMissingReportMs;
    if (commandedLongEnough && (aEdges[index] == 0 || bEdges[index] == 0)) {
      if (!encoderFaultReported[index]) {
        Serial.printf(
            "[NEXUS][ERROR][ENCODER_SIGNAL_MISSING] motor=%s A=GPIO%d edges=%lu "
            "B=GPIO%d edges=%lu; check yellow/green signal wires and 3V3/GND\n",
            kMotors[index].name, kMotors[index].encoderAPin,
            static_cast<unsigned long>(aEdges[index]),
            kMotors[index].encoderBPin,
            static_cast<unsigned long>(bEdges[index]));
        encoderFaultReported[index] = true;
      }
      encoderSafetyFault = true;
    } else if (aEdges[index] > 0 && bEdges[index] > 0 &&
               encoderFaultReported[index]) {
      Serial.printf("[NEXUS][INFO][ENCODER_SIGNAL_RECOVERED] motor=%s\n",
                    kMotors[index].name);
      encoderFaultReported[index] = false;
    }
  }
  lastRpmWindowMs = now;
  if (encoderSafetyFault) {
    // Manual driving remains available for bring-up even when one encoder is
    // missing.  PID is disabled because it cannot balance against invalid RPM,
    // while the independent undervoltage, overcurrent, PS2-loss and SELECT
    // emergency stops remain active.
    resetBalanceCorrections();
    if (!encoderOpenLoopReported) {
      Serial.println(
          "[NEXUS][WARNING][ENCODER_OPEN_LOOP] One or more commanded encoders "
          "are missing; balance PID disabled but PS2 manual control remains active");
      encoderOpenLoopReported = true;
    }
    return;
  }
  if (encoderOpenLoopReported) {
    Serial.println(
        "[NEXUS][INFO][ENCODER_CLOSED_LOOP_READY] All commanded encoder signals "
        "recovered; balance PID available");
    encoderOpenLoopReported = false;
  }
  updateBalancePid(static_cast<float>(elapsedMs) / 1000.0f);
}

void emitHardwareProfile() {
#ifdef NEXUS_BNO055_ENABLED
  Serial.printf(
      "[NEXUS][INFO][HARDWARE_PROFILE] profile_version=%s profile_id=%s "
      "profile_sha256=%s hardware_model_id=%s controller=%s sensor=%s driver=%s "
      "imu=bno055@0x%02X motor=3x-jgb37-520-12v-encoder control=ps2-receiver "
      "pins=sda1,scl2,m1-12-13-11-a16-b17,m2-15-18-21-a4-b5,"
      "m3-6-7-8-a9-b10,ps2-data38-cmd39-att40-clk41\n",
      NEXUS_HARDWARE_PROFILE_VERSION, NEXUS_HARDWARE_PROFILE_ID,
      NEXUS_HARDWARE_PROFILE_SHA256, NEXUS_HARDWARE_MODEL_ID,
      NEXUS_CONTROLLER_BOARD_ID, NEXUS_SENSOR_PROFILE, NEXUS_DRIVER_PROFILE,
      activeBno055Address == 0 ? kBno055PreferredAddress
                               : activeBno055Address);
#else
  Serial.printf(
      "[NEXUS][INFO][HARDWARE_PROFILE] profile_version=%s profile_id=%s "
      "profile_sha256=%s hardware_model_id=%s controller=%s sensor=%s driver=%s "
      "imu=none motor=3x-jgb37-520-12v-encoder control=ps2-receiver "
      "pins=sda1,scl2,m1-12-13-11-a16-b17,m2-15-18-21-a4-b5,"
      "m3-6-7-8-a9-b10,ps2-data38-cmd39-att40-clk41\n",
      NEXUS_HARDWARE_PROFILE_VERSION, NEXUS_HARDWARE_PROFILE_ID,
      NEXUS_HARDWARE_PROFILE_SHA256, NEXUS_HARDWARE_MODEL_ID,
      NEXUS_CONTROLLER_BOARD_ID, NEXUS_SENSOR_PROFILE, NEXUS_DRIVER_PROFILE);
#endif
}

void emitTelemetry() {
  if (!latestPower.valid) {
    return;
  }

  const uint32_t sequence = telemetrySequence++;
  const int maxPwm = max(max(abs(motorCommandPercent[0]),
                             abs(motorCommandPercent[1])),
                         abs(motorCommandPercent[2]));
  const float averageRpm =
      (motorRpm[0] + motorRpm[1] + motorRpm[2]) / 3.0f;
  const float minRpm = fminf(motorRpm[0], fminf(motorRpm[1], motorRpm[2]));
  const float maxRpm = fmaxf(motorRpm[0], fmaxf(motorRpm[1], motorRpm[2]));
  const uint32_t packetAgeMs =
      lastPs2PacketMs == 0 ? millis() : millis() - lastPs2PacketMs;
  const bool controlReady = ps2.connected && !ps2FailsafeActive &&
                             driveArmed && !emergencyStopLatched &&
                             !powerSafetyBlocked;
#ifdef NEXUS_BNO055_ENABLED
  const float signalQuality =
      currentSensorReady && ps2.connected && imuReady ? 100.0f : 70.0f;
#else
  const float signalQuality =
      currentSensorReady && ps2.connected ? 100.0f : 70.0f;
#endif
  char heading[24] = "null";
  char roll[24] = "null";
  char pitch[24] = "null";
  char accelX[24] = "null";
  char accelY[24] = "null";
  char accelZ[24] = "null";
  if (latestImu.valid) {
    snprintf(heading, sizeof(heading), "%.2f", latestImu.headingDeg);
    snprintf(roll, sizeof(roll), "%.2f", latestImu.rollDeg);
    snprintf(pitch, sizeof(pitch), "%.2f", latestImu.pitchDeg);
    snprintf(accelX, sizeof(accelX), "%.3f", latestImu.accelXMps2);
    snprintf(accelY, sizeof(accelY), "%.3f", latestImu.accelYMps2);
    snprintf(accelZ, sizeof(accelZ), "%.3f", latestImu.accelZMps2);
  }

  Serial.printf(
      "{\"schema_version\":\"%s\",\"device_id\":\"%s\","
      "\"hardware_model_id\":\"%s\",\"sample_id\":\"%s-%lu\","
      "\"recorded_at\":null,\"sequence\":%lu,\"measurements\":{"
      "\"bus_voltage_v\":%.3f,\"current_ma\":%.2f,\"power_mw\":%.2f,"
      "\"pwm_percent\":%d,\"driver_enabled\":%s,\"motor_rpm\":%.2f,"
      "\"total_current_ma\":%.2f,\"rpm_left\":%.2f,\"rpm_right\":%.2f,"
      "\"rpm_rear\":%.2f,\"rpm_delta\":%.2f,\"pwm_left_percent\":%d,"
      "\"pwm_right_percent\":%d,\"pwm_rear_percent\":%d,"
      "\"pid_state\":\"%s\",\"ps2_connected\":%s,"
      "\"ps2_failsafe_active\":%s,\"ps2_last_packet_age_ms\":%lu,"
      "\"control_mode\":\"%s\",\"drive_armed\":%s,"
      "\"bno055_connected\":%s,\"imu_heading_deg\":%s,"
      "\"imu_roll_deg\":%s,\"imu_pitch_deg\":%s,"
      "\"imu_accel_x_mps2\":%s,\"imu_accel_y_mps2\":%s,"
      "\"imu_accel_z_mps2\":%s},\"quality\":{"
      "\"signal_quality_percent\":%.1f,\"source\":\"device\"}}\n",
      nexus::contract::v1::kSchemaVersion, deviceId.c_str(),
      NEXUS_HARDWARE_MODEL_ID, deviceId.c_str(),
      static_cast<unsigned long>(sequence), static_cast<unsigned long>(sequence),
      latestPower.busVoltageV, latestPower.currentMa, latestPower.powerMw,
      maxPwm, anyMotorEnabled() ? "true" : "false", averageRpm,
      latestPower.currentMa, motorRpm[0], motorRpm[1], motorRpm[2],
      maxRpm - minRpm, abs(motorCommandPercent[0]),
      abs(motorCommandPercent[1]), abs(motorCommandPercent[2]),
      balancePidActive ? "balance_pid" : "idle",
      ps2.connected ? "true" : "false",
      ps2FailsafeActive ? "true" : "false",
      static_cast<unsigned long>(packetAgeMs),
      controlReady ? "ps2_manual" : "failsafe",
      driveArmed ? "true" : "false", imuReady ? "true" : "false",
      heading, roll, pitch, accelX, accelY, accelZ, signalQuality);
}

void configurePins() {
  for (uint8_t index = 0; index < 3; ++index) {
    pinMode(kMotors[index].enablePin, OUTPUT);
    pinMode(kMotors[index].in1Pin, OUTPUT);
    pinMode(kMotors[index].in2Pin, OUTPUT);
    pinMode(kMotors[index].encoderAPin, INPUT_PULLUP);
    pinMode(kMotors[index].encoderBPin, INPUT_PULLUP);
    encoderLastState[index] =
        (digitalRead(kMotors[index].encoderAPin) == HIGH ? 0x02 : 0x00) |
        (digitalRead(kMotors[index].encoderBPin) == HIGH ? 0x01 : 0x00);
  }
  attachInterrupt(digitalPinToInterrupt(kMotors[0].encoderAPin), handleEncoder1,
                  CHANGE);
  attachInterrupt(digitalPinToInterrupt(kMotors[0].encoderBPin), handleEncoder1,
                  CHANGE);
  attachInterrupt(digitalPinToInterrupt(kMotors[1].encoderAPin), handleEncoder2,
                  CHANGE);
  attachInterrupt(digitalPinToInterrupt(kMotors[1].encoderBPin), handleEncoder2,
                  CHANGE);
  attachInterrupt(digitalPinToInterrupt(kMotors[2].encoderAPin), handleEncoder3,
                  CHANGE);
  attachInterrupt(digitalPinToInterrupt(kMotors[2].encoderBPin), handleEncoder3,
                  CHANGE);

  pinMode(NEXUS_PS2_DATA_PIN, INPUT_PULLUP);
  pinMode(NEXUS_PS2_CMD_PIN, OUTPUT);
  pinMode(NEXUS_PS2_ATT_PIN, OUTPUT);
  pinMode(NEXUS_PS2_CLK_PIN, OUTPUT);
  digitalWrite(NEXUS_PS2_CMD_PIN, HIGH);
  digitalWrite(NEXUS_PS2_ATT_PIN, HIGH);
  digitalWrite(NEXUS_PS2_CLK_PIN, HIGH);
  stopAllMotors();
}
}  // namespace

void setup() {
  Serial.begin(NEXUS_SERIAL_BAUD_RATE);
  delay(300);
  char chipSuffix[13];
  snprintf(chipSuffix, sizeof(chipSuffix), "%012llx",
           static_cast<unsigned long long>(ESP.getEfuseMac()));
  deviceId = String("nexus-") + NEXUS_CONTROLLER_BOARD_ID + "-" + chipSuffix;

  configurePins();
  analogWriteFrequency(1000);
  Wire.begin(kInaSdaPin, kInaSclPin);
  Serial.printf(
      "[NEXUS][INFO][SIGNAL_MONITOR_READY] I2C SDA=GPIO%d SCL=GPIO%d "
      "checked every sample; three encoder A/B pairs checked during motion\n",
      kInaSdaPin, kInaSclPin);
  Serial.printf(
      "[NEXUS][INFO][BOOT] device_id=%s controller=%s profile=%s drive=%s\n",
      deviceId.c_str(), NEXUS_CONTROLLER_MODEL, NEXUS_HARDWARE_PROFILE_ID,
      NEXUS_DRIVE_MODE);
  emitHardwareProfile();
  initializeCurrentSensor();
  initializeImu();
  configurePs2Receiver();
  const uint32_t now = millis();
  lastSensorReadMs = now;
  lastTelemetryMs = now;
  lastProfileHeartbeatMs = now;
  lastRpmWindowMs = now;
  Serial.println(
      "[NEXUS][INFO][SAFE_BOOT] All three PWM outputs are zero; keep sticks "
      "centered until PS2 analog mode and safe motor power are ready; manual "
      "control then arms automatically");
#ifdef NEXUS_PS2_DIAGNOSTIC
  Serial.println(
      "[NEXUS][INFO][PS2_TEST_READY] Move sticks and press buttons; all motor "
      "outputs are forced OFF in this diagnostic build");
#endif
}

void loop() {
  const uint32_t now = millis();
  servicePs2();

  if (!currentSensorReady && now - lastSensorInitAttemptMs >= kSensorRetryIntervalMs) {
    initializeCurrentSensor();
  }
  if (currentSensorReady && now - lastSensorReadMs >= kSensorReadIntervalMs) {
    lastSensorReadMs = now;
    readPowerMeasurement(latestPower, true);
    updatePowerSafety();
  }
  if (!imuReady && now - lastImuInitAttemptMs >= kImuRetryIntervalMs) {
    initializeImu();
  }
  if (imuReady && now - lastImuReadMs >= kImuReadIntervalMs) {
    lastImuReadMs = now;
    readImuMeasurement();
  }

  updateRpm();
  if (now - lastTelemetryMs >= kTelemetryIntervalMs) {
    lastTelemetryMs = now;
    emitTelemetry();
  }
  if (now - lastProfileHeartbeatMs >= kProfileHeartbeatMs) {
    lastProfileHeartbeatMs = now;
    emitHardwareProfile();
  }
  delay(1);
}
