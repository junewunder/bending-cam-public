# bendcam

bendcam is a digital camera built to be circuit-bent: glitched on purpose,
either by a setting in software or by rewiring its image data while it runs.
It's an ESP32-S3 running CircuitPython, an OV5640 camera module, a 2-inch
320x240 screen with a microSD slot, a shutter button, and a 32-pin cartridge
header that the camera's data lines pass through, so a plug-in cartridge can
interfere with them. An Android app changes the camera's settings and receives
its photos over Bluetooth. The circuit board is written as code.

This repo holds all of it: the firmware, the phone app, the board, and a
simulator that runs two builds of the firmware against fake hardware and diffs
every hardware call they make, so a refactor can be checked before it touches
the board. The v3 board in `pcb/v3` is built and runs this firmware.

I built bendcam by directing AI coding agents: they wrote the code, and I
decided what the camera should do, tried it on the bench, and chose
what got checked and how. Writing code got cheap that way, but reviewing it
didn't, so the checks are where I put my own work: the simulator, the fuzzer,
and lint and type checks on the firmware and the app.

If you're here to bend a camera, skip to [Bends](#bends) and
[Building one](#building-one). If you have five minutes for the code, these
are the places to look:

- `tools/sim/run.py`: the trace diff, and `by_kind` for changes that move
  work between frames.
- `tools/sim/fuzz.py`, `check()` at line 126: the rules every random run must
  keep.
- `src/willow.py`, `flush()` at line 372 and `tick()` below it: the order a
  tick runs in.
- `src/code.py`, `Main.run()` at line 2435: the camera's main loop.

![The v3 mainboard, top side, as `just pcb-render v3` draws it](docs/v3-top.png)

*The v3 mainboard, rendered from `pcb/v3/v3.circuit.tsx` by KiCad. It's a
render, not a photo.*

## What's here

| Part | What it does | Where | Lines |
|---|---|---|---|
| Firmware | Preview, shutter, saving to SD, settings, review, Bluetooth, crash recovery | `src/code.py` | 2,613 |
| Runtime | The component and event runtime the firmware is written on | `src/willow.py` | 457 |
| Bring-up scripts | One hardware stage each: display, camera, shutter and SD, BLE, still timing | `src/bringup/` | 972 |
| Simulator and fuzzer | Fake CircuitPython modules, scenarios, the trace diff, random runs | `tools/sim/` | 1,259 |
| Phone app | Settings, photo transfer and review over BLE (Expo / React Native, Kotlin modules) | `phone/` | 3,730 |
| Circuit board | The v3 mainboard as tscircuit code, earlier test boards, fab tools | `pcb/` | 1,753 |
| Host tools | Deploying to the board, BLE from a laptop, BMP to JPEG, UI art export | `tools/`, `justfile` | 1,838 |

## Try it without the hardware

You need [just](https://github.com/casey/just), Python 3.9 or newer, and
[uv](https://docs.astral.sh/uv/) for the checks. These are the results from a
fresh clone on my laptop:

```sh
just sim      # 18 of 18 scenarios the same, in under 2 s
just fuzz     # 0 of 200 seeds failed, in about 25 s
just dev      # once: a .venv with the CircuitPython 10.3.0 stubs for this board
just check    # ruff: All checks passed; pyright: 0 errors
```

`just sim` and `just fuzz` use only the standard library. For the phone app,
`just phone setup` then `just phone typecheck` installs it with pnpm and
type-checks it; running it needs the Android SDK and a JDK (`just phone auth`
says what's missing), and it has a fake camera you can switch on in the app.
For the board, `just pcb-setup` installs tscircuit with bun, then
`just pcb-build v3` builds it.

## The simulator

`tools/sim` runs a build of `src/code.py` on a laptop against fake
CircuitPython modules. Every call that would reach hardware goes into a trace:
panel commands with a CRC of every frame drawn, sensor register writes,
files opened, written (with a CRC of the bytes), renamed and removed on the
card, nvm writes, Bluetooth notifications, the watchdog, and every `print()`.

`just sim` takes two builds, `main` and the working tree by default (`--a` and
`--b` take any git revision), runs each through every scenario in
`tools/sim/scenarios.py`, and diffs their traces. A scenario is a script of
events by frame: shutter presses, the card pulled mid-save and put back, no
RAM for a still, a full card, a camera that stops sending frames, a phone
connecting, writing good and bad settings, and dropping. A refactor should come
back `same` on all 18. A change in behavior shows up as a diff to explain.

The clock only moves when the hardware would take time (a frame, a sleep, a
card write at a modelled 1 MB/s), never on a read, so a build that checks the
time more often still gets the same trace. When a change moves work from one
frame to the next on purpose, `--by-kind` compares each kind of line in order
and leaves the frame markers out.

`just fuzz` builds a random scenario per seed and checks the run against rules
rather than another build: the run ends normally, nothing crashes, the
watchdog is never left unfed for 10 s, no file is written twice, shot numbers
only go up, every captured still is either saved or reported lost, every image
file on the card is the right size, every line to the phone is one JSON object
that fits in a packet, and nothing is sent to the phone that wasn't asked for.
`--seed N --show` replays one seed with its trace.

To see both catch a bug, make the shot counter stop advancing after the first
shot. In `Card.claim` in `src/code.py`, change `self.seq += 1` to
`self.seq = max(self.seq, 1)`:

```
$ just sim
...
13 of 18 scenarios the same
$ just sim presses
DIFF  presses        4498 vs 4498 lines
      -file rename /sd/_screen.tmp /sd/IMG_0002_screen.bmp
      +file rename /sd/_screen.tmp /sd/IMG_0001_screen.bmp
      ...
      -print: captured shot 2 in 0.60s, 2 pending
      +print: captured shot 1 in 0.60s, 2 pending
$ just fuzz --seeds 150
FAIL seed 149: written twice: /sd/IMG_0001_screen.bmp; shot 1 after shot 1; ...
120 of 150 seeds failed
```

The fuzzer only checks its rules. When I made the counter never advance at
all, no shot was ever taken, nothing broke a rule, and 0 of 150 seeds failed;
`just sim` flagged 13 of 18 scenarios.

What the fakes don't model: hard faults, heap fragmentation, garbage
collection pauses, real SPI and Bluetooth timing, and button debounce (the
firmware leaves that to CircuitPython's `keypad`, scanning every 20 ms). Those
still need the board. The fakes are also written to the same understanding of
the hardware as the firmware, so `same` means two builds behave alike against
them, not that either is right on the board.

## The firmware

`src/code.py` is a tree of components (`Shutter`, `Saver`, `Card`, `Panel`,
`Camera`, `Look`, `Link`, `Outbox`, `Settings`, `Review`) on
`src/willow.py`, a small runtime based on Willow, a reactive programming model
from my research that isn't published yet. No component calls another. They
talk through events and state:

- `self.emit(label, payload)` runs every listener of that label before it
  returns. `bind`, `once`, `remove`, `after` and `cancel` take effect at once.
- A state setter only queues the new value. Each `tick()` dispatches the
  drivers' events (a key press, a frame), applies the queued values, fires due
  timers, then renders the tree. A component's `@on("x", "y")` blocks run only
  when `x` or `y` changed, so every render sees one consistent state.
- The update queue, event queue and timer table are fixed-size arrays (64
  updates, 16 events, 16 timers), allocated once, because on the
  microcontroller a garbage collection pass costs frames. Emits nested 8 deep
  raise an error, since that means a cycle.
- `src/willow.pyi` types it for pyright: `x, set_x = state(0)` gives a value
  and a typed `Setter`.

`tools/sim/calculus_debounce.py` is a small model of a different cancel rule,
one where a cancel with no timer pending is kept and swallows the next timer.
Under that rule, a debounce built as "cancel, then start a timer" on every
change never fires (run it: `slow ends None` both times). In `src/willow.py`,
a cancel only reaches a pending timer.

Hardware handles come in through each component's `open()`, which is what
lets the simulator swap the hardware out. The main loop still schedules the
work that shares a frame, the SPI bus and the radio, in the order the hardware
needs. The board's pins are at the top of `src/code.py`, and its settings,
the ones the phone shows, are in the `SETTINGS` table below them.

What happens on a press:

1. The frame on the screen is saved at once as `IMG_NNNN_screen.bmp`, 320x240.
2. The sensor switches to 1024x768, takes one still into a 1.5 MB buffer in
   RAM, and switches back to the preview.
3. The still is written to the card as `IMG_NNNN.bmp` in 32 KB slices between
   preview frames, so the camera stays live while it saves. If the card is
   pulled, the still waits in RAM and is saved when a card comes back. If
   there isn't room in RAM for another still, the press is refused.

Both files are RGB565 BMPs, not JPEGs, because of the bends. The driver
drops any JPEG frame that doesn't start with the bytes `FF D8 FF`, so with one
data line stuck, a JPEG capture times out on every shot. Raw RGB565 has no
framing and comes through bent. The phone app turns them into JPEGs for the
gallery and keeps the BMPs; `just convert` does the same on a laptop.

The camera also looks after itself. A 10 s watchdog resets it if the loop
stalls. After an error it resets, and after 3 crashes in a row without 30 s
of healthy running, it stops and says why on the screen instead of looping.
If frames stop coming, it rebuilds the camera driver, backing off from 4 s to
60 s between tries; if frames keep coming but stop changing, it reports a
frozen picture. Settings from the phone survive power cycles, and holding the
shutter at power-on starts with the defaults.

CircuitPython's `espcamera` wraps Espressif's C driver. Its binding has no
autofocus and no register access, but the driver only holds the I2C bus during
its own calls, so the firmware writes the sensor's clock registers itself
between captures and writes them again after every size change.

## Bends

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

Column 1 is at the right-hand end, as in the render above. For the eight data
lines (D2 to D9), only a cartridge joins A to B. Eight jumper shunts across
columns 1 to 8 make a straight-through cartridge and a normal picture; from
there a cartridge can cross bits over, tie the ESP32's side to 3V3 or GND,
or mix in noise. With no cartridge fitted, the 8x10k resistor network RN1 holds the
ESP32's side low. CART goes to IO14; this firmware doesn't read it yet.

The header mates all 32 pins in whatever order a cartridge rocks in, so swap
cartridges with the power off. Nothing keys it, and a cartridge fitted
backwards or one column over can short two camera outputs. I kept the header
plain on this revision on purpose. The fixes (splitting it into two keyed
2x8 blocks, alignment posts) don't change the pinout, so they can wait for
the next board.

## The circuit board

`pcb/v3/v3.circuit.tsx` describes the mainboard in tscircuit: parts, pin
assignments, traces and silkscreen, on a 100x100 mm two-layer board with
through-hole parts. The netlist and fabrication files are generated from it.

```sh
just pcb-setup        # install tscircuit (bun)
just pcb-build v3     # build it and draw pcb/dist/v3/v3/pcb.png
just pcb-copper v3    # 0 shorts, 0 pad clashes; GND is joined by the pour
just pcb-fab v3       # KiCad DRC, then gerbers and drill files in v3-fab.zip
```

In my run, `just pcb-fab v3` reported 0 errors and 18 warnings, one per
footprint, each saying KiCad's configuration doesn't include the `tscircuit`
footprint library. The footprints are embedded in the exported board, so the
warnings don't affect the gerbers. It needs `kicad-cli`; with the Flatpak
KiCad, clone somewhere under your home directory, since the sandbox can't see
`/tmp`. `pcb/tools/` holds the copper clearance check and the step that
finishes the files for fabrication. `pcb/test00` and the `probe` boards are
earlier test designs.

## Building one

The parts on the v3 board: an ESP32-S3-DevKitC-1 N8R8, Adafruit's OV5640
camera breakout (product 5840), Adafruit's 2.0-inch 320x240 TFT with microSD
(product 4311), a pushbutton, a 4609X-101-103LF resistor network, a 10 uF
capacitor and the 2x16 header. `just pcb-parts` downloads the vendors' board
files.

The firmware gives the camera no clock pin, so the OV5640 breakout has to run
from its own oscillator. Adafruit's breakout has a jumper for that; on EXT
the sensor never answers and looks exactly like a wiring fault.

None of this runs without the board, so I haven't checked these steps in a
clean setup the way I checked the ones above:

```sh
just flash            # write CircuitPython 10.3.0 to the board
just fetch-bundle     # download Adafruit's library bundle
just libs             # copy the one library the firmware needs to the board
just willow           # deploy the runtime
just push src/code.py # deploy the firmware and watch it start
just console          # a serial console
```

`just flash` expects the CircuitPython `.bin` under `vendor/`; download it from
circuitpython.org for the `espressif_esp32s3_devkitc_1_n8r8` board. `just boot`
installs `src/boot.py`, which hides the CIRCUITPY drive at power-on so the
camera can run unplugged; after that, `just devmode` brings the drive back for
one boot. `just bringup <n>` runs one of the bring-up scripts instead of the
firmware. `just --list` shows the rest.

## Learned on the bench

Some of the firmware and tooling only makes sense with what the board taught
me:

- **The sensor clock.** On EXT, the OV5640 never answers on I2C and holds its
  data lines high-impedance, which looks exactly like a wiring fault. Hence
  `external_clock_pin=None` and the INT jumper.
- **Copying to the board.** A plain `cp` to CIRCUITPY while `code.py` runs is
  silently lost, and a host-side compare still says it landed. `just push`
  stops the program at the REPL over serial, writes the file, and checks it
  from the board's side.
- **A failed SD init.** If `sdcardio.SDCard()` fails on a bare pin, the next
  garbage collection crashes. `Card.attach` keeps one `DigitalInOut` for the
  chip select and reuses it.
- **Bluetooth.** With more than one characteristic in a service, a soft reload
  hard-faulted, so each BLE service has one characteristic.
- **Power.** A dip in the supply, from a powered card insert or a bad USB
  cable, browns the board out or drops it off USB with nothing logged.

## About this snapshot

This is a public snapshot, as of October 2026, of a private repo. While the
repo was private, its code comments, docstrings and design notes held personal
details, so I stripped them all rather than edit them one by one; this README
carries the design reasoning instead. Vendored third-party files (Adafruit's
bundle and firmware, the vendors' board files) are left out, and the `just`
recipes fetch them.

Claude wrote this README from my notes and decisions.
