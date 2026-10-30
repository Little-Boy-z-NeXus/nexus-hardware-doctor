export type WiringScope = "all" | "power" | "i2c" | "ps2" | "motor1" | "motor2" | "motor3";

export interface PlannedWire {
  id: string;
  scope: Exclude<WiringScope, "all">;
  from: string;
  fromPin: string;
  to: string;
  toPin: string;
  color: "red" | "black" | "green" | "yellow" | "blue" | "orange" | "purple" | "white" | "gray";
  note?: string;
}

const powerWires: PlannedWire[] = [
  { id: "p01", scope: "power", from: "Pin LiPo 3S", fromPin: "+", to: "Đế cầu chì 4 A", toPin: "IN", color: "red" },
  { id: "p02", scope: "power", from: "Đế cầu chì 4 A", fromPin: "OUT", to: "Relay 12 V", toPin: "COM", color: "red" },
  { id: "p03", scope: "power", from: "Relay 12 V", fromPin: "NO", to: "INA219 SEN0291", toPin: "IN+", color: "red" },
  { id: "p04", scope: "power", from: "INA219 SEN0291", fromPin: "IN−", to: "PCT MOTOR+", toPin: "P1", color: "red" },
  { id: "p05", scope: "power", from: "PCT MOTOR+", fromPin: "P2", to: "L298N #1", toPin: "+12V / VS", color: "red" },
  { id: "p06", scope: "power", from: "PCT MOTOR+", fromPin: "P3", to: "L298N #2", toPin: "+12V / VS", color: "red" },
  { id: "p08", scope: "power", from: "Pin LiPo 3S", fromPin: "−", to: "Điểm GND chung", toPin: "GND", color: "black" },
  { id: "p09", scope: "power", from: "Điểm GND chung", fromPin: "GND", to: "L298N #1", toPin: "GND", color: "black" },
  { id: "p10", scope: "power", from: "Điểm GND chung", fromPin: "GND", to: "L298N #2", toPin: "GND", color: "black" },
  { id: "p11", scope: "power", from: "Điểm GND chung", fromPin: "GND", to: "ESP32-S3", toPin: "GND", color: "black" },
];

const i2cWires: PlannedWire[] = [
  { id: "i01", scope: "i2c", from: "ESP32-S3", fromPin: "3V3", to: "INA219 SEN0291", toPin: "VCC", color: "purple" },
  { id: "i02", scope: "i2c", from: "Điểm GND chung", fromPin: "GND", to: "INA219 SEN0291", toPin: "GND", color: "black" },
  { id: "i03", scope: "i2c", from: "ESP32-S3", fromPin: "GPIO1 / SDA", to: "INA219 SEN0291", toPin: "SDA", color: "green", note: "Địa chỉ 0x40; A0/A1 OFF" },
  { id: "i04", scope: "i2c", from: "ESP32-S3", fromPin: "GPIO2 / SCL", to: "INA219 SEN0291", toPin: "SCL", color: "yellow", note: "Không đảo SDA/SCL" },
];

const ps2Wires: PlannedWire[] = [
  { id: "ps01", scope: "ps2", from: "ESP32-S3", fromPin: "3V3", to: "Đầu thu PS2", toPin: "VCC / đỏ", color: "red", note: "Bắt đầu ở 3,3 V; không đưa tín hiệu 5 V vào GPIO" },
  { id: "ps02", scope: "ps2", from: "Điểm GND chung", fromPin: "GND", to: "Đầu thu PS2", toPin: "GND / đen", color: "black" },
  { id: "ps03", scope: "ps2", from: "Đầu thu PS2", fromPin: "DATA / xanh dương", to: "ESP32-S3", toPin: "GPIO38", color: "blue", note: "Kéo lên 3V3 bằng điện trở 10 kΩ" },
  { id: "ps04", scope: "ps2", from: "ESP32-S3", fromPin: "GPIO39", to: "Đầu thu PS2", toPin: "CMD / xanh lá", color: "green" },
  { id: "ps05", scope: "ps2", from: "ESP32-S3", fromPin: "GPIO40", to: "Đầu thu PS2", toPin: "ATTN / cam", color: "orange" },
  { id: "ps06", scope: "ps2", from: "ESP32-S3", fromPin: "GPIO41", to: "Đầu thu PS2", toPin: "CLK / xám", color: "gray" },
];

