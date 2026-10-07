import React from "react"

const topPinOfCol = (col: number, pinCount: number) =>
  col === 1 ? 1 : pinCount + 2 - col
const botPinOfCol = (col: number) => col + 1

const DEVKIT_J1 = [
  "V3V3_1", "V3V3_2", "EN", "IO4", "IO5", "IO6", "IO7", "IO15", "IO16", "IO17", "IO18",
  "IO8", "IO3", "IO46", "IO9", "IO10", "IO11", "IO12", "IO13", "IO14", "V5", "GND_N22",
]
const DEVKIT_J3 = [
  "GND_S1", "IO43", "RX", "IO1", "IO2", "IO42", "IO41", "IO40", "IO39", "IO38", "IO37",
  "IO36", "IO35", "IO0", "IO45", "IO48", "IO47", "IO21", "IO20", "IO19", "GND_S21", "GND_S22",
]

const silkName = (pad: string) =>
  pad.startsWith("V3V3") ? "3V3" : pad.startsWith("GND") ? "G" : pad === "V5" ? "5V"
    : pad === "IO43" ? "TX" : pad

const devkitPinAtCol = (col: number) => 23 - col

const u2PinLabels: string[] = Array.from({ length: 44 }, () => "NC")
for (let col = 1; col <= 22; col++) {
  u2PinLabels[topPinOfCol(col, 44) - 1] = DEVKIT_J1[devkitPinAtCol(col) - 1]
  u2PinLabels[botPinOfCol(col) - 1] = DEVKIT_J3[devkitPinAtCol(col) - 1]
}

const U1_CENTRE = ["GND", "SDA", "HS", "XC", "D8", "D6", "D4", "D2", "PD"]
const U1_BOTTOM = ["V3V", "SCL", "VS", "PC", "D9", "D7", "D5", "D3", "RT"]
const u1Silk = (pad: string) => (pad === "V3V" ? "3V" : pad === "GND" ? "G" : pad)

const u1PinLabels: string[] = Array.from({ length: 18 }, () => "NC")
for (let col = 1; col <= 9; col++) {
  u1PinLabels[topPinOfCol(col, 18) - 1] = U1_CENTRE[col - 1]
  u1PinLabels[botPinOfCol(col) - 1] = U1_BOTTOM[col - 1]
}

const U3_PINS = ["BL", "SDCS", "DC", "RST", "TCS", "MOSI", "MISO", "SCK", "GND", "OUT3V3", "VIN"]
const U3_SILK = ["BL", "SDCS", "D/C", "RST", "CS", "MOSI", "MISO", "SCK", "GND", "3Vo", "VIN"]

type Chan = {
  col: number
  net: string
  u1col: number
  u1row: "up" | "lo"
  dodge: -0.5 | 0 | 0.5
  io: string
}

const CHANNELS: Chan[] = [
  { col: 1, net: "D2", u1col: 8, u1row: "lo", dodge: 0, io: "IO5" },
  { col: 2, net: "D3", u1col: 8, u1row: "up", dodge: -0.5, io: "IO6" },
  { col: 3, net: "D4", u1col: 7, u1row: "lo", dodge: 0, io: "IO7" },
  { col: 4, net: "D5", u1col: 7, u1row: "up", dodge: -0.5, io: "IO15" },
  { col: 5, net: "D6", u1col: 6, u1row: "lo", dodge: 0, io: "IO16" },
  { col: 6, net: "D7", u1col: 6, u1row: "up", dodge: -0.5, io: "IO17" },
  { col: 7, net: "D8", u1col: 5, u1row: "lo", dodge: 0, io: "IO18" },
  { col: 8, net: "D9", u1col: 5, u1row: "up", dodge: -0.5, io: "IO8" },
]

const SYNC = [
  { col: 9, net: "PCLK", u1col: 4, u1row: "up", dodge: -0.5, io: "IO9" },
  { col: 10, net: "HREF", u1col: 3, u1row: "lo", dodge: 0, io: "IO10" },
  { col: 11, net: "VSYNC", u1col: 3, u1row: "up", dodge: -0.5, io: "IO11" },
]

const SERVICE = [
  { col: 12, net: "GND" },
  { col: 13, net: "SDA" },
  { col: 14, net: "SCL" },
  { col: 15, net: "V3V3" },
  { col: 16, net: "CART" },
]

