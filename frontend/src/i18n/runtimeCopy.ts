import type { HardwareDiagnostic, SerialConnection } from "../realtime/HardwareMonitorContext";
import type { Language } from "./I18nContext";

interface DiagnosticCopy {
  title: string;
  message: string;
  action: string;
}

const ENGLISH_DIAGNOSTICS: Record<string, readonly [title: string, message: string, action: string]> = {
  FIRMWARE_PROFILE_MISMATCH: ["Firmware does not match the selected BOM", "The profile, hardware model, or sensor declared by firmware differs from the active Hardware-as-Code profile.", "Turn off motor power and flash firmware generated from the active profile."],
  HARDWARE_MODEL_MISMATCH: ["Firmware targets a different hardware model", "The board reported a hardware model that does not match the active MVP profile.", "Regenerate the configuration from the active profile and flash the matching firmware."],
  I2C_SDA_STUCK_LOW: ["SDA is stuck LOW", "SDA does not return HIGH while the I²C bus is idle, so sensor readings are not trustworthy.", "Turn off motor power; inspect SDA, shared GND, shorts, and the pull-up resistor, then reset the board."],
  I2C_SCL_STUCK_LOW: ["SCL is stuck LOW", "SCL does not return HIGH while the I²C bus is idle, so the controller cannot clock the sensor safely.", "Turn off motor power; inspect SCL, shared GND, shorts, and the pull-up resistor, then reset the board."],
  INA219_I2C_NO_ACK: ["INA219 does not acknowledge on I²C", "The configured sensor address did not return an ACK, so the sample was discarded.", "Turn off motor power and check INA219 VCC, GND, SDA, SCL, and address-selection pins."],
  INA226_I2C_NO_ACK: ["INA226 does not acknowledge on I²C", "The configured sensor address did not return an ACK, so the sample was discarded.", "Turn off motor power and check INA226 VCC, GND, SDA, SCL, and address-selection pins."],
  INA219_I2C_FAILURE: ["Cannot read INA219", "The controller could not read or configure the sensor; invalid samples are not sent to the UI.", "Turn off motor power, verify VCC, GND, SDA, and SCL against the profile, then reset the board."],
  INA226_I2C_FAILURE: ["Cannot read INA226", "The controller could not read or configure the sensor; invalid samples are not sent to the UI.", "Turn off motor power, verify VCC, GND, SDA, and SCL against the profile, then reset the board."],
  INA219_SIGNAL_INVALID: ["INA219 signal is inconsistent", "The current register disagrees with the independent shunt calculation.", "Stop the motor, reseat SDA/SCL and GND, separate signal wires from motor outputs, and verify the shunt value."],
  INA226_SIGNAL_INCONSISTENT: ["INA226 signal is inconsistent", "The current register disagrees with the independent shunt calculation.", "Stop the motor, reseat SDA/SCL and GND, separate signal wires from motor outputs, and verify the shunt value."],
  INA226_ID_MISMATCH: ["Installed sensor does not match the hardware profile", "The I²C identity is not the INA226 expected by the active profile.", "Turn off power, verify the physical IC and address, then reset the board."],
  INA219_CONFIGURATION_MISMATCH: ["INA219 configuration does not match the profile", "The configuration or calibration registers do not match the selected sensor profile.", "Turn off motor power, verify the INA219 model and address straps, then reset the board."],
  ENCODER_CHANNEL_A_MISSING: ["Encoder A signal is missing", "Encoder B has edges, but channel A has no signal while the motor is running.", "Turn off motor power and verify encoder A, VCC, GND, and wire colors against the hardware profile."],
  ENCODER_CHANNEL_B_MISSING: ["Encoder B signal is missing", "Encoder A has edges, but channel B has no signal while the motor is running.", "Turn off motor power and verify encoder B, VCC, GND, and wire colors against the hardware profile."],
  ENCODER_SIGNAL_MISSING: ["No encoder A/B pulses detected", "The motor driver was commanded to run, but neither encoder channel produced signal edges.", "Turn off motor power; verify encoder VCC, GND, A, and B and confirm the motor shaft really turns."],
  ENCODER_SIGNAL_INVALID: ["Encoder A/B signal is noisy", "Too many invalid A/B transitions were detected while the motor was running.", "Turn off motor power, reseat A/B, separate encoder wires from motor power wires, and repeat a short test."],
  MOTOR_SUPPLY_NOT_DETECTED: ["Motor supply not detected", "The power monitor reads approximately 0 V. This is normal only when motor power is switched off.", "If power is on, verify the supply path, sensor power terminals, driver input, and shared GND."],
  INA219_REFERENCE_INVALID: ["INA219 reading is not physically plausible", "Bus voltage is near zero while measured current is still significant.", "Check shared GND and the IN+/IN− path; load current must pass through the sensor before the driver."],
  INA226_REFERENCE_INVALID: ["INA226 reading is not physically plausible", "Bus voltage is near zero while measured current is still significant.", "Check shared GND and the VBUS/VIN+/VIN− path; load current must pass through the sensor before the driver."],
  INA219_POLARITY_REVERSED: ["INA219 power path polarity is reversed", "Measured current direction is opposite to the expected motor supply direction.", "Turn off power and verify IN+ is supply-side and IN− is load-side."],
  INA226_POLARITY_REVERSED: ["INA226 power path polarity is reversed", "Measured current direction is opposite to the expected motor supply direction.", "Turn off power and verify VIN+ is supply-side, VIN− is load-side, and VBUS senses the load side."],
  MOTOR_UNDERVOLTAGE: ["Motor supply voltage is too low", "Measured voltage is below the safe threshold in the active profile.", "Disable the driver and use the power source specified by the active profile."],
  MOTOR_OVERCURRENT: ["Motor current exceeds the safety limit", "Measured current is above the maximum allowed by the active profile.", "Stop the motor immediately and inspect for a stalled shaft, shorted output, or undersized driver."],
  PWM_SAFETY_LIMIT_EXCEEDED: ["PWM exceeds the safety limit", "Commanded PWM is above the maximum allowed by the active profile.", "Stop the motor and lower the command to the configured safe limit."],
  TELEMETRY_INVALID: ["Invalid telemetry packet", "The backend rejected a malformed packet so the UI does not display unsafe measurements.", "Reset the controller, verify the sensor, and flash the latest matching firmware."],
  TELEMETRY_SEQUENCE_GAP: ["Some telemetry packets were lost", "The telemetry sequence counter skipped one or more values.", "Check the USB cable and close other serial monitors."],
  TELEMETRY_TIMEOUT: ["Telemetry timed out", "No fresh telemetry packet arrived within the expected interval.", "Check board power, USB, the selected COM port, and whether another serial monitor owns the port."],
  SERIAL_DEVICE_NOT_FOUND: ["ESP32 serial device not found", "The backend could not find the configured USB serial device.", "Connect the ESP32, verify the COM port, and restart the backend launcher."],
  SERIAL_PORT_BUSY: ["Serial port is busy", "Another application is using the ESP32 COM port.", "Close PlatformIO Serial Monitor and other terminals, then reconnect."],
  SERIAL_PORT_ERROR: ["Serial port error", "The backend lost access to the ESP32 serial port.", "Reconnect USB, verify the COM port, and use Reconnect in the UI."],
};

