import { AlertTriangle, Cable, CheckCircle2, ShieldCheck } from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";

import type {
  HardwareAsCodeProfile,
  HardwareProfileConnection,
} from "../realtime/HardwareMonitorContext";
import { useI18n } from "../i18n/I18nContext";

interface WiringGuideProps {
  profile: HardwareAsCodeProfile | null;
  selectedComponentId?: string;
  onSelectComponent: (componentId: string) => void;
}

interface WireColorPresentation {
  key: string;
  label: string;
  color: string;
  border: string;
  isExact: boolean;
}

type WireStyle = CSSProperties & {
  "--wire-color": string;
  "--wire-border": string;
};

const WIRE_COLORS: Record<string, Omit<WireColorPresentation, "key" | "isExact">> = {
  red: { label: "Red", color: "#cf4d47", border: "#a63d38" },
  black: { label: "Black", color: "#263640", border: "#14212a" },
  yellow: { label: "Yellow", color: "#e0ad2f", border: "#b88914" },
  green: { label: "Green", color: "#27906f", border: "#176d53" },
  blue: { label: "Blue", color: "#3d82b7", border: "#28658f" },
  white: { label: "White", color: "#ffffff", border: "#aebfc6" },
  orange: { label: "Orange", color: "#d67a32", border: "#ad5f24" },
  purple: { label: "Purple", color: "#7d64af", border: "#624b91" },
  violet: { label: "Violet", color: "#7d64af", border: "#624b91" },
  gray: { label: "Gray", color: "#8799a2", border: "#657780" },
  grey: { label: "Gray", color: "#8799a2", border: "#657780" },
  brown: { label: "Brown", color: "#8c6247", border: "#6e4933" },
};

const SIGNAL_LABELS: Record<string, string> = {
  power: "Power",
  ground: "GND",
  i2c: "I²C",
  digital: "Digital",
  pwm: "PWM",
  analog: "Analog",
  spi: "SPI",
  uart: "UART",
  usb: "USB",
};

const COMPONENT_TYPE_LABELS: Record<string, string> = {
  controller: "Controller",
  sensor: "Sensor",
  power_monitor: "Power monitor",
  driver: "Driver",
  motor_driver: "Motor driver",
  actuator: "Actuator",
  power: "Power",
  power_supply: "Power supply",
  compute: "Computer",
  communication: "Communication",
};

function wireColorPresentation(value: string | undefined, text: (english: string, vietnamese: string) => string): WireColorPresentation {
  const key = value?.trim().toLocaleLowerCase("en") ?? "";
  const canonical = WIRE_COLORS[key];
  const colorLabels: Record<string, string> = { red: "Đỏ", black: "Đen", yellow: "Vàng", green: "Xanh lá", blue: "Xanh dương", white: "Trắng", orange: "Cam", purple: "Tím", violet: "Tím", gray: "Xám", grey: "Xám", brown: "Nâu" };
  if (canonical) return { key, ...canonical, label: text(canonical.label, colorLabels[key] ?? canonical.label), isExact: true };

  if (/^#[0-9a-f]{6}$/i.test(key)) {
    return {
      key,
      label: text(`Custom ${key.toUpperCase()}`, `Tùy chỉnh ${key.toUpperCase()}`),
      color: key,
      border: "#71838c",
      isExact: true,
    };
  }

  return {
    key: key || "missing",
    label: text("Color not specified", "Chưa chốt màu"),
    color: "#c4d0d5",
    border: "#8fa1a9",
    isExact: false,
  };
}

function signalLabel(signalType: string) {
  return SIGNAL_LABELS[signalType] ?? signalType.toUpperCase();
}