const j2FootCol = (col: number) => 17 - col

const j2PinLabels: string[] = Array.from({ length: 32 }, () => "NC")
for (const ch of [...CHANNELS, ...SYNC, ...SERVICE]) {
  const fc = j2FootCol(ch.col)
  j2PinLabels[topPinOfCol(fc, 32) - 1] = `${ch.net}_A`
  j2PinLabels[botPinOfCol(fc) - 1] = `${ch.net}_B`
}

const PITCH = 2.54

const SILK_MIN = 1.5
const SILK_TITLE = 1.8
const SILK_EDGE_INSET = 0.6
const ART_X = 35
const ART_W = 24
const ART_H = 24
const ART_Y_TOP = 24.0
const ART_PITCH = 24
const ART: { src: string; h: number }[] = []
const TW = 0.3

const PAD_OD = 1.778
const PAD_ID = 1.0
const TH_PAD = `_id${PAD_ID}mm_od${PAD_OD}mm`

const DEVKIT_W = 62.87
const DEVKIT_H = 25.4
const DEVKIT_OVER_USB = 7.96
const USB_OVERHANG = 0
const DEVKIT_X_WEST = -50 - USB_OVERHANG
const X_U2_C1 = DEVKIT_X_WEST + DEVKIT_OVER_USB
const Y_U2_S = -47.2
const Y_U2_N = Y_U2_S + 22.86
const u2X = (col: number) => X_U2_C1 + (col - 1) * PITCH
const devkitX = (pin: number) => u2X(23 - pin)

const DROP_SHIFT = 3.27
const X_J2_C1 = X_U2_C1 + 17 * PITCH + DROP_SHIFT
const Y_J2_B = -4.0
const Y_J2_A = Y_J2_B + PITCH
const j2X = (col: number) => X_J2_C1 - (col - 1) * PITCH

const X_U1_C1 = X_J2_C1 - 18.9
const Y_U1_UP = 41.5
const Y_U1_LO = Y_U1_UP - PITCH
const u1X = (col: number) => X_U1_C1 + (col - 1) * PITCH
const u1Y = (row: "up" | "lo") => (row === "up" ? Y_U1_UP : Y_U1_LO)

const Y_U1_EXIT = Y_U1_LO - 3.46
const Y_FAN = Y_J2_A + 5.46

const X_CAM_HOLE_DX = 8.89
const Y_CAM_HOLE = Y_U1_UP - 31.75
const X_CAM_HOLE_W = u1X(5) - X_CAM_HOLE_DX
const X_CAM_HOLE_E = u1X(5) + X_CAM_HOLE_DX
const CAM_HOLE_KEEP = 3.2
const GATE_PITCH = 1.27
const GATE_SPARE = 1.25

const Y_DROP_TOP = Y_J2_B - 1.8
const Y_DROP_BOT = Y_DROP_TOP - 4.0

const Y_RN = Y_DROP_BOT - 3.2
const RN_BODY_L = 22.81
const RN_BODY_W = 2.49

const X_U3 = 17.5
const Y_U3_PIN1 = 44.2
const u3Y = (pin: number) => Y_U3_PIN1 - (pin - 1) * PITCH
const DISP_W = 59.05
const DISP_H = 35.56
const DISP_CX = X_U3 + 2.54 - DISP_W / 2
const DISP_CY = Y_U3_PIN1 - 12.7
const X_DISP_HOLE = X_U3 - 53.975
const DISP_HOLE_DY = 15.24

const CART_Y_N = DISP_CY - DISP_H / 2
const CART_Y_S = Y_U2_N + 1.27

const CH = {
  SCL: -27.0,
  SDA: -28.3,
  V3V3: -29.6,
  RESET: -30.9,
  SCK: -32.2,
  MISO: -33.5,
  MOSI: -34.8,
  TCS: -36.1,
  RST: -37.4,
  DC: -38.7,
  SDCS: -40.0,
  IO2: -41.3,
  SHUTTER: -42.6,
  IO43: -43.9,
}
const X_EXIT_SCL = devkitX(20) - PITCH / 2
const X_EXIT_SDA = devkitX(21) - PITCH / 2
const X_EXIT_3V3 = devkitX(22) - 1.46

