# The circuit board, and building one

Back to the [README](../README.md).

![The v3 mainboard, top side, as `just pcb-render v3` draws it](v3-top.png)

*The v3 mainboard, rendered from `pcb/v3/v3.circuit.tsx` by KiCad.*

## The circuit board

The v3 mainboard is a carrier board. The DevKitC and the two Adafruit
breakouts plug into it on headers, and it routes between them and adds the
cartridge header, RN1, the shutter button and an I2C port. It has no power
stage of its own: it runs from the DevKitC's USB port and 3.3 V regulator.
It's 100x100 mm, two layers, all through-hole.

`pcb/v3/v3.circuit.tsx` describes it in tscircuit: parts, pin assignments,
traces and silkscreen. The netlist and fabrication files are generated from
it.

```sh
just pcb-setup        # install tscircuit (bun)
just pcb-build v3     # build it and draw pcb/dist/v3/v3/pcb.png
just pcb-copper v3    # 0 shorts, 0 pad clashes; GND is joined by the pour
just pcb-fab v3       # KiCad DRC, then gerbers and drill files in v3-fab.zip
```

In my run, `just pcb-fab v3` reported 0 errors and 18 warnings, one per
footprint, each saying KiCad's configuration doesn't include the `tscircuit`
footprint library. The footprints are embedded in the exported board, so the
warnings don't affect the gerbers. `just pcb-fab` needs `kicad-cli`; with the Flatpak
KiCad, clone somewhere under your home directory, since the sandbox can't see
`/tmp`. `pcb/tools/` holds the copper clearance check and the step that
finishes the files for fabrication. `pcb/test00` and the `probe` boards are
earlier test designs.

## Bends and the cartridge header

The software bend is the `shift` setting. It draws each frame starting one
byte late, so every RGB565 pixel's two bytes are read across the boundary
with its neighbour. The colour comes out in hard bands rather than a smooth
hue shift, but the brightness mostly survives, so the picture stays readable
underneath. It costs nothing per pixel and can't hang the camera. It changes
the screen and the `_screen` copy, not the 1024x768 still.

Hardware bends go through the cartridge header, J2, a 2x16 pin header. Each
of its 16 columns has two pins: row A goes to the camera, row B to the ESP32.

| Column | 1-8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|
| Signal | D2-D9 | PCLK | HREF | VSYNC | GND | SDA | SCL | 3V3 | CART |
| A and B joined on the board | no | yes | yes | yes | yes | yes | yes | yes | yes |

Column 1 is at the right-hand end, as in the render above and in the photo in
the README. For the eight data
lines (D2 to D9), only a cartridge joins A to B. Eight jumper shunts across
columns 1 to 8 make a straight-through cartridge and a normal picture; from
there a cartridge can cross bits over, tie the ESP32's side to 3V3 or GND,
or mix in noise. With no cartridge fitted, the 8x10k resistor network RN1
holds the ESP32's side low. CART goes to IO14; this firmware doesn't read it yet.

The header mates all 32 pins in whatever order a cartridge rocks in, so swap
cartridges with the power off. Nothing keys it, and a cartridge fitted
backwards or one column over can short two camera outputs. I kept the header
plain on this revision on purpose. The fixes (splitting it into two keyed
2x8 blocks, alignment posts) don't change the pinout, so they can wait for
the next board.

The cartridge I use is an 8-way DIP switch across columns 1 to 8, one switch
per data line. This repo has no design files for it.

## Building one

The parts on the v3 board: an ESP32-S3-DevKitC-1 N8R8, Adafruit's OV5640
camera breakout (product 5840), Adafruit's 2.0-inch 320x240 TFT with microSD
(product 4311), a pushbutton, a 4609X-101-103LF resistor network, a 10 uF
capacitor and the 2x16 header. J3, a 4-pin header, is a spare port on the
camera's I2C bus. `just pcb-parts` downloads the vendors' board files.

The firmware gives the camera no clock pin, so the OV5640 breakout has to run
from its own oscillator. Adafruit's breakout has a jumper for that, INT or EXT; on EXT
the sensor never answers and looks exactly like a wiring fault.

None of this runs without the board, so I haven't checked these steps in a
clean setup the way I checked the laptop commands in the README:

```sh
just flash            # write CircuitPython 10.3.0 to the board
just fetch-bundle     # download Adafruit's library bundle
just libs             # copy the one library the firmware needs to the board
just willow           # deploy the runtime
just ui-push          # deploy the status art, src/ui.bin
just push src/code.py # deploy the firmware and watch it start
just console          # a serial console
```

`just flash` uses `esptool` and expects the CircuitPython `.bin` under
`vendor/`; download it from circuitpython.org for the
`espressif_esp32s3_devkitc_1_n8r8` board. `just bootloader` puts the board in
download mode, or hold BOOT and tap RST. `just boot` installs `src/boot.py`,
which hides the CIRCUITPY drive at power-on so the camera can run unplugged;
after that, `just devmode` brings the drive back for one boot.

On a new board, the bring-up scripts check one stage at a time before the
firmware: `just bringup 01` for the display, `03` for the camera, `03b` for a
live preview, `04` for the shutter and SD card, `05` for Bluetooth throughput
and `06` for still timing. Each one replaces `code.py` on the board until you
push the firmware again. `just --list` shows the rest.
