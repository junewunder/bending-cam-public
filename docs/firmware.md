# The firmware

Back to the [README](../README.md).

If you have five minutes for the code, these are the places to look:

- `src/code.py`, `Main.run()` at line 2435: the camera's main loop.
- `src/willow.py`, `flush()` at line 372 and `tick()` at line 454: the order a
  tick runs in.
- `tools/sim/run.py`: the trace diff, and `by_kind` for changes that move
  work between frames.
- `tools/sim/fuzz.py`, `check()` at line 126: the rules every random run must
  keep.

`src/code.py` is a tree of components (`Shutter`, `Saver`, `Card`, `Panel`,
`Camera`, `Look`, `Link`, `Outbox`, `Settings`, `Review`) on
`src/willow.py`, a small runtime based on Willow, a reactive programming model
from my research that isn't published yet. Components don't call their
siblings; they talk through events and state:

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

`just test` runs 13 unit tests of these rules against `src/willow.py` on
CPython. If you know React, the batching will look familiar: setters land at
the next render, as `setState` does. `emit` is closer to the DOM's
`dispatchEvent`, which also runs its listeners before it returns.

Hardware handles come in through each component's `open()`, which is what
lets the simulator swap the hardware out. `Main` builds the tree and wires the
handles, and its loop, `Main.run()`, is the one place that calls components
directly: it schedules the work that shares a frame, the SPI bus and the
radio, in the order the hardware needs. Not everything is state. What the
hardware is doing right now (the open SD card, the presses waiting, whether
the panel needs re-anchoring) lives in plain fields that `Main.run()` and the
components read and write directly, because a value that lands a tick late is
a frame late.

The board's pins are at the top of `src/code.py`, and its settings, the ones
the phone shows, are in the `SETTINGS` table below them. The `shift` bend is
`Panel.shift()` and the blit around it.

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

The camera also looks after itself. A 10 s watchdog resets it if the main
loop stalls; it's armed at the end of boot, so a hang while the drivers start
isn't covered. After an error it resets, and after 3 crashes in a row without
30 s of healthy running, it stops and says why on the screen instead of
looping.
If frames stop coming, it rebuilds the camera driver, backing off from 4 s to
60 s between tries; if frames keep coming but stop changing, it reports a
frozen picture. Settings from the phone survive power cycles, and holding the
shutter at power-on starts with the defaults.

CircuitPython's `espcamera` wraps Espressif's C driver. Its binding has no
autofocus and no register access, but the driver only holds the I2C bus during
its own calls, so the firmware writes the sensor's clock registers itself
between captures and writes them again after every size change.

## Learned on the bench

Parts of the firmware and tooling come from things the board taught me:

- The sensor clock. On EXT, the OV5640 never answers on I2C and holds its
  data lines high-impedance, which looks exactly like a wiring fault. Hence
  `external_clock_pin=None` and the INT jumper.
- Copying to the board. A plain `cp` to CIRCUITPY while `code.py` runs is
  silently lost, and a host-side compare still says it landed. `just push`
  stops the program at the REPL over serial, writes the file, and checks it
  from the board's side.
- A failed SD init. If `sdcardio.SDCard()` fails on a bare pin, the next
  garbage collection crashes. `Card.attach` keeps one `DigitalInOut` for the
  chip select and reuses it.
- Bluetooth. With more than one characteristic in a service, a soft reload
  hard-faulted, so each BLE service has one characteristic.
- Power. A dip in the supply, from a powered card insert or a bad USB
  cable, browns the board out or drops it off USB with nothing logged.
