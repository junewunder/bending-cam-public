import React from "react"

export default () => (
  <board width="60mm" height="40mm" layers={2} routingDisabled>
    {}
    <pushbutton name="SWA" footprint="kicad:Button_Switch_THT/SW_PUSH_6mm" pcbX={-20} pcbY={12} schX={-8} schY={6} />

    {}
    <pushbutton name="SWB" footprint="pushbutton" pcbX={-20} pcbY={0} schX={-8} schY={2} />

    {}
    <pushbutton name="SWC" footprint="tactileswitch" pcbX={-20} pcbY={-12} schX={-8} schY={-2} />

    {}
    <pinheader
      name="SWD"
      pinCount={2}
      gender="male"
      pitch="2.54mm"
      footprint="pinrow2_p2.54mm"
      pinLabels={["a", "b"]}
      pcbX={10}
      pcbY={12}
      schX={8}
      schY={6}
    />

    {}
    <pushbutton name="SWE" footprint="pushbutton_p4.5mm" pcbX={10} pcbY={0} schX={8} schY={2} />

    <resistor name="R1" resistance="1k" footprint="axial_p0.3in" pcbX={10} pcbY={-12} schX={8} schY={-2} />

    <trace from=".SWA > .pin1" to=".R1 > .pin1" />
    <trace from=".SWB > .pin1" to=".R1 > .pin1" />
    <trace from=".SWC > .pin1" to=".R1 > .pin1" />
    <trace from=".SWD > .a" to=".R1 > .pin1" />
    <trace from=".SWE > .pin1" to=".R1 > .pin1" />
  </board>
)
