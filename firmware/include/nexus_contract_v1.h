#pragma once

namespace nexus {
namespace contract {
namespace v1 {

inline constexpr char kSchemaVersion[] = "1.0.0";
inline constexpr char kHardwareModelId[] = "hardware_model_id";
inline constexpr char kSchemaVersionField[] = "schema_version";
inline constexpr char kDeviceId[] = "device_id";
inline constexpr char kSampleId[] = "sample_id";
inline constexpr char kRecordedAt[] = "recorded_at";
inline constexpr char kSequence[] = "sequence";
inline constexpr char kMeasurements[] = "measurements";
inline constexpr char kBusVoltageV[] = "bus_voltage_v";
inline constexpr char kCurrentMa[] = "current_ma";
inline constexpr char kPowerMw[] = "power_mw";
inline constexpr char kPwmPercent[] = "pwm_percent";
inline constexpr char kDriverEnabled[] = "driver_enabled";
inline constexpr char kMotorRpm[] = "motor_rpm";
inline constexpr char kQuality[] = "quality";
inline constexpr char kSignalQualityPercent[] = "signal_quality_percent";
inline constexpr char kSource[] = "source";

}  // namespace v1
}  // namespace contract
}  // namespace nexus
