export type WiringScope = "all" | "power" | "i2c" | "left" | "right";

export interface PlannedWire {
  id: string;
  scope: Exclude<WiringScope, "all">;
  from: string;
  fromPin: string;
  to: string;
  toPin: string;
  color: "red" | "black" | "green" | "yellow" | "blue" | "orange" | "purple" | "white";
  note?: string;
}

const powerWires: PlannedWire[] = [
  ["p01", "Pin LiPo 3S", "+", "Đế cầu chì 1,5 A", "IN", "red"],
  ["p02", "Đế cầu chì 1,5 A", "OUT", "Công tắc nguồn", "IN", "red"],
  ["p03", "Công tắc nguồn", "OUT", "Nút ngắt lỗi NC", "IN", "red"],
  ["p04", "Nút ngắt lỗi NC", "OUT", "INA226", "VIN+", "red"],
  ["p05", "INA226", "VIN−", "L298N", "+12V / VS", "red"],
  ["p06", "INA226", "VIN−", "INA226", "VBS", "red", "Jumper đo điện áp bus"],
  ["p07", "Pin LiPo 3S", "−", "Điểm GND sao", "GND", "black"],
  ["p08", "Điểm GND sao", "GND", "L298N", "GND", "black"],
  ["p09", "Điểm GND sao", "GND", "ESP32-S3", "GND", "black"],
  ["p10", "Tụ 470–1000 µF", "+", "L298N", "+12V / VS", "red"],
  ["p11", "Tụ 470–1000 µF", "−", "L298N", "GND", "black"],
].map(([id, from, fromPin, to, toPin, color, note]) => ({
  id, scope: "power", from, fromPin, to, toPin, color, note,
} as PlannedWire));

const i2cDevices = [
  { id: "ina", name: "INA226", address: "0x40" },
  { id: "bme", name: "BME680", address: "0x76 / 0x77" },
  { id: "bno", name: "BNO055", address: "0x29 / 0x28" },
];

const i2cWires: PlannedWire[] = i2cDevices.flatMap((device) => [
  {
    id: `i2c-${device.id}-vcc`, scope: "i2c", from: "ESP32-S3", fromPin: "3V3",
    to: device.name, toPin: "VCC", color: "red", note: `Địa chỉ ${device.address}`,
  },
  {
    id: `i2c-${device.id}-gnd`, scope: "i2c", from: "Điểm GND sao", fromPin: "GND",
    to: device.name, toPin: "GND", color: "black",
  },
  {
    id: `i2c-${device.id}-sda`, scope: "i2c", from: "ESP32-S3", fromPin: "GPIO1 / SDA",
    to: device.name, toPin: "SDA", color: "green",
  },
  {
    id: `i2c-${device.id}-scl`, scope: "i2c", from: "ESP32-S3", fromPin: "GPIO2 / SCL",
    to: device.name, toPin: "SCL", color: "yellow",
  },
]);

const motorWires = (
  side: "left" | "right",
  pins: { pwm: number; in1: number; in2: number; encoderA: number; encoderB: number },
  channel: { enable: string; in1: string; in2: string; outPlus: string; outMinus: string },
): PlannedWire[] => {
  const label = side === "left" ? "Motor trái" : "Motor phải";
  const prefix = side === "left" ? "l" : "r";
  return [
    { id: `${prefix}01`, scope: side, from: "ESP32-S3", fromPin: `GPIO${pins.pwm}`, to: "L298N", toPin: channel.enable, color: "blue", note: "PWM; tháo jumper EN" },
    { id: `${prefix}02`, scope: side, from: "ESP32-S3", fromPin: `GPIO${pins.in1}`, to: "L298N", toPin: channel.in1, color: "orange" },
    { id: `${prefix}03`, scope: side, from: "ESP32-S3", fromPin: `GPIO${pins.in2}`, to: "L298N", toPin: channel.in2, color: "purple" },
    { id: `${prefix}04`, scope: side, from: "L298N", fromPin: channel.outPlus, to: label, toPin: "M+ / đỏ", color: "red" },
    { id: `${prefix}05`, scope: side, from: "L298N", fromPin: channel.outMinus, to: label, toPin: "M− / trắng", color: "white" },
    { id: `${prefix}06`, scope: side, from: "ESP32-S3", fromPin: "3V3", to: label, toPin: "Encoder VCC / xanh dương", color: "blue" },
    { id: `${prefix}07`, scope: side, from: "Điểm GND sao", fromPin: "GND", to: label, toPin: "Encoder GND / đen", color: "black" },
    { id: `${prefix}08`, scope: side, from: label, fromPin: "Encoder A / vàng", to: "ESP32-S3", toPin: `GPIO${pins.encoderA}`, color: "yellow" },
    { id: `${prefix}09`, scope: side, from: label, fromPin: "Encoder B / xanh lá", to: "ESP32-S3", toPin: `GPIO${pins.encoderB}`, color: "green" },
    { id: `${prefix}10`, scope: side, from: "Tụ ceramic 100 nF", fromPin: "Chân 1", to: label, toPin: "M+ ↔ M−", color: "white", note: "Hàn trực tiếp ngang hai cực motor" },
  ];
};

export const DUAL_MOTOR_ARCHITECTURE = {
  schemaVersion: "1.0.0-draft",
  designId: "nexus-dual-motor-pid-robot-v1",
  name: "NeXus dual-motor PID robot",
  controller: "GOOUUU Tech ESP32-S3-N16R8",
  powerMonitor: "INA226 R100 0.1 Ω",
  driver: "L298N dual H-bridge",
  motors: "2 × JGB37-520 12V Hall A/B",
  power: "Pin LiPo 3S · 11,1–12,6 V",
  i2c: [
    { name: "INA226", address: "0x40", purpose: "Điện áp, dòng và công suất tổng của hai motor", icon: "power" },
    { name: "BME680", address: "0x76 / 0x77", purpose: "Nhiệt độ, độ ẩm, áp suất và chất lượng khí", icon: "environment" },
    { name: "BNO055", address: "0x29 / 0x28", purpose: "Rung, nghiêng và tốc độ quay thân xe", icon: "motion" },
  ],
  expectedTelemetry: [
    "rpm_left", "rpm_right", "rpm_delta", "pwm_left_percent", "pwm_right_percent",
    "pid_state", "bus_voltage_v", "total_current_ma", "yaw_rate_dps",
  ],
  wires: [
    ...powerWires,
    ...i2cWires,
    ...motorWires("left", { pwm: 12, in1: 13, in2: 14, encoderA: 16, encoderB: 17 }, { enable: "ENA", in1: "IN1", in2: "IN2", outPlus: "OUT1", outMinus: "OUT2" }),
    ...motorWires("right", { pwm: 4, in1: 5, in2: 6, encoderA: 7, encoderB: 8 }, { enable: "ENB", in1: "IN3", in2: "IN4", outPlus: "OUT3", outMinus: "OUT4" }),
  ] satisfies PlannedWire[],
} as const;

export const WIRING_SCOPE_LABELS: Record<WiringScope, string> = {
  all: "Tất cả",
  power: "Nguồn & an toàn",
  i2c: "Bus I²C",
  left: "Motor trái",
  right: "Motor phải",
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
};
