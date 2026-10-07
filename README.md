# bendcam

> **About this repo.** This is a public snapshot of a private repo. I'm looking
> for work, and I wanted employers to have real code to look at: a hardware
> project I built by directing AI coding agents, from the circuit board to the
> firmware to the phone app. The snapshot is a copy of the private repo as of
> October 2026.
>
> **All code comments, docstrings and design notes have been removed.** While
> the repo was private, it was fine for them to hold personal details. Rather
> than edit them one by one, I've stripped them out to protect my privacy. The
> design reasoning is summarized in this README instead. Vendored third-party
> files (Adafruit's CircuitPython bundle and firmware, and the vendors' board
> files) are also left out, and the `just` recipes below fetch them.
>
> **This README is entirely AI-written.** I'm busy with my thesis right now.
> This camera is something I build in my free time.

bendcam is a digital camera built to be circuit-bent: glitched on purpose, by
software settings or by rewiring its image data while it runs. It's an
ESP32-S3 running CircuitPython, an OV5640 camera module, a 2-inch TFT screen
with a microSD slot, a shutter button, and a 32-pin cartridge header that
breaks the camera's data bus out so swappable cartridges can interfere with it.
An Android app changes the camera's settings and receives its photos over
Bluetooth.

## What's in it

About 12,000 lines.

| Part | What | Where |
|---|---|---|
| Firmware | The camera: preview, shutter, saving to SD, review, settings, Bluetooth | `src/code.py` (CircuitPython) |
| Runtime | A small component and event runtime the firmware is written on | `src/willow.py` |
| Simulator | Runs two builds of the firmware against fake hardware and diffs what they did | `tools/sim/` |
| Phone app | Settings and photo transfer over BLE | `phone/` (Expo / React Native, Kotlin) |
| Circuit board | The mainboard, written as code, plus earlier test boards | `pcb/` (tscircuit) |
| Host tools | Deploying code, Bluetooth transfer and settings, image conversion, UI art export | `tools/`, `justfile` |

## Quick start

The board is an ESP32-S3-DevKitC-1 N8R8.

```sh
just flash            # write CircuitPython 10.3.0 to the board
just fetch-bundle     # download Adafruit's library bundle
just libs             # copy the one library the firmware needs to the board
just push src/code.py # deploy the firmware
just console          # watch it run
```

`just flash` expects the CircuitPython `.bin` under `vendor/`. Download it
from circuitpython.org for the `espressif_esp32s3_devkitc_1_n8r8` board.

```sh
just sim              # firmware: main branch vs the working tree, every scenario
just fuzz             # random scenarios
just dev              # once: a venv with CircuitPython stubs, for the checks
just check            # ruff and pyright
```

For the phone app (`just phone <recipe>` runs these from the root):

```sh
just phone setup
just phone prebuild
just phone run
```

For the circuit board, `just pcb-parts` downloads the vendors' board files,
`just skills-update` downloads the kicad-happy analysis scripts that
`just pcb-review` uses, and `just pcb-fab v3` builds the fabrication files.

## How it's built

### The firmware is a tree of components

`src/code.py` is written as components (`Shutter`, `Saver`, `Card`, `Panel`,
`Camera`, `Link`, `Settings` and others) on `src/willow.py`, a runtime based on
Willow, a reactive programming model from my research. No component calls
another. They communicate through events, which run their listeners
immediately, and state changes, which land on the next tick, so every render
sees one consistent state. Hardware comes in through each component's `open()`,
which is what lets the simulator swap it out.

### A simulator that diffs behavior

`tools/sim` runs a build of the firmware on a laptop against fake CircuitPython
modules that record every hardware call: panel commands with a checksum of
every frame drawn, SD card writes, camera sensor registers, Bluetooth
notifications and the watchdog. `just sim` runs two builds through every
scenario in `tools/sim/scenarios.py` and diffs their traces, so a refactor can
be checked for identical behavior before it touches the board. The clock only
advances when real hardware would take time, which keeps traces deterministic.
`just fuzz` builds random scenarios: button presses, card pulls, a phone
connecting and dropping, bad settings.

The fakes don't model hard faults, heap fragmentation, real SPI and Bluetooth
timing, or button debounce. Those still need the board.

### Bends

The first bend is in software. The `shift` setting draws each frame starting
one byte late, so every RGB565 pixel's two bytes are read across the boundary
with its neighbor. Color comes out in hard bands rather than a smooth hue
shift, but brightness mostly survives, so the image stays readable underneath.
It costs nothing per pixel and can't hang the camera.

Hardware bends go through the cartridge header. Eight of the camera's data
lines (D2 to D9) pass through it, so a cartridge can swap bits, tie them high
or low, or mix in noise. The header is a mezzanine connector: cartridges swap
without tools, but all 32 pins mate in whatever order the cartridge rocks in,
so swap them with the power off. Nothing keys the connector, which is a known
hazard on this board revision.

### Camera driver limits

CircuitPython's `espcamera` wraps Espressif's C driver. It has no autofocus,
because the binding never uploads the sensor's focus program, and no register
access API. The driver only holds the I2C bus during its own calls, though, so
the firmware writes sensor registers itself between captures. That's how the
preview and still clock settings are applied, and they have to be reapplied
after every size change, because the driver rewrites them.

### Photos

A still is the frame already in the preview buffer, saved as a QVGA RGB565
BMP, so taking one needs no extra memory and no sensor reconfiguration. Saving
happens in the background, so the camera stays live while the card writes. The
phone app keeps the BMP and adds a JPEG to the gallery; `tools/to_jpeg.py` does
the same on a laptop. `src/settings.toml` stops CircuitPython from exposing the
SD card to the USB host, because host reads compete with the screen for the
SPI bus the two share.

### The circuit board is code

`pcb/v3/v3.circuit.tsx` describes the mainboard in tscircuit: parts, pin
assignments, traces and silkscreen. The netlist and fabrication files are
generated from it, and `pcb/tools/` checks copper clearances and finishes the
files for fabrication. `pcb/test00` and the `probe` boards are earlier test
designs.