const X_E_RESET = 14.0
const X_E_SPI0 = 19.5
const X_E_SHUTTER = 48.9

const X_SW1 = 38.5
const Y_SW1 = 44.5
const SW1_PIN3 = { x: X_SW1 + 2.25, y: Y_SW1 - 3.25 }

const MOUNT_INSET = 3.5
const MOUNT_HOLES = [
  { name: "HM1", x: -50 + MOUNT_INSET, y: 50 - MOUNT_INSET },
  { name: "HM2", x: 50 - MOUNT_INSET, y: 50 - MOUNT_INSET },
  { name: "HM3", x: 50 - MOUNT_INSET, y: -50 + MOUNT_INSET },
  { name: "HM4", x: -50 + MOUNT_INSET, y: -50 + MOUNT_INSET },
]
const X_E_PWRDN = X_CAM_HOLE_E + CAM_HOLE_KEEP + 0.6
const Y_PWRDN_TURN = Y_DROP_BOT - 1.6

const Y_3V3_TOP = Y_U3_PIN1
const X_3V3_U3 = X_U3 - 1.3
const X_3V3_WEST = -48.7
const Y_3V3_J2 = Y_J2_A + 2.0
const X_C1 = -40.0

const X_J3 = -47.0
const Y_J3_VIN = CART_Y_S + 3.0
const j3Y = (net: "Vin" | "SDA" | "SCL" | "Gnd") =>
  Y_J3_VIN + ["Vin", "SDA", "SCL", "Gnd"].indexOf(net) * PITCH

type Pt = { x: number; y: number }
const wire = (pts: Pt[], width: number, layer: "top" | "bottom") =>
  pts.map((p) => ({ route_type: "wire" as const, x: p.x, y: p.y, width, layer }))

const Track = ({ pts, width = TW }: { pts: Pt[]; width?: number }) => (
  <pcbtrace layer="top" thickness={`${width}mm`} route={wire(pts, width, "top")} />
)

const SPI = [
  { net: "SCK", io: "IO47", u3pin: 8 },
  { net: "MISO", io: "IO48", u3pin: 7 },
  { net: "MOSI", io: "IO38", u3pin: 6 },
  { net: "TCS", io: "IO39", u3pin: 5 },
  { net: "RST", io: "IO40", u3pin: 4 },
  { net: "DC", io: "IO41", u3pin: 3 },
  { net: "SDCS", io: "IO42", u3pin: 2 },
] as const
const xSpiRiser = (i: number) => X_E_SPI0 + i * 1.3
const TEST_PADS = [
  { io: "IO2", x: 31.0 },
  { io: "IO43", x: 35.0 },
] as const

const U1_PORT: Record<string, string> = {
  PCLK: "PC", VSYNC: "VS", HREF: "HS", SDA: "SDA", SCL: "SCL", V3V3: "V3V",
}
const u1Port = (net: string) => U1_PORT[net] ?? net

const CAMFAN: { net: string; u1col: number; u1row: "up" | "lo"; dodge: number; col: number }[] = [
  ...CHANNELS.map((c) => ({ net: c.net, u1col: c.u1col, u1row: c.u1row, dodge: c.dodge, col: c.col })),
  ...SYNC.map((c) => ({ net: c.net, u1col: c.u1col, u1row: c.u1row as "up" | "lo", dodge: c.dodge, col: c.col })),
  { net: "SDA", u1col: 2, u1row: "lo", dodge: 0, col: 13 },
  { net: "SCL", u1col: 2, u1row: "up", dodge: -0.5, col: 14 },
  { net: "V3V3", u1col: 1, u1row: "up", dodge: -0.5, col: 15 },
]

const DROPS: { net: string; col: number; io: string }[] = [
  ...CHANNELS.map((c) => ({ net: c.net, col: c.col, io: c.io })),
  ...SYNC.map((c) => ({ net: c.net, col: c.col, io: c.io })),
  { net: "SDA", col: 13, io: "IO12" },
  { net: "SCL", col: 14, io: "IO13" },
  { net: "CART", col: 16, io: "IO14" },
]
const northX = (io: string) => devkitX(DEVKIT_J1.indexOf(io) + 1)
const southX = (io: string) => devkitX(DEVKIT_J3.indexOf(io) + 1)