export function WiringGuide({ profile, selectedComponentId, onSelectComponent }: WiringGuideProps) {
  const { text } = useI18n();
  const [scope, setScope] = useState<"selected" | "all">("selected");
  const componentById = useMemo(
    () => new Map(profile?.components.map((component) => [component.component_id, component]) ?? []),
    [profile],
  );
  const selectedComponent = selectedComponentId ? componentById.get(selectedComponentId) : undefined;
  const connections = profile?.connections ?? [];
  const visibleConnections = scope === "all" || !selectedComponentId
    ? connections
    : connections.filter(
        (connection) => connection.from.component_id === selectedComponentId
          || connection.to.component_id === selectedComponentId,
      );
  const exactColorCount = connections.filter(
    (connection) => wireColorPresentation(connection.wire_color, text).isExact,
  ).length;
  const incompleteColorCount = connections.length - exactColorCount;

  const endpoint = (connection: HardwareProfileConnection, side: "from" | "to") => {
    const target = connection[side];
    const component = componentById.get(target.component_id);
    const pin = component?.pins.find((item) => item.pin_id === target.pin_id);
    return {
      componentId: target.component_id,
      componentType: text(COMPONENT_TYPE_LABELS[component?.component_type ?? ""] ?? component?.component_type.replaceAll("_", " ") ?? "Component", ({ controller: "Bộ điều khiển", sensor: "Cảm biến", power_monitor: "Cảm biến nguồn", driver: "Driver", motor_driver: "Driver motor", actuator: "Cơ cấu chấp hành", power: "Nguồn", power_supply: "Nguồn", compute: "Máy tính", communication: "Giao tiếp" } as Record<string, string>)[component?.component_type ?? ""] ?? component?.component_type.replaceAll("_", " ") ?? "Linh kiện"),
      model: component?.model ?? target.component_id,
      pinId: target.pin_id,
      pinLabel: pin?.label ?? target.pin_id,
      pinMode: pin?.mode ?? text("mode not declared", "chưa khai báo mode"),
      logicVoltage: pin?.logic_voltage_v,
    };
  };

  return (
    <section className="card wiring-guide" aria-labelledby="wiring-guide-title" data-testid="wiring-guide">
      <div className="wiring-guide__header">
        <div>
          <p className="eyebrow">{text("Wiring", "Đấu dây")} · Hardware-as-code</p>
          <h2 id="wiring-guide-title">{text("Match every pin and wire color", "Nối đúng chân, đúng màu")}</h2>
          <p>
            {text("Every wire is read directly from the profile. Select a BOM component to see related wires, or show the complete graph for assembly and troubleshooting.", "Mỗi đường dây được đọc trực tiếp từ profile. Chọn linh kiện trong BOM để chỉ xem những dây liên quan, hoặc mở toàn bộ sơ đồ khi lắp ráp và dò lỗi.")}
          </p>
        </div>
        <span className={`status-pill status-pill--${incompleteColorCount ? "warning" : "healthy"}`}>
          {incompleteColorCount ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          {exactColorCount}/{connections.length} {text("colors specified", "màu đã chốt")}
        </span>
      </div>

      <div className="wiring-guide__toolbar">
        <div className="wiring-scope" role="group" aria-label={text("Wiring graph scope", "Phạm vi sơ đồ đấu dây")}>
          <button
            type="button"
            className={scope === "selected" ? "is-active" : ""}
            aria-pressed={scope === "selected"}
            onClick={() => setScope("selected")}
          >
            {text("Selected component", "Linh kiện đang chọn")}
          </button>
          <button
            type="button"
            className={scope === "all" ? "is-active" : ""}
            aria-pressed={scope === "all"}
            onClick={() => setScope("all")}
          >
            {text(`All ${connections.length} wires`, `Toàn bộ ${connections.length} dây`)}
          </button>
        </div>
        <p title={selectedComponent?.model}>
          {scope === "selected"
            ? text(`Filtered: ${selectedComponent?.model ?? "no component selected"}`, `Đang lọc: ${selectedComponent?.model ?? "chưa chọn linh kiện"}`)
            : `Profile ${profile?.schema_version ?? "--"}`}
        </p>
      </div>

      <div className="wiring-guide__safety" role="note">
        <ShieldCheck size={17} aria-hidden="true" />
        <p>
          <strong>{text("Disconnect 12 V and USB before connecting or removing wires.", "Ngắt nguồn 12 V và USB trước khi cắm hoặc rút dây.")}</strong>{" "}
          {text("Unspecified colors use a dashed line; update the profile to match the physical wire instead of guessing.", "Màu chưa chốt được vẽ nét đứt; hãy cập nhật profile theo đúng dây vật lý, không đoán màu.")}
        </p>
      </div>

      <ol className="wiring-list" aria-label={text("Wire list", "Danh sách các đường dây")}>
        {visibleConnections.map((connection) => {
          const from = endpoint(connection, "from");
          const to = endpoint(connection, "to");
          const wire = wireColorPresentation(connection.wire_color, text);
          const style: WireStyle = {
            "--wire-color": wire.color,
            "--wire-border": wire.border,
          };
          const absoluteIndex = connections.findIndex(
            (item) => item.connection_id === connection.connection_id,
          ) + 1;
          return (
            <li
              key={connection.connection_id}
              className={`wiring-row${wire.isExact ? "" : " wiring-row--incomplete"}`}
              data-connection-id={connection.connection_id}
              data-wire-color={wire.key}
            >
              <span className="wiring-row__number" aria-hidden="true">
                {String(absoluteIndex).padStart(2, "0")}
              </span>

              <button
                type="button"
                className={`wire-endpoint${from.componentId === selectedComponentId ? " is-selected" : ""}`}
                onClick={() => onSelectComponent(from.componentId)}
                aria-label={text(`Select ${from.model}, pin ${from.pinLabel}`, `Chọn ${from.model}, chân ${from.pinLabel}`)}
              >
                <small>{text("Endpoint A", "Đầu A")} · {from.componentType}</small>
                <span className="wire-endpoint__model" title={from.model}>{from.model}</span>
                <span className="wire-endpoint__pin">
                  <strong>{from.pinLabel}</strong>
                  <code>{from.pinId}</code>
                  <em>{from.logicVoltage == null ? from.pinMode : `${from.pinMode} · ${from.logicVoltage} V`}</em>
                </span>
              </button>

              <div
                className="wire-connection"
                style={style}
                aria-label={text(`${signalLabel(connection.signal_type)}, ${wire.label} wire`, `${signalLabel(connection.signal_type)}, dây ${wire.label}`)}
              >
                <span className="wire-connection__label">
                  <Cable size={14} aria-hidden="true" />
                  <strong>{wire.label}</strong>
                </span>
                <span className="wire-connection__line" aria-hidden="true" />
                <span className="wire-connection__meta">
                  <strong>{signalLabel(connection.signal_type)}</strong>
                  <code>{connection.connection_id}</code>
                </span>
              </div>

              <button
                type="button"
                className={`wire-endpoint${to.componentId === selectedComponentId ? " is-selected" : ""}`}
                onClick={() => onSelectComponent(to.componentId)}
                aria-label={text(`Select ${to.model}, pin ${to.pinLabel}`, `Chọn ${to.model}, chân ${to.pinLabel}`)}
              >
                <small>{text("Endpoint B", "Đầu B")} · {to.componentType}</small>
                <span className="wire-endpoint__model" title={to.model}>{to.model}</span>
                <span className="wire-endpoint__pin">
                  <strong>{to.pinLabel}</strong>
                  <code>{to.pinId}</code>
                  <em>{to.logicVoltage == null ? to.pinMode : `${to.pinMode} · ${to.logicVoltage} V`}</em>
                </span>
              </button>
            </li>
          );
        })}
        {visibleConnections.length === 0 && (
          <li className="wiring-list__empty">
            <Cable size={20} aria-hidden="true" />
            {text("No wires are declared for this component.", "Chưa có đường dây nào được khai báo cho linh kiện này.")}
          </li>
        )}
      </ol>

      <div className="wiring-guide__legend" aria-label={text("Motor wire color convention", "Quy ước màu dây motor trong profile")}>
        <span><i className="wire-legend wire-legend--red" />{text("Red: positive power / Motor+", "Đỏ: nguồn dương / Motor+")}</span>
        <span><i className="wire-legend wire-legend--black" />{text("Black: GND", "Đen: GND")}</span>
        <span><i className="wire-legend wire-legend--yellow" />{text("Yellow: Encoder A", "Vàng: Encoder A")}</span>
        <span><i className="wire-legend wire-legend--green" />{text("Green: Encoder B", "Xanh lá: Encoder B")}</span>
        <span><i className="wire-legend wire-legend--blue" />{text("Blue: Encoder VCC", "Xanh dương: Encoder VCC")}</span>
        <span><i className="wire-legend wire-legend--white" />{text("White: Motor−", "Trắng: Motor−")}</span>
      </div>
    </section>
  );
}
