import React from "react"

const topPinOfCol = (col: number) => (col === 1 ? 1 : 34 - col)
const botPinOfCol = (col: number) => col + 1

const DATA_LINES = [
  { net: "D2", gp: "GP2" },
  { net: "D3", gp: "GP3" },
  { net: "D4", gp: "GP4" },
  { net: "D5", gp: "GP5" },
]

const COL_PITCH = 2.54
const COL1_X = -19.05
const colX = (col: number) => COL1_X + (col - 1) * COL_PITCH

const j2PinLabels: string[] = Array.from({ length: 32 }, () => "NC")
for (const [i, line] of DATA_LINES.entries()) {
  const col = i + 1
  j2PinLabels[topPinOfCol(col) - 1] = `${line.net}_A`
  j2PinLabels[botPinOfCol(col) - 1] = `${line.net}_B`
}

const J2_TOP_Y = 1.27
const J2_BOT_Y = -1.27

const U1_Y = 16
const U2_Y = -16
const R_SERIES_Y = 8
const R_PULLDOWN_Y = -8

export default () => (
  <board width="70mm" height="50mm" layers={2} routingDisabled>
    {}
    <pinheader
      name="J2"
      pinCount={32}
      gender="male"
      pitch="2.54mm"
      doubleRow
      footprint="pinrow32_p2.54mm_rows2"
      pinLabels={j2PinLabels}
      showSilkscreenPinLabels
      pcbX={0}
      pcbY={0}
      schX={0}
      schY={0}
    />

    {}
    <pinheader
      name="U1"
      pinCount={4}
      gender="female"
      pitch="2.54mm"
      footprint="pinrow4_p2.54mm"
      pinLabels={DATA_LINES.map((l) => l.net)}
      pcbX={colX(2)}
      pcbY={U1_Y}
      schX={-8}
      schY={0}
    />

    {}
    <pinheader
      name="U2"
      pinCount={4}
      gender="female"
      pitch="2.54mm"
      footprint="pinrow4_p2.54mm"
      pinLabels={DATA_LINES.map((l) => l.gp)}
      pcbX={colX(2)}
      pcbY={U2_Y}
      schX={8}
      schY={0}
    />

    {}
    {DATA_LINES.map((line, i) => {
      const col = i + 1
      const x = colX(col)
      const pd = DATA_LINES.length + col
      return (
        <React.Fragment key={line.net}>
          {}
          <resistor
            key={`R${col}`}
            name={`R${col}`}
            resistance="1k"
            footprint="0805"
            pcbX={x}
            pcbY={R_SERIES_Y}
            pcbRotation={90}
            schX={-4}
            schY={3 - i * 2}
          />
          {}
          <resistor
            key={`R${pd}`}
            name={`R${pd}`}
            resistance="100k"
            footprint="0805"
            pcbX={x}
            pcbY={R_PULLDOWN_Y}
            pcbRotation={90}
            schX={4}
            schY={3 - i * 2}
          />

          {}
          <trace name={`${line.net}_cam`} from={`.U1 > .${line.net}`} to={`.R${col} > .pin1`} />
          <trace name={`${line.net}_ser`} from={`.R${col} > .pin2`} to={`.J2 > .${line.net}_A`} />
          <trace name={`${line.net}_pico`} from={`.J2 > .${line.net}_B`} to={`.U2 > .${line.gp}`} />
          <trace name={`${line.net}_pd`} from={`.J2 > .${line.net}_B`} to={`.R${pd} > .pin1`} />
          <trace name={`${line.net}_pdg`} from={`.R${pd} > .pin2`} to="net.GND" />

          {}
          <pcbtrace
            layer="top"
            thickness="0.3mm"
            route={[
              { route_type: "wire", x, y: R_SERIES_Y - 1, width: 0.3, layer: "top" },
              { route_type: "wire", x, y: J2_TOP_Y, width: 0.3, layer: "top" },
            ]}
          />
          <pcbtrace
            layer="top"
            thickness="0.3mm"
            route={[
              { route_type: "wire", x, y: J2_BOT_Y, width: 0.3, layer: "top" },
              { route_type: "wire", x, y: R_PULLDOWN_Y + 1, width: 0.3, layer: "top" },
            ]}
          />
        </React.Fragment>
      )
    })}

    {}
    <copperpour connectsTo="net.GND" layer="bottom" clearance="0.2mm" />

    {}
    <silkscreentext text="test00 - toolchain proof, NOT FOR FABRICATION" pcbX={0} pcbY={22} fontSize={1.5} />
    <silkscreentext text="COL1" pcbX={colX(1)} pcbY={4.2} fontSize={0.8} />
  </board>
)