const X_RN_COM = northX("IO8") - PITCH
const rnX = (pin: number) => X_RN_COM + (pin - 1) * PITCH
const rnPin = (col: number) => 10 - col
const rnPinLabels = Object.fromEntries([
  ["pin1", "COM"],
  ...CHANNELS.map((ch) => [`pin${rnPin(ch.col)}`, ch.net]),
])

const exitX = (ch: { u1col: number; dodge: number }) => u1X(ch.u1col) + ch.dodge * PITCH
const Y_U1_BAND = (Y_U1_UP + Y_U1_LO) / 2

const gateX = (ch: { col: number }) => {
  if (ch.col <= 8) return u1X(5) + (4.5 - ch.col) * GATE_PITCH
  const shift = X_CAM_HOLE_W - CAM_HOLE_KEEP - GATE_SPARE - j2X(9)
  return j2X(ch.col) + Math.min(0, shift)
}

const PIN1_NORTH_ROTATION = -90

export default () => (
  <board width="100mm" height="100mm" layers={2} routingDisabled>
    {}

    <pinheader
      name="U2" pinCount={44} gender="female" pitch="2.54mm" doubleRow
      footprint={`pinrow44_p2.54mm${TH_PAD}_rows2_py22.86mm`}
      pinLabels={u2PinLabels} showSilkscreenPinLabels
      pcbX={(u2X(1) + u2X(22)) / 2} pcbY={(Y_U2_N + Y_U2_S) / 2}
      schX={0} schY={0}
    />

    {}
    <pinheader
      name="U1" pinCount={18} gender="female" pitch="2.54mm" doubleRow
      footprint={`pinrow18_p2.54mm${TH_PAD}_rows2`}
      pinLabels={u1PinLabels} showSilkscreenPinLabels
      layer="bottom" pcbRotation={180}
      pcbX={(X_U1_C1 + u1X(9)) / 2} pcbY={(Y_U1_UP + Y_U1_LO) / 2}
      schX={-14} schY={0}
    />

    <pinheader
      name="J2" pinCount={32} gender="male" pitch="2.54mm" doubleRow
      footprint={`pinrow32_p2.54mm_nopinlabels${TH_PAD}_rows2`}
      pinLabels={j2PinLabels}
      pcbX={(X_J2_C1 + j2X(16)) / 2} pcbY={(Y_J2_A + Y_J2_B) / 2}
      schX={-14} schY={-14}
    />

    <pinheader
      name="U3" pinCount={11} gender="female" pitch="2.54mm"
      footprint={`pinrow11_p2.54mm${TH_PAD}`}
      pinLabels={U3_PINS}
      pcbRotation={PIN1_NORTH_ROTATION}
      pcbX={X_U3} pcbY={(u3Y(1) + u3Y(11)) / 2}
      schX={16} schY={6}
    />

    {}
    <pinheader
      name="J3" pinCount={4} gender="male" pitch="2.54mm"
      footprint={`pinrow4_p2.54mm${TH_PAD}`}
      pinLabels={["Gnd", "SCL", "SDA", "Vin"]} showSilkscreenPinLabels
      pcbRotation={PIN1_NORTH_ROTATION}
      pcbX={X_J3} pcbY={(j3Y("Vin") + j3Y("Gnd")) / 2}
      schX={16} schY={-8}
    />

    {}
    {}
    <pushbutton name="SW1" footprint="pushbutton" pcbX={X_SW1} pcbY={Y_SW1} schX={-14} schY={12} />

    {}
    {}
    <chip
      name="RN1" manufacturerPartNumber="4609X-101-103LF"
      footprint={`pinrow9_p2.54mm_nopinlabels${TH_PAD}`}
      pinLabels={rnPinLabels}
      pcbX={(rnX(1) + rnX(9)) / 2} pcbY={Y_RN}
      schX={4} schY={2}
    />

    {}
    {}
    <capacitor name="C1" capacitance="10uF" footprint="radial_p2.54mm_d5mm"
      pcbX={X_C1} pcbY={Y_3V3_J2 + 1.27} pcbRotation={90} schX={-4} schY={-14} />

    {}
    {}
    {CAMFAN.map((ch) => {
      const xU1 = u1X(ch.u1col)
      const ex = exitX(ch)
      const x2 = j2X(ch.col)
      return (
        <React.Fragment key={`fan-${ch.net}`}>
          {}
          {ch.u1row === "up" ? (
            <Track pts={[
              { x: xU1, y: Y_U1_UP },
              { x: xU1, y: Y_U1_BAND },
              { x: ex, y: Y_U1_BAND },
              { x: ex, y: Y_U1_EXIT },
            ]} />
          ) : (
            <Track pts={[{ x: xU1, y: Y_U1_LO }, { x: ex, y: Y_U1_EXIT }]} />
          )}
          <Track pts={[
            { x: ex, y: Y_U1_EXIT },
            { x: gateX(ch), y: Y_CAM_HOLE + CAM_HOLE_KEEP },
            { x: gateX(ch), y: Y_CAM_HOLE - CAM_HOLE_KEEP },
            { x: x2, y: Y_FAN },
          ]} />
          <Track pts={[{ x: x2, y: Y_FAN }, { x: x2, y: Y_J2_A }]} />
        </React.Fragment>
      )
    })}

    {}
    {}
    {DROPS.map((d) => (
      <Track key={`drop-${d.net}`} pts={[
        { x: j2X(d.col), y: Y_J2_B },
        { x: j2X(d.col), y: Y_DROP_TOP },
        { x: northX(d.io), y: Y_DROP_BOT },
        { x: northX(d.io), y: CHANNELS.some((c) => c.net === d.net) ? Y_RN : Y_U2_N },
      ]} />
    ))}

    {}
    {CHANNELS.map((ch) => {
      const x = northX(ch.io)
      return (
        <React.Fragment key={`bit-${ch.net}`}>
          {}
          <trace from={`.J2 > .${ch.net}_B`} to={`.U2 > .${ch.io}`} />
          <trace from={`.J2 > .${ch.net}_B`} to={`.RN1 > .${ch.net}`} />

          {}
          <Track pts={[{ x, y: Y_RN }, { x, y: Y_U2_N }]} />
        </React.Fragment>
      )
    })}

    {}
    {}
    {SYNC.map((s) => (
      <React.Fragment key={`sync-${s.net}`}>
        <trace from={`.J2 > .${s.net}_A`} to={`.J2 > .${s.net}_B`} />
        <trace from={`.J2 > .${s.net}_B`} to={`.U2 > .${s.io}`} />
        <Track pts={[{ x: j2X(s.col), y: Y_J2_A }, { x: j2X(s.col), y: Y_J2_B }]} />
      </React.Fragment>
    ))}

    {}
    {SERVICE.map((s) => (
      <React.Fragment key={`svc-${s.net}`}>
        <trace name={`J2_${s.net}_link`} from={`.J2 > .${s.net}_A`} to={`.J2 > .${s.net}_B`} />
        <Track pts={[{ x: j2X(s.col), y: Y_J2_A }, { x: j2X(s.col), y: Y_J2_B }]} />
      </React.Fragment>
    ))}

    {}
    {}
    {CHANNELS.map((ch) => (
      <trace key={`nl-${ch.net}`} from={`.U1 > .${ch.net}`} to={`.J2 > .${ch.net}_A`} />
    ))}
    {SYNC.map((s) => (
      <trace key={`nl-${s.net}`} from={`.U1 > .${u1Port(s.net)}`} to={`.J2 > .${s.net}_A`} />
    ))}

    {}
    <trace from=".U1 > .RT" to=".U2 > .IO21" />
    <trace from=".U1 > .PD" to=".U2 > .IO4" />
    <Track pts={[
      { x: u1X(9), y: Y_U1_UP },
      { x: u1X(9), y: Y_U1_BAND },
      { x: X_E_RESET, y: Y_U1_BAND },
      { x: X_E_RESET, y: CH.RESET },
      { x: southX("IO21"), y: CH.RESET },
      { x: southX("IO21"), y: Y_U2_S },
    ]} />
    <Track pts={[
      { x: u1X(9), y: Y_U1_LO },
      { x: u1X(9), y: Y_U1_EXIT },
      { x: X_E_PWRDN, y: Y_U1_EXIT - (X_E_PWRDN - u1X(9)) },
      { x: X_E_PWRDN, y: Y_PWRDN_TURN },
      { x: northX("IO4"), y: Y_PWRDN_TURN },
      { x: northX("IO4"), y: Y_U2_N },
    ]} />

    {}

    {}
    {}
    <trace from=".U1 > .SDA" to="net.SDA" />
    <trace from=".J2 > .SDA_A" to="net.SDA" />
    <trace from=".U2 > .IO12" to="net.SDA" />
    <trace from=".J3 > .SDA" to="net.SDA" />
    <trace from=".U1 > .SCL" to="net.SCL" />
    <trace from=".J2 > .SCL_A" to="net.SCL" />
    <trace from=".U2 > .IO13" to="net.SCL" />
    <trace from=".J3 > .SCL" to="net.SCL" />

    {}
    <Track pts={[
      { x: northX("IO12"), y: Y_U2_N }, { x: northX("IO12"), y: CH.SDA },
      { x: X_EXIT_SDA, y: CH.SDA }, { x: X_EXIT_SDA, y: j3Y("SDA") },
      { x: X_J3, y: j3Y("SDA") },
    ]} />
    <Track pts={[
      { x: northX("IO13"), y: Y_U2_N }, { x: northX("IO13"), y: CH.SCL },
      { x: X_EXIT_SCL, y: CH.SCL }, { x: X_EXIT_SCL, y: j3Y("SCL") },
      { x: X_J3, y: j3Y("SCL") },
    ]} />

    {}
    <trace name="CART_IO" from=".J2 > .CART_A" to=".U2 > .IO14" />

    {}
    {}
    <trace from=".SW1 > .pin3" to=".U2 > .IO1" />
    <trace from=".SW1 > .pin1" to="net.GND" />
    <Track pts={[
      SW1_PIN3,
      { x: X_E_SHUTTER, y: SW1_PIN3.y },
      { x: X_E_SHUTTER, y: CH.SHUTTER },
      { x: southX("IO1"), y: CH.SHUTTER },
      { x: southX("IO1"), y: Y_U2_S },
    ]} />

    {}
    {}
    {SPI.map((s) => (
      <trace key={`nl-spi-${s.net}`} from={`.U3 > .${s.net}`} to={`.U2 > .${s.io}`} />
    ))}

    {SPI.map((s, i) => {
      const src = southX(s.io)
      const lane = CH[s.net]
      const rise = xSpiRiser(i)
      const pad = u3Y(s.u3pin)
      return (
        <Track key={`spi-${s.net}`} pts={[
          { x: src, y: Y_U2_S }, { x: src, y: lane },
          { x: rise, y: lane }, { x: rise, y: pad },
          { x: X_U3, y: pad },
        ]} />
      )
    })}

    {}
    {}
    <trace from=".U2 > .V3V3_1" to="net.V3V3" />
    <trace from=".U2 > .V3V3_2" to="net.V3V3" />
    <trace from=".U1 > .V3V" to="net.V3V3" />
    <trace from=".U3 > .VIN" to="net.V3V3" />
    <trace from=".U3 > .BL" to="net.V3V3" />
    <trace from=".J2 > .V3V3_A" to="net.V3V3" />
    <trace from=".J3 > .Vin" to="net.V3V3" />
    <trace from=".C1 > .pin1" to="net.V3V3" />

    <Track pts={[{ x: devkitX(1), y: Y_U2_N }, { x: devkitX(2), y: Y_U2_N }]} />
    <Track pts={[
      { x: devkitX(1), y: Y_U2_N },
      { x: devkitX(1), y: CH.V3V3 },
      { x: X_EXIT_3V3, y: CH.V3V3 },
      { x: X_EXIT_3V3, y: j3Y("Vin") },
      { x: X_J3, y: j3Y("Vin") },
    ]} />
    <Track pts={[
      { x: X_J3, y: j3Y("Vin") },
      { x: X_3V3_WEST, y: j3Y("Vin") },
      { x: X_3V3_WEST, y: Y_3V3_J2 },
      { x: X_C1, y: Y_3V3_J2 },
      { x: j2X(15), y: Y_3V3_J2 },
    ]} />
    <Track pts={[
      { x: u1X(1), y: Y_3V3_TOP },
      { x: X_3V3_U3, y: Y_3V3_TOP },
      { x: X_U3, y: Y_3V3_TOP },
    ]} />
    <Track pts={[{ x: u1X(1), y: Y_3V3_TOP }, { x: u1X(1), y: Y_U1_UP }]} />
    <Track pts={[
      { x: X_3V3_U3, y: Y_3V3_TOP },
      { x: X_3V3_U3, y: u3Y(11) },
      { x: X_U3, y: u3Y(11) },
    ]} />

    {}
    {}
    <trace from=".U1 > .GND" to="net.GND" />
    <trace from=".U3 > .GND" to="net.GND" />
    <trace from=".J2 > .GND_A" to="net.GND" />
    <trace from=".J2 > .GND_B" to="net.GND" />
    <trace from=".J3 > .Gnd" to="net.GND" />
    {}
    <trace from=".RN1 > .COM" to="net.GND" />
    <trace from=".C1 > .pin2" to="net.GND" />
    {["GND_N22", "GND_S1", "GND_S21", "GND_S22"].map((p) => (
      <trace key={p} name={`GND_U2_${p}`} from={`.U2 > .${p}`} to="net.GND" />
    ))}

    {}
    {}
    {TEST_PADS.map(({ io, x }) => (
      <React.Fragment key={`tp-${io}`}>
        <pinheader name={`TP${io.slice(2)}`} pinCount={1} gender="male" pitch="2.54mm"
          footprint={`pinrow1_p2.54mm${TH_PAD}`} pinLabels={[io]} showSilkscreenPinLabels
          pcbX={x} pcbY={CH[io]} schX={8} schY={io === "IO2" ? 4 : 2} />
        <trace from={`.TP${io.slice(2)} > .pin1`} to={`.U2 > .${io}`} />
        <Track pts={[
          { x: southX(io), y: Y_U2_S }, { x: southX(io), y: CH[io] }, { x, y: CH[io] },
        ]} />
      </React.Fragment>
    ))}

    {}
    {}
    <hole name="HC1" diameter="3.2mm" pcbX={X_CAM_HOLE_W} pcbY={Y_CAM_HOLE} />
    <hole name="HC2" diameter="3.2mm" pcbX={X_CAM_HOLE_E} pcbY={Y_CAM_HOLE} />

    {}
    <hole name="HD1" diameter="2.7mm" pcbX={X_DISP_HOLE} pcbY={DISP_CY + DISP_HOLE_DY} />
    <hole name="HD2" diameter="2.7mm" pcbX={X_DISP_HOLE} pcbY={DISP_CY - DISP_HOLE_DY} />

    {}
    {MOUNT_HOLES.map((h) => (
      <hole key={h.name} name={h.name} diameter="3.2mm" pcbX={h.x} pcbY={h.y} />
    ))}

    {}
    {}
    <copperpour connectsTo="net.GND" layer="bottom" clearance="0.25mm" />

    {}
    {}
    <silkscreentext text="bending-cam v3 mainboard" pcbX={28} pcbY={-47.5} fontSize={SILK_TITLE} />

    {}
    {[...CHANNELS, ...SYNC, ...SERVICE].map((c) => (
      <silkscreentext key={`j2col-${c.net}`}
        text={c.net === "V3V3" ? "3V3" : c.net}
        pcbX={j2X(c.col)} pcbY={Y_J2_B - 4.4}
        fontSize={SILK_TITLE} pcbRotation={90} />
    ))}

    <silkscreentext text="SHUTTER" pcbX={X_SW1 - 0.5} pcbY={38.4} fontSize={SILK_MIN} />

    {}
    {}
    <silkscreencircle pcbX={rnX(0)} pcbY={Y_RN} radius={0.3} strokeWidth={0.6} />
    <silkscreentext text="COM" pcbX={rnX(0)} pcbY={Y_RN - 2.4} fontSize={SILK_MIN} />
    <silkscreentext text="RN1 8x10k" pcbX={rnX(5)} pcbY={Y_RN - 2.4} fontSize={SILK_MIN} />
    <silkscreenrect pcbX={(rnX(1) + rnX(9)) / 2} pcbY={Y_RN}
      width={RN_BODY_L} height={RN_BODY_W} filled={false} strokeWidth={0.2} />

    {}
    <silkscreentext text="10uF" pcbX={X_C1 - 5.0} pcbY={Y_3V3_J2 + 1.27} fontSize={SILK_MIN} />
    <silkscreentext text="+" pcbX={X_C1 + 1.6} pcbY={Y_3V3_J2 - 1.5} fontSize={SILK_MIN} />

    {}
    {}
    <silkscreenrect pcbX={DEVKIT_X_WEST + SILK_EDGE_INSET + (DEVKIT_W - SILK_EDGE_INSET) / 2} pcbY={(Y_U2_N + Y_U2_S) / 2}
      width={DEVKIT_W - SILK_EDGE_INSET} height={DEVKIT_H} filled={false} strokeWidth={0.2} />
    <silkscreentext text="<- USB" pcbX={DEVKIT_X_WEST + 12} pcbY={(Y_U2_N + Y_U2_S) / 2 + 2.2} fontSize={SILK_TITLE} />
    <silkscreentext text="ESP32-S3-DevKitC-1 N8R8" pcbX={DEVKIT_X_WEST + DEVKIT_W / 2} pcbY={(Y_U2_N + Y_U2_S) / 2 - 1.8} fontSize={SILK_TITLE} />
    {Array.from({ length: 22 }, (_, i) => i + 1).flatMap((col) => [
      [DEVKIT_J1[devkitPinAtCol(col) - 1], Y_U2_N - 3.4],
      [DEVKIT_J3[devkitPinAtCol(col) - 1], Y_U2_S + 3.4],
    ].map(([name, y]) => (
      <silkscreentext key={`u2-${name}`} text={silkName(name as string)}
        pcbX={u2X(col)} pcbY={y as number} fontSize={SILK_MIN} pcbRotation={90} />
    )))}

    <silkscreentext text="I2C1" pcbX={X_J3} pcbY={j3Y("Gnd") + 2.4} fontSize={SILK_MIN} />
    {(["Gnd", "SCL", "SDA", "Vin"] as const).map((p) => (
      <silkscreentext key={`j3-${p}`} text={p === "Vin" ? "3V3" : p.toUpperCase()}
        pcbX={X_J3 + 3.9} pcbY={j3Y(p)} fontSize={SILK_MIN} />
    ))}

    {TEST_PADS.map(({ io, x }, i) => (
      <silkscreentext key={`tp-silk-${io}`} text={io}
        pcbX={x} pcbY={CH[io] + (i === 0 ? 2.0 : -2.0)} fontSize={SILK_MIN} />
    ))}

    <silkscreentext text="CAMERA ON BACK" pcbX={u1X(5)} pcbY={Y_U1_UP + 4.6} fontSize={SILK_TITLE} />
    {}
    {Array.from({ length: 9 }, (_, i) => i + 1).flatMap((col) => [
      <silkscreentext key={`u1-up-${col}`} text={u1Silk(U1_BOTTOM[col - 1])} layer="bottom"
        pcbX={u1X(col)} pcbY={Y_U1_UP + 2.9} fontSize={SILK_MIN} pcbRotation={90} />,
      <silkscreentext key={`u1-lo-${col}`} text={u1Silk(U1_CENTRE[col - 1])} layer="bottom"
        pcbX={u1X(col)} pcbY={Y_U1_LO - 2.9} fontSize={SILK_MIN} pcbRotation={90} />,
    ])}

    {}
    <silkscreenrect pcbX={DISP_CX} pcbY={DISP_CY} width={DISP_W} height={DISP_H}
      filled={false} strokeWidth={0.2} />
    <silkscreentext text="SCREEN" pcbX={DISP_CX} pcbY={DISP_CY} fontSize={SILK_TITLE} />
    <silkscreentext text="<- SD" pcbX={DISP_CX - DISP_W / 2 + 4.5} pcbY={DISP_CY} fontSize={SILK_TITLE} />
    {}
    {U3_SILK.map((name, i) => (
      <silkscreentext key={`u3-${i}`} text={name}
        pcbX={X_U3 - 5.4} pcbY={u3Y(i + 1)} fontSize={SILK_MIN} />
    ))}

    {}
    {ART.map(({ src, h }, i) => (
      <silkscreengraphic key={`art-${i}`} imageUrl={`file://${src}`}
        pcbX={ART_X} pcbY={ART_Y_TOP - i * ART_PITCH + (ART_H - h) / 2} width={ART_W} height={h} />
    ))}
  </board>
)

