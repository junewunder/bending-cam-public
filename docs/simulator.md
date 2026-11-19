# The simulator and the fuzzer

Back to the [README](../README.md).

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
frame to the next on purpose, `--by-kind` compares sensor writes, card files,
nvm, Bluetooth, camera calls and prints, each kind in order on its own. It
leaves out the frame markers, the panel and the watchdog, so a `same` from
`--by-kind` says nothing about what was drawn.

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
