"""Generate editable English diagrams.net diagrams for the active INA219 profile."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


OUT = Path(__file__).resolve().parent
NAVY = "#123044"
INK = "#203847"
MUTED = "#526979"
LINE = "#B8CCD5"
RED = "#D94747"
BLUE = "#2777BF"
TEAL = "#098B7D"
ORANGE = "#C67A22"
PURPLE = "#8458B8"
GREEN = "#32835B"
BLACK = "#384650"
BG = "#F6F9FB"


class Diagram:
    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.vertices: list[ET.Element] = []
        self.backgrounds: list[ET.Element] = []
        self.edges: list[ET.Element] = []
        self.n = 0

    def ident(self) -> str:
        self.n += 1
        return f"n{self.n}"

    def box(self, x, y, w, h, value="", *, fill="white", stroke=LINE,
            font=20, color=INK, bold=False, align="center", radius=True,
            dashed=False, shape="rectangle", behind=False):
        style = (
            f"shape={shape};rounded={1 if radius else 0};arcSize=12;"
            f"whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
            f"strokeWidth=2;fontColor={color};fontSize={font};"
            f"fontFamily=Arial;fontStyle={1 if bold else 0};align={align};"
            f"verticalAlign=middle;spacingLeft=12;spacingRight=12;"
            f"dashed={1 if dashed else 0};"
        )
        cell = ET.Element("mxCell", {"id": self.ident(), "value": value,
                                     "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y),
                                           "width": str(w), "height": str(h), "as": "geometry"})
        (self.backgrounds if behind else self.vertices).append(cell)
        return cell

    def text(self, x, y, w, h, value, *, font=20, color=INK, bold=False,
             align="left"):
        return self.box(x, y, w, h, value, fill="none", stroke="none",
                        font=font, color=color, bold=bold, align=align, radius=False)

    def wire(self, x1, y1, x2, y2, *, color=BLUE, width=3, arrow=False,
             dashed=False, bends=()):
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                 f"jettySize=auto;html=1;strokeColor={color};strokeWidth={width};"
                 f"dashed={1 if dashed else 0};endArrow={'block' if arrow else 'none'};"
                 "endFill=1;")
        cell = ET.Element("mxCell", {"id": self.ident(), "value": "",
                                     "style": style, "edge": "1", "parent": "1"})
        geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(geo, "mxPoint", {"x": str(x1), "y": str(y1), "as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", {"x": str(x2), "y": str(y2), "as": "targetPoint"})
        if bends:
            arr = ET.SubElement(geo, "Array", {"as": "points"})
            for x, y in bends:
                ET.SubElement(arr, "mxPoint", {"x": str(x), "y": str(y)})
        self.edges.append(cell)

    def header(self, kicker, title, subtitle):
        self.box(45, 35, self.width - 90, 145, fill=NAVY, stroke=NAVY)
        self.text(85, 53, self.width - 170, 30, kicker.upper(), font=17,
                  color="#8EDDD1", bold=True)
        self.text(85, 83, self.width - 170, 57, title, font=39,
                  color="white", bold=True)
        self.text(87, 139, self.width - 174, 32, subtitle, font=18,
                  color="#D8E9EF")

    def footer(self, note):
        self.text(65, self.height - 72, self.width - 130, 42, note, font=16,
                  color=MUTED)

    def save(self, filename):
        mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "type": "device"})
        diagram = ET.SubElement(mxfile, "diagram", {"id": filename.replace(".", "-"),
                                                 "name": self.name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": str(self.width), "dy": str(self.height), "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1",
            "pageWidth": str(self.width), "pageHeight": str(self.height),
            "background": BG,
        })
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        root.extend(self.backgrounds)
        root.extend(self.edges)
        root.extend(self.vertices)
        path = OUT / filename
        ET.ElementTree(mxfile).write(path, encoding="utf-8", xml_declaration=True)
        return path


def power():
    d = Diagram("01 Power and safety wiring", 2300, 1230)
    d.header("NeXus / Wiring 01 of 03", "Power, protection and distribution",
             "Active profile: ESP32-S3 DevKitC N16R8 + DFRobot INA219 SEN0291 + two L298N modules")
    d.text(90, 215, 650, 35, "12 V MOTOR PATH · HIGH-SIDE CURRENT SENSE", font=22,
           color=RED, bold=True)
    cards = [
        (90, 290, 250, "3S LiPo", "11.1–12.6 V\nXT60 positive"),
        (385, 290, 200, "4 A fuse", "In series with +"),
        (630, 290, 250, "+12 V splitter", "Relay COM\nBuck input branch"),
        (925, 290, 240, "12 V relay", "COM → NO\nNC unused"),
        (1210, 290, 300, "INA219 SEN0291", "IN+ → IN−\nHigh-side, ±8 A"),
        (1555, 290, 245, "MOTOR+ bus", "PCT-213\nSplit after IN−"),
        (1845, 290, 340, "L298N #1 and #2", "VS / +12 V inputs\nM1 · M2 · M3"),
    ]
    for x, y, w, title, desc in cards:
        d.box(x, y, w, 140, fill="#FFF2F1", stroke="#E6A3A0")
        d.text(x + 15, y + 16, w - 30, 34, title, font=23, bold=True, align="center")
        d.text(x + 15, y + 57, w - 30, 68, desc, font=17, color=MUTED, align="center")
    for a, b in zip(cards, cards[1:]):
        d.wire(a[0] + a[2], 360, b[0], 360, color=RED, width=5, arrow=True)
    d.text(1190, 455, 390, 34, "IN− is NOT ground.", font=20, color=RED, bold=True)

    d.text(90, 545, 700, 35, "5 V LOGIC SUPPLY · SEPARATE FROM MOTOR BUS", font=22,
           color=PURPLE, bold=True)
    d.box(630, 620, 265, 145, "5.0 V buck\n3 A rated\nIN+ from fused splitter", fill="#F4EEFC", stroke="#BFA6D9", font=20)
    d.box(1090, 620, 300, 145, "Dual USB output\n5 V measured before use", fill="#F4EEFC", stroke="#BFA6D9", font=20)
    d.box(1530, 600, 330, 85, "USB #1 → ESP32 UART/COM", fill="#EDF5FC", stroke="#A3C8E4", font=18)
    d.box(1530, 705, 330, 85, "USB #2 → 5 V splitter", fill="#F4EEFC", stroke="#BFA6D9", font=18)
    d.box(1930, 705, 255, 85, "L298N #1/#2 5 V", fill="#F4EEFC", stroke="#BFA6D9", font=18)
    d.wire(755, 430, 755, 620, color=RED, width=4)
    d.wire(895, 690, 1090, 690, color=PURPLE, width=4, arrow=True)
    d.wire(1390, 690, 1460, 690, color=PURPLE, width=4)
    d.wire(1460, 642, 1460, 748, color=PURPLE, width=4)
    d.wire(1460, 642, 1530, 642, color=PURPLE, width=4, arrow=True)
    d.wire(1460, 748, 1530, 748, color=PURPLE, width=4, arrow=True)
    d.wire(1860, 748, 1930, 748, color=PURPLE, width=4, arrow=True)
    d.text(1900, 610, 285, 60, "Remove the 5V-EN\njumper on both drivers.", font=17, color=PURPLE)

    d.text(90, 855, 570, 35, "RELAY CONTROL · LOW-TRIGGER INPUT", font=22,
           color=ORANGE, bold=True)
    relays = [(90, 922, 355, "Relay DC+ → fused +12 V\nRelay DC− → GND"),
              (615, 922, 310, "Relay IN"),
              (1090, 922, 310, "SW1 ON/OFF"),
              (1565, 922, 310, "E-STOP NC"),
              (2040, 922, 150, "GND")]
    for x, y, w, label in relays:
        d.box(x, y, w, 90, label, fill="#FFF4E8", stroke="#E5BE92", font=19)
    for a, b in zip(relays[1:], relays[2:]):
        d.wire(a[0] + a[2], 967, b[0], 967, color=ORANGE, width=4)
    d.box(90, 1060, 2100, 65,
          "COMMON GND NET  ·  Battery −  ·  relay DC−  ·  buck IN−  ·  INA219 GND terminal  ·  both L298N GND  ·  ESP32/PS2/encoder signal GND",
          fill="#EAF0F4", stroke="#9AABB6", font=18, color=BLACK)
    d.footer("Do not connect INA219 IN− to GND. Never feed 3S LiPo into the ESP32 5 V pin or expansion-board DC jack. Do not use PC USB and buck USB at the same time.")
    return d.save("01-power-wiring.drawio")


def signal():
    d = Diagram("02 Controller and signal wiring", 2100, 1940)
    d.header("NeXus / Wiring 02 of 03", "ESP32-S3 signal wiring",
             "One row per physical wire · GPIO numbers match the active v2 hardware profile")
    d.box(90, 220, 595, 80, "ESP32-S3 DevKitC · 44-pin expansion", fill="#EAF3FC",
          stroke="#9AC6E8", font=25, bold=True)
    d.box(1320, 220, 690, 80, "Connected device / pin", fill="#EAF3FC",
          stroke="#9AC6E8", font=25, bold=True)
    groups = [
        ("INA219 SEN0291 · 3.3 V I²C", [
            ("3V3", "INA219 VCC", PURPLE), ("GND", "INA219 GND", BLACK),
            ("GPIO1 · SDA", "INA219 SDA · I²C 0x40", BLUE),
            ("GPIO2 · SCL", "INA219 SCL · I²C 0x40", TEAL)]),
        ("PS2 WIRELESS RECEIVER · 3.3 V LOGIC", [
            ("3V3", "PS2 VCC (red)", PURPLE), ("GND", "PS2 GND (black)", BLACK),
            ("GPIO38 · DATA", "PS2 DATA (blue)", BLUE),
            ("GPIO39 · CMD", "PS2 CMD (green)", GREEN),
            ("GPIO40 · ATTN", "PS2 ATTN (orange)", ORANGE),
            ("GPIO41 · CLK", "PS2 CLK (gray)", MUTED)]),
        ("L298N #1 · FRONT-LEFT AND FRONT-RIGHT", [
            ("GPIO12 · PWM M1", "L298N #1 ENA", ORANGE),
            ("GPIO13 · DIR M1", "L298N #1 IN1", BLUE),
            ("GPIO11 · DIR M1", "L298N #1 IN2", BLUE),
            ("GPIO15 · PWM M2", "L298N #1 ENB", ORANGE),
            ("GPIO18 · DIR M2", "L298N #1 IN3", BLUE),
            ("GPIO21 · DIR M2", "L298N #1 IN4", BLUE)]),
        ("L298N #2 · REAR WHEEL", [
            ("GPIO6 · PWM M3", "L298N #2 ENA", ORANGE),
            ("GPIO7 · DIR M3", "L298N #2 IN1", BLUE),
            ("GPIO8 · DIR M3", "L298N #2 IN2", BLUE)]),
    ]
    y = 335
    for title, rows in groups:
        d.box(90, y, 1920, 50, title, fill=NAVY, stroke=NAVY,
              font=20, color="white", bold=True, align="left")
        y += 66
        for left, right, color in rows:
            d.box(90, y, 595, 48, left, fill="white", stroke=LINE,
                  font=19, bold=True, align="left", radius=False)
            d.box(1320, y, 690, 48, right, fill="white", stroke=LINE,
                  font=19, bold=True, align="left", radius=False)
            d.wire(685, y + 24, 1320, y + 24, color=color, width=3)
            y += 57
        y += 23
    d.box(90, 1780, 1920, 65,
          "Driver power: VS from the INA219 MOTOR+ bus, 5 V from the buck logic bus, GND to common ground. L298N #2 channel B is unused.",
          fill="#FFF4E8", stroke="#E5BE92", font=18, color=INK)
    d.footer("PS2 ACK and VIBR are not connected. Verify expansion-board V rail is 3.3 V before attaching the INA219, receiver or encoders.")
    return d.save("02-signal-wiring.drawio")


def motors():
    d = Diagram("03 Motor and encoder wiring", 2100, 1680)
    d.header("NeXus / Wiring 03 of 03", "Motor outputs and Hall encoders",
             "Three isolated wheel groups · no crossed conductors · M1 front-left, M2 front-right, M3 rear")
    groups = [
        ("M1 · FRONT-LEFT", [
            ("L298N #1 OUT1", "M1 motor+ · red", RED),
            ("L298N #1 OUT2", "M1 motor− · white", MUTED),
            ("3V3 SIGNAL bus", "M1 encoder VCC · blue", PURPLE),
            ("GND SIGNAL bus", "M1 encoder GND · black", BLACK),
            ("M1 encoder A · yellow", "ESP32 GPIO16", ORANGE),
            ("M1 encoder B · green", "ESP32 GPIO17", GREEN)]),
        ("M2 · FRONT-RIGHT", [
            ("L298N #1 OUT3", "M2 motor+ · red", RED),
            ("L298N #1 OUT4", "M2 motor− · white", MUTED),
            ("3V3 SIGNAL bus", "M2 encoder VCC · blue", PURPLE),
            ("GND SIGNAL bus", "M2 encoder GND · black", BLACK),
            ("M2 encoder A · yellow", "ESP32 GPIO4", ORANGE),
            ("M2 encoder B · green", "ESP32 GPIO5", GREEN)]),
        ("M3 · REAR", [
            ("L298N #2 OUT1", "M3 motor+ · red", RED),
            ("L298N #2 OUT2", "M3 motor− · white", MUTED),
            ("3V3 SIGNAL bus", "M3 encoder VCC · blue", PURPLE),
            ("GND SIGNAL bus", "M3 encoder GND · black", BLACK),
            ("M3 encoder A · yellow", "ESP32 GPIO9", ORANGE),
            ("M3 encoder B · green", "ESP32 GPIO10", GREEN)]),
    ]
    y = 235
    for title, rows in groups:
        d.box(90, y, 1920, 48, title, fill=NAVY, stroke=NAVY,
              font=20, color="white", bold=True, align="left")
        y += 58
        for left, right, color in rows:
            d.box(90, y, 590, 43, left, fill="white", stroke=LINE,
                  font=18, bold=True, align="left", radius=False)
            d.box(1320, y, 690, 43, right, fill="white", stroke=LINE,
                  font=18, bold=True, align="left", radius=False)
            d.wire(680, y + 22, 1320, y + 22, color=color, width=3)
            y += 51
        y += 37
    d.box(90, 1470, 1920, 65,
          "Keep Hall A/B leads with their encoder GND return. Motor leads are driver outputs; do not connect them to ESP32 GPIO."
          " 100 nF noise suppression at each motor is documented in the wiring guide.",
          fill="#FFF4E8", stroke="#E5BE92", font=17)
    d.footer("The left and right labels are endpoints of the same wire; wire color follows the physical lead when specified.")
    return d.save("03-motor-encoder-wiring.drawio")


def system_design():
    d = Diagram("System design", 2300, 1240)
    d.header("NeXus / Runtime flow", "System design · observe → diagnose → verify",
             "Grounded physical evidence enters a bounded AI workflow; safety decisions remain deterministic")
    stages = [
        (90, "PHYSICAL RIG", "ESP32-S3 + INA219\nPS2 + 3 motors", "#E7F5F1", TEAL),
        (470, "TELEMETRY", "Firmware v1 envelopes\nProfile ID + sample ID", "#EAF3FC", BLUE),
        (850, "VALIDATE + STORE", "FastAPI · schema/BOM checks\nSQLite · event trace", "#EAF3FC", BLUE),
        (1230, "AI DIAGNOSIS", "Nemotron-3-Ultra\non Nebius Token Factory", "#F2EEFA", PURPLE),
        (1610, "POLICY GATE", "Read-only tool allowlist\nDefault-deny decisions", "#FFF2E6", ORANGE),
        (1990, "VERIFY", "Fresh observations\nBefore/after evidence", "#E7F5F1", GREEN),
    ]
    for x, title, body, fill, stroke in stages:
        d.box(x, 390, 310, 250, fill=fill, stroke=stroke)
        d.box(x + 18, 410, 70, 48, str(stages.index((x,title,body,fill,stroke))+1).zfill(2),
              fill=stroke, stroke=stroke, font=19, color="white", bold=True)
        d.text(x + 18, 475, 274, 42, title, font=22, bold=True)
        d.text(x + 18, 535, 274, 75, body, font=18, color=MUTED)
    for left, right in zip(stages, stages[1:]):
        d.wire(left[0] + 310, 510, right[0], 510, color=TEAL, width=4, arrow=True)
    d.box(475, 225, 690, 92,
          "VERSIONED HARDWARE-AS-CODE PROFILE\nPins · wiring · electrical limits · active model identity",
          fill="#EFF8F6", stroke=TEAL, font=20, bold=True)
    d.wire(680, 317, 680, 390, color=TEAL, width=3, dashed=True, arrow=True)
    d.wire(1005, 317, 1005, 390, color=TEAL, width=3, dashed=True, arrow=True)
    d.box(90, 750, 500, 150, "USER / TECHNICIAN\nSymptom, supervised inspection, approval",
          fill="#F2F5F7", stroke=LINE, font=21)
    d.box(720, 750, 870, 150,
          "REACT + TYPESCRIPT FRONTEND\nDashboard · wiring graph · AI Doctor · diagnosis timeline",
          fill="#EAF3FC", stroke=BLUE, font=22)
    d.box(1720, 750, 580, 150,
          "EVIDENCE RECORD\nTrace ID · model metadata · policy outcome",
          fill="#EFF8F6", stroke=GREEN, font=21)
    d.wire(590, 825, 720, 825, color=BLUE, width=4, arrow=True)
    d.wire(1155, 640, 1155, 750, color=BLUE, width=4, arrow=True)
    d.wire(2145, 640, 2145, 750, color=GREEN, width=4, arrow=True)
    d.wire(1720, 825, 1590, 825, color=GREEN, width=4, arrow=True)
    d.box(90, 990, 2110, 115,
          "CONTROL BOUNDARY  ·  Nemotron returns hypotheses and proposed next reads. Local validation and policy decide which read-only tool can run. "
          "Any physical repair or actuation remains under human supervision and separate safety gates.",
          fill="#FFF8EB", stroke="#E4C994", font=19, align="left")
    d.footer("Architecture view for the current INA219 adapter. A replay UI session is labeled separately and is not live physical evidence.")
    return d.save("04-system-design.drawio")


def architecture():
    d = Diagram("System architecture", 2300, 1300)
    d.header("NeXus / Deployment boundaries", "System architecture · edge / local / cloud",
             "Components, transports and ownership for the active three-wheel profile")
    cols = [
        (80, 250, 570, 865, "EDGE DEVICE", "#E7F5F1", TEAL),
        (700, 250, 1010, 865, "LOCAL APPLICATION", "#EAF3FC", BLUE),
        (1760, 250, 460, 865, "HOSTED MODEL", "#F2EEFA", PURPLE),
    ]
    for x,y,w,h,title,fill,stroke in cols:
        d.box(x,y,w,h,fill=fill,stroke=stroke,behind=True)
        d.box(x+18,y+18,w-36,52,title,fill=stroke,stroke=stroke,font=21,
              color="white",bold=True,align="left")
    # Edge stack
    for y,title,body in [
        (350,"CONTROL + POWER","PS2 receiver · 3S LiPo · fuse / relay"),
        (515,"ESP32-S3 FIRMWARE","Local failsafe · three-wheel PWM / PID"),
        (680,"SENSOR + ACTUATORS","INA219 · dual L298N · 3 Hall motors"),
        (845,"PROFILE FINGERPRINT","Firmware constants · profile ID / hash"),
    ]:
        d.box(112,y,506,120,fill="white",stroke="#9BCFC3")
        d.text(135,y+17,460,34,title,font=20,bold=True)
        d.text(135,y+61,460,36,body,font=17,color=MUTED)
    d.wire(365,470,365,515,color=TEAL,width=3,arrow=True)
    d.wire(365,635,365,680,color=TEAL,width=3,arrow=True)
    # Local stack: bridge + two backend columns + frontend
    d.box(740,350,930,100,"USB SERIAL BRIDGE  ·  device samples → validated telemetry v1",
          fill="white",stroke="#9AC6E8",font=21,bold=True)
    d.box(740,520,430,190,fill="white",stroke="#9AC6E8")
    d.text(765,540,380,36,"FASTAPI INGEST",font=21,bold=True)
    d.text(765,590,380,85,"Contract validation\nProfile / model identity\nDeterministic signal checks",font=18,color=MUTED)
    d.box(1230,520,440,190,fill="white",stroke="#9AC6E8")
    d.text(1255,540,390,36,"DIAGNOSIS ENGINE",font=21,bold=True)
    d.text(1255,590,390,85,"Grounded context · read-only tools\nOrchestrator · safety policy\nVerification / audit",font=18,color=MUTED)
    d.box(740,770,430,135,"SQLITE DATA STORE\nSessions · telemetry · traces",
          fill="white",stroke="#9AC6E8",font=20)
    d.box(1230,770,440,135,"REACT FRONTEND\nWebSocket · graph · AI Doctor",
          fill="white",stroke="#9AC6E8",font=20)
    # Cloud
    d.box(1800,455,380,330,fill="white",stroke="#BDA6DC")
    d.text(1824,490,332,55,"Nebius Token Factory",font=24,bold=True,align="center")
    d.text(1824,575,332,105,"NVIDIA\nNemotron-3-Ultra-550b-a55b",font=22,
           color=PURPLE,bold=True,align="center")
    d.text(1824,710,332,42,"Structured hypotheses",font=18,color=MUTED,align="center")
    # Explicit, sparse transport arrows
    d.wire(618,575,740,400,color=BLUE,width=4,arrow=True,
           bends=((670,575),(670,400)))
    d.wire(955,450,955,520,color=BLUE,width=3,arrow=True)
    d.wire(1170,615,1230,615,color=BLUE,width=4,arrow=True)
    d.wire(955,710,955,770,color=BLUE,width=3,arrow=True)
    d.wire(1450,710,1450,770,color=BLUE,width=3,arrow=True)
    d.wire(1670,620,1800,620,color=PURPLE,width=4,arrow=True)
    d.wire(1800,680,1670,680,color=PURPLE,width=4,arrow=True)
    d.text(1680,575,115,34,"HTTPS",font=16,color=PURPLE,bold=True,align="center")
    d.text(1690,705,115,34,"result",font=16,color=PURPLE,bold=True,align="center")
    d.box(740,985,930,65,
          "Shared profile JSON defines pins and limits. Backend owns validation, model calls, policy and audit. Firmware owns local motor limits.",
          fill="#F5F9FC",stroke="#B9D4E6",font=18)
    d.footer("Live Nemotron mode requires a configured Nebius key and fresh source=device telemetry. The replay server is a separate labeled demonstration path.")
    return d.save("05-system-architecture.drawio")


if __name__ == "__main__":
    for create in (power, signal, motors, system_design, architecture):
        print(create())