export function localizeDiagnostic(item: HardwareDiagnostic, language: Language): DiagnosticCopy {
  if (language === "vi") return { title: item.title, message: item.message, action: item.action };
  const english = ENGLISH_DIAGNOSTICS[item.code];
  if (english) return { title: english[0], message: english[1], action: english[2] };
  return {
    title: item.code.replaceAll("_", " ").toLocaleLowerCase("en-US").replace(/^./, (letter) => letter.toUpperCase()),
    message: "The hardware monitor reported a diagnostic condition. Use its code to correlate it with the firmware log.",
    action: "Put the system in a safe state and inspect the Hardware-as-Code profile before changing wiring or firmware.",
  };
}

export function localizeConnectionMessage(connection: SerialConnection | undefined, language: Language): string {
  if (language === "vi" && connection?.message) return connection.message;
  if (!connection) return language === "vi" ? "Đang tải trạng thái runtime từ backend." : "Loading runtime status from the backend.";
  if (connection.status === "connected") return language === "vi" ? connection.message : `Receiving real-time telemetry from ${connection.port ?? "the connected controller"}.`;
  if (language === "vi") return connection.message;
  if (connection.status === "searching") return "Searching for the configured hardware controller.";
  if (connection.status === "disabled") return "Live serial monitoring is disabled in the backend.";
  if (connection.status === "error") return "The backend encountered a serial connection error.";
  return "The hardware controller is not connected.";
}
