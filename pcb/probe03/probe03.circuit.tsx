import React from "react"

const wire = (pts: { x: number; y: number; layer?: string }[], width = 0.3) =>
  pts.map((p) => ({
    route_type: "wire" as const,
    x: p.x,
    y: p.y,
    width,
    layer: (p.layer ?? "top") as string,
  }))

export default () => (
  <board width="50mm" height="40mm" layers={2} routingDisabled>
    <pinheader
      name="JA"
      pinCount={2}
      gender="male"
      pitch="2.54mm"
      footprint="pinrow2_p2.54mm"
      pinLabels={["a", "b"]}
      pcbX={-15}
      pcbY={0}
      schX={-6}
      schY={0}
    />
    <pinheader
      name="JB"
      pinCount={2}
      gender="male"
      pitch="2.54mm"
      footprint="pinrow2_p2.54mm"
      pinLabels={["a", "b"]}
      pcbX={15}
      pcbY={0}
      schX={6}
      schY={0}
    />

    {}
    <trace from=".JA > .a" to="net.SIG" />
    <trace from=".JB > .a" to="net.SIG" />

    {}
    <trace from=".JA > .b" to="net.GND" />
    <trace from=".JB > .b" to="net.GND" />

    {}
    <via
      fromLayer="top"
      toLayer="bottom"
      holeDiameter="0.4mm"
      outerDiameter="0.8mm"
      pcbX={-8}
      pcbY={-1.27}
      connectsTo="net.SIG"
    />
    <via
      fromLayer="top"
      toLayer="bottom"
      holeDiameter="0.4mm"
      outerDiameter="0.8mm"
      pcbX={8}
      pcbY={-1.27}
      connectsTo="net.SIG"
    />

    {}
    <pcbtrace
      layer="top"
      thickness="0.3mm"
      route={wire([{ x: -15, y: -1.27 }, { x: -8, y: -1.27 }])}
    />
    <pcbtrace
      layer="bottom"
      thickness="0.3mm"
      route={wire([
        { x: -8, y: -1.27, layer: "bottom" },
        { x: 8, y: -1.27, layer: "bottom" },
      ])}
    />
    <pcbtrace
      layer="top"
      thickness="0.3mm"
      route={wire([{ x: 8, y: -1.27 }, { x: 15, y: -1.27 }])}
    />

    <copperpour connectsTo="net.GND" layer="bottom" clearance="0.25mm" />
  </board>
)
