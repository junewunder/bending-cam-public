# bendcam

bendcam is a digital camera I designed and built to be glitched on purpose.

<p>
  <img src="docs/photo-plants.jpg" width="39%" alt="Garden plants in purple, magenta and acid yellow">
  <img src="docs/photo-butterfly.jpg" width="39%" alt="A butterfly sculpture washed out to pale green">
  <img src="docs/photo-tree.jpg" width="20%" alt="A tree stump in pink with patches of blue and green">
</p>

*Three photos from the camera. Nothing was edited afterwards; all three were
taken through the same bend cartridge.*

<p>
  <img src="docs/camera-front.jpg" width="49%" alt="The camera from the front: a black circuit board with a screen, a shutter button and a microcontroller board">
  <img src="docs/camera-back.jpg" width="49%" alt="The camera from the back, with the camera module showing through a cut-out">
</p>

*The camera. On the front are the screen, the shutter button (top right), the
microcontroller on its own small board (bottom), and between them the
cartridge header, the two rows of black sockets, shown here with no cartridge
fitted. The camera module looks out of the back.*

One of these cameras exists. Its circuit board is called v3 here, and it
works: it shows a live preview, takes photos, saves them to a
microSD card and sends them to a phone over Bluetooth. This repo is a snapshot
of everything that went into it, not a kit.

## How a bend works

Circuit bending is rewiring a cheap electronic device so that it misbehaves in
ways you like. With a camera, that normally means opening one up and soldering
onto its board.

In this camera the bend is part of the design. The camera module sends each
pixel to the microcontroller over eight wires, the data lines, one bit on
each. On the v3 board those eight wires don't go straight across. Each one
stops at the cartridge header and starts again on the other side, and only a
cartridge, a small plug-in board, joins the two halves. So the cartridge
decides what the microcontroller sees, nothing is soldered, and a bend comes
out when the cartridge does.

The cartridge that took the photos above is a DIP switch, a row of eight
small switches, one per data line. A closed switch passes its line through. An
open one cuts it, a resistor on the board holds the microcontroller's side
low, and that bit reads 0 in every pixel. Different switch settings give
different pictures.

The header has 16 columns of two pins: row A goes to the camera module, row B
to the microcontroller.

| Column | 1-8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|
| Signal | D2-D9 | PCLK | HREF | VSYNC | GND | SDA | SCL | 3V3 | CART |
| A and B joined on the board | no | yes | yes | yes | yes | yes | yes | yes | yes |

Columns 1 to 8 are the data lines, and column 1 is at the right-hand end in
the photo. Eight jumpers across them make a straight-through cartridge and a
normal picture. A cartridge can also cross two lines over, or tie the
microcontroller's side of a line to power or ground. The other columns carry
timing, power and control signals, which the board joins itself. Swap
cartridges with the power off: nothing keys the header, and a cartridge
fitted one column over can short two of the camera module's outputs.

There is one bend in software too, a setting called `shift`. It draws each
frame starting one byte late, so every pixel's two bytes are read across the
boundary with its neighbour. The colour comes out in hard bands and the
brightness mostly survives, so the picture stays readable. It changes the
screen and the small copy of each photo, not the full-size one.

Photos are saved as raw bitmaps, not JPEGs, because of the bends. The camera
driver throws away any JPEG frame that doesn't start with the right three
bytes, so with one data line cut, a JPEG capture times out on every shot. A
raw frame has no framing to break and comes through bent. The phone app turns
the bitmaps into JPEGs for the gallery.

## How I built it

I had bent cameras before, and stopped because I got bored with the photos:
whichever camera I bought online, I got the same kind of result. A camera
built for bending, where I choose what happens to the data, was the way out,
and for a long time it looked like more than I had time for. This is the first
circuit board I've made.

I built bendcam by directing AI coding agents. They wrote the code; I decided
what the camera should do, tried it on the bench, and chose what got checked
and how. Writing code got cheap that way, but reviewing it didn't, so the
checks are where I put my own work: a simulator that runs the camera's
software on a laptop against fake hardware, a fuzzer, and lint and type checks
on the camera's software and the phone app.

The checks run on a laptop, and some things only the board could teach me:

- The camera module's clock. The module has a jumper for where its clock
  comes from. On the wrong setting it never answers and leaves its data lines
  floating, which looks exactly like a wiring fault.
- Copying to the board. A plain file copy while the camera's program is
  running is silently lost, and comparing the files from the laptop still says
  it landed. `just push` stops the program, writes the file, and checks it
  from the board's side.
- A failed SD card start. If the card fails to start, the board crashes at
  the next garbage collection, unless the firmware keeps hold of the card's
  select pin itself. So it keeps one pin object and reuses it.