const motorWires = (
  scope: "motor1" | "motor2" | "motor3",
  motor: string,
  driver: string,
  pins: { pwm: number; in1: number; in2: number; encoderA: number; encoderB: number },
  channel: { enable: string; in1: string; in2: string; outPlus: string; outMinus: string },
): PlannedWire[] => [
  { id: `${scope}-01`, scope, from: "ESP32-S3", fromPin: `GPIO${pins.pwm}`, to: driver, toPin: channel.enable, color: "blue", note: "PWM; tháo jumper EN" },
  { id: `${scope}-02`, scope, from: "ESP32-S3", fromPin: `GPIO${pins.in1}`, to: driver, toPin: channel.in1, color: "orange" },
  { id: `${scope}-03`, scope, from: "ESP32-S3", fromPin: `GPIO${pins.in2}`, to: driver, toPin: channel.in2, color: "purple" },
  { id: `${scope}-04`, scope, from: driver, fromPin: channel.outPlus, to: motor, toPin: "M+ / đỏ", color: "red" },
  { id: `${scope}-05`, scope, from: driver, fromPin: channel.outMinus, to: motor, toPin: "M− / trắng", color: "white" },
  { id: `${scope}-06`, scope, from: "ESP32-S3", fromPin: "3V3", to: motor, toPin: "Encoder VCC / xanh dương", color: "blue" },
  { id: `${scope}-07`, scope, from: "Điểm GND chung", fromPin: "GND", to: motor, toPin: "Encoder GND / đen", color: "black" },
  { id: `${scope}-08`, scope, from: motor, fromPin: "Encoder A / vàng", to: "ESP32-S3", toPin: `GPIO${pins.encoderA}`, color: "yellow" },
  { id: `${scope}-09`, scope, from: motor, fromPin: "Encoder B / xanh lá", to: "ESP32-S3", toPin: `GPIO${pins.encoderB}`, color: "green" },
  { id: `${scope}-10`, scope, from: "Tụ ceramic 100 nF", fromPin: "Chân 1", to: motor, toPin: "M+ ↔ M−", color: "white", note: "Hàn ngang hai cực motor nếu có" },
];

export const DUAL_MOTOR_ARCHITECTURE = {
  schemaVersion: "1.0.0",
  designId: "nexus-profile-esp32-s3-devkitc-ina219-dual-l298n-3wheel-ps2-v2",
  name: "NeXus three-wheel PS2 robot",
  controller: "ESP32-S3 DevKitC-compatible N16R8 44-pin",
  powerMonitor: "DFRobot Gravity INA219 SEN0291 · R010",
  driver: "2 × L298N dual H-bridge",
  motors: "3 × JGB37-520 12V Hall A/B",
  power: "Pin LiPo 3S · 11,1–12,6 V",
  i2c: [
    { name: "INA219 SEN0291", address: "0x40", purpose: "Điện áp, dòng và công suất tổng của ba motor", icon: "power" },
  ],
  expectedTelemetry: [
    "rpm_left", "rpm_right", "rpm_rear", "rpm_delta",
    "pwm_left_percent", "pwm_right_percent", "pwm_rear_percent",
    "ps2_connected", "ps2_failsafe_active", "bus_voltage_v", "total_current_ma",
  ],
  wires: [
    ...powerWires,
    ...i2cWires,
    ...ps2Wires,
    ...motorWires("motor1", "Motor 1 · trước trái", "L298N #1", { pwm: 12, in1: 13, in2: 14, encoderA: 16, encoderB: 17 }, { enable: "ENA", in1: "IN1", in2: "IN2", outPlus: "OUT1", outMinus: "OUT2" }),
    ...motorWires("motor2", "Motor 2 · trước phải", "L298N #1", { pwm: 15, in1: 18, in2: 21, encoderA: 4, encoderB: 5 }, { enable: "ENB", in1: "IN3", in2: "IN4", outPlus: "OUT3", outMinus: "OUT4" }),
    ...motorWires("motor3", "Motor 3 · bánh sau", "L298N #2", { pwm: 6, in1: 7, in2: 8, encoderA: 9, encoderB: 10 }, { enable: "ENA", in1: "IN1", in2: "IN2", outPlus: "OUT1", outMinus: "OUT2" }),
  ] satisfies PlannedWire[],
} as const;

export const WIRING_SCOPE_LABELS: Record<WiringScope, string> = {
  all: "Tất cả",
  power: "Nguồn & an toàn",
  i2c: "INA219 / I²C",
  ps2: "Tay cầm PS2",
  motor1: "Motor 1",
  motor2: "Motor 2",
  motor3: "Motor 3",
};

export const WIRE_COLOR_LABELS: Record<PlannedWire["color"], string> = {
  red: "Đỏ",
  black: "Đen",
  green: "Xanh lá",
  yellow: "Vàng",
  blue: "Xanh dương",
  orange: "Cam",
  purple: "Tím",
  white: "Trắng",
  gray: "Xám",
};