- Bluetooth. A Bluetooth service with more than one value in it crashed the
  board when the program reloaded, so each service has one.
- Power. A dip in the supply, from pushing a card in or from a bad USB cable,
  resets the board or drops it off USB with nothing logged.

## What's in the repo

| Part | What it does | Where | Lines |
|---|---|---|---|
| Firmware | The camera's own software: preview, shutter, saving, settings, Bluetooth, crash recovery | `src/code.py` | 2,613 |
| Runtime | The small event and state library the firmware is written on | `src/willow.py` | 457 |
| Bring-up scripts | One test per hardware stage, for a new board | `src/bringup/` | 972 |
| Simulator, fuzzer, tests | Fake hardware, scripted runs, random runs, the runtime's tests | `tools/sim/` | 1,477 |
| Phone app | Settings, photo transfer and review over Bluetooth, for Android | `phone/` | 3,730 |
| Circuit board | The v3 board written as code, earlier test boards, fabrication tools | `pcb/` | 1,753 |
| Host tools | Deploying to the board, Bluetooth from a laptop, bitmap to JPEG | `tools/`, `justfile` | 1,852 |

The firmware is Python (CircuitPython) on an ESP32-S3 microcontroller. Three
longer documents hold the detail:

- [docs/simulator.md](docs/simulator.md): how the simulator and the fuzzer
  work, and what they can't see.
- [docs/firmware.md](docs/firmware.md): how the firmware is put together,
  what happens when you press the shutter, and where to start reading the
  code.
- [docs/building.md](docs/building.md): the circuit board, the parts, and
  getting the firmware onto a board.

## Try it without the camera

You need [just](https://github.com/casey/just), Python 3.9 or newer, and
[uv](https://docs.astral.sh/uv/) for the checks. These are the results on my
laptop:

```sh
just sim      # 18 of 18 scenarios the same, in under 2 s
just fuzz     # 0 of 200 seeds failed, in about 25 s
just dev      # once: a .venv with the type stubs for this board
just check    # ruff: All checks passed; pyright: 0 errors
just test     # 13 tests of the runtime, OK
```

`just sim` takes two versions of the firmware, the `main` branch and your
working copy by default, and runs each one on the laptop against fake
hardware. It records every call that would have reached real hardware: what
was drawn on the screen, what was written to the card, what was sent over
Bluetooth. Each version goes through 18 scenarios, and a scenario is a script
of events: shutter presses, the card pulled out in the middle of a save, a
full card, a phone connecting and dropping. Then it compares the two
recordings. A refactor should come back `same` on all 18, and a change in
behaviour shows up as a difference to explain.

`just fuzz` builds a random scenario per seed and checks each run against
rules, with no second version to compare to: nothing crashes, no file is
written twice, shot numbers only go up, every photo taken is either saved or
reported lost.

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
$ just fuzz --seeds 150
FAIL seed 149: written twice: /sd/IMG_0001_screen.bmp; shot 1 after shot 1; ...
120 of 150 seeds failed
```

The fuzzer only checks its rules. When I made the counter never advance at
all, no shot was ever taken, nothing broke a rule, and 0 of 150 seeds failed;
`just sim` flagged 13 of 18 scenarios.

The fake hardware was written from the same understanding of the real
hardware as the firmware was. So `same` means two versions behave alike
against the fakes, not that either is right on the board. Crashes inside the
microcontroller, memory running short, and real radio and card timing still
need the camera.

## Building one

The parts on the v3 board are an ESP32-S3-DevKitC-1 N8R8 (the
microcontroller board), Adafruit's OV5640 camera breakout (the camera module,
product 5840), Adafruit's 2.0-inch 320x240 screen with a microSD slot
(product 4311), a pushbutton, an 8x10k resistor network, a 10 uF capacitor
and the 2x16 header. All of it is through-hole, on a 100x100 mm two-layer
board.

The board is written as code in `pcb/v3/v3.circuit.tsx`, and the files a
board factory needs are generated from it.
[docs/building.md](docs/building.md) has those commands, the steps to put the
firmware on a board, and the tests to run on a new board one stage at a time.

What a stranger doesn't get here: there are no design files for a cartridge
and no parts prices, and I haven't run the firmware steps on a second board.

## About this snapshot

This is a public snapshot, as of October 2026, of a private repo. While the
repo was private, its code comments and design notes held personal details,
so I stripped them all rather than edit them one by one; this README and the
three documents in `docs/` carry the design reasoning. Third-party files
(Adafruit's libraries and firmware, the vendors' board files) are left out,
and the `just` recipes fetch them.

Claude wrote this README from my notes and decisions.
