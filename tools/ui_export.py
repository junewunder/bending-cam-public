#!/usr/bin/env python3

import glob
import json
import os
import shutil
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "ui", "ui.aseprite")
OUT = os.path.join(REPO, "src", "ui.bin")
DUMP = os.path.join(REPO, "tools", "ui_dump.lua")

SLOTS = {
    "card": ("saving", "saved", "refused", "failed", "no_card", "full"),
    "signal": ("frozen", "no_signal"),
}

FORWARD, REVERSE, PING_PONG, PING_PONG_REVERSE = range(4)

MAGIC = b"BCUI"
VERSION = 1


def aseprite():
    exe = os.environ.get("ASEPRITE")
    if exe:
        return exe
    found = sorted(glob.glob(os.path.expanduser("~/Applications/aseprite*.appimage")))
    if found:
        return found[-1]
    exe = shutil.which("aseprite")
    if exe:
        return exe
    raise SystemExit("no Aseprite: set ASEPRITE to its binary")


def dump(src):
    r = subprocess.run(
        [aseprite(), "-b", "--script-param", "file=" + src, "--script", DUMP],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    if r.returncode or not lines:
        raise SystemExit("aseprite failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    return json.loads(lines[-1])


def playback(st):
    n = len(st["frames"])
    fwd = list(range(n))
    d = st["dir"]
    if d == REVERSE:
        return fwd[::-1]
    if d == PING_PONG:
        return fwd + fwd[-2:0:-1]
    if d == PING_PONG_REVERSE:
        return fwd[::-1] + fwd[1:-1]
    return fwd


def pack_image(fr, where, errors):
    w, h, x0, y0 = fr["w"], fr["h"], fr["x"], fr["y"]
    rgba = bytes.fromhex(fr["rgba"])
    runs, pix = [], bytearray()
    soft = []
    for y in range(h):
        start = None
        for x in range(w + 1):
            i = (y * w + x) * 4
            a = rgba[i + 3] if x < w else 0
            if a not in (0, 255):
                soft.append((x0 + x, y0 + y))
                a = 255
            if a:
                if start is None:
                    start = x
                r, g, b = rgba[i], rgba[i + 1], rgba[i + 2]
                c = (r >> 3) << 11 | (g >> 2) << 5 | b >> 3
                pix += bytes((c >> 8, c & 0xFF))
            elif start is not None:
                runs.append((x0 + start, y0 + y, x - start))
                start = None
    if soft:
        errors.append("{}: {} pixel(s) partly transparent, first at {}; alpha must be "
                      "on or off".format(where, len(soft), soft[0]))
    return runs, bytes(pix)


def pixels(runs):
    return {(x + i, y) for x, y, n in runs for i in range(n)}


def build(d):
    errors, warnings = [], []
    known = {name: slot for slot, names in SLOTS.items() for name in names}
    for name in d["strays"]:
        errors.append("layer {!r} is at the top level: put it in a slot group, "
                      "or start its name with _ to keep it as a reference".format(name))
    statuses = []
    drawn = {}
    seen = set()
    for st in d["statuses"]:
        where = "{}/{}".format(st["slot"], st["name"])
        if st["slot"] not in SLOTS:
            errors.append("{}: no slot called {!r}; the slots are {}".format(
                where, st["slot"], ", ".join(SLOTS)))
            continue
        if known.get(st["name"]) != st["slot"]:
            errors.append("{}: {} has no status {!r}; its statuses are {}".format(
                where, st["slot"], st["name"], ", ".join(SLOTS[st["slot"]])))
            continue
        if not st["group"]:
            warnings.append("{}: a plain layer, not a group; fine, but a group can hold several".format(where))
        if st["dir"] not in (FORWARD, REVERSE, PING_PONG, PING_PONG_REVERSE):
            errors.append("{}: unknown tag direction {}".format(where, st["dir"]))
            continue
        seen.add(st["name"])

        images, index = [], {}
        steps = []
        for i in playback(st):
            fr = st["frames"][i]
            img = pack_image(fr, "{} frame {}".format(where, fr["frame"]), errors)
            key = (tuple(img[0]), img[1])
            if key not in index:
                index[key] = len(images)
                images.append(img)
                label = "{} frame {}".format(where, fr["frame"])
                for px in pixels(img[0]):
                    drawn.setdefault(st["slot"], {}).setdefault(px, label)
            steps.append((index[key], max(1, fr["ms"])))
        if not st["tagged"] and not images[0][0]:
            warnings.append("{}: nothing drawn; it will show nothing".format(where))
        if len(images) > 255 or len(steps) > 255:
            errors.append("{}: over 255 frames".format(where))
            continue
        statuses.append((st["slot"], st["name"], st["repeats"], images, steps))

    for name, slot in known.items():
        if name not in seen:
            warnings.append("{}/{}: missing; it will show nothing".format(slot, name))

    slots = list(drawn)
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            shared = drawn[a].keys() & drawn[b].keys()
            if shared:
                px = min(shared, key=lambda p: (p[1], p[0]))
                errors.append(
                    "{} and {} both draw pixel {} ({} shared): the slots show at once, "
                    "so their art must not overlap".format(drawn[a][px], drawn[b][px], px, len(shared)))

    out = bytearray(MAGIC)
    out += struct.pack("<BHHB", VERSION, d["width"], d["height"], len(statuses))
    for slot, name, repeats, images, steps in statuses:
        for s in (slot, name):
            out += struct.pack("<B", len(s)) + s.encode()
        out += struct.pack("<BBB", min(repeats, 255), len(images), len(steps))
        for runs, pix in images:
            out += struct.pack("<H", len(runs))
            for run in runs:
                out += struct.pack("<HHH", *run)
            out += pix
        for i, ms in steps:
            out += struct.pack("<BH", i, ms)
    return bytes(out), errors, warnings


def main(argv):
    src = argv[0] if argv else SRC
    out_path = argv[1] if len(argv) > 1 else OUT
    d = dump(src)
    data, errors, warnings = build(d)
    for w in warnings:
        print("warning: " + w)
    for e in errors:
        print("error: " + e, file=sys.stderr)
    if errors:
        raise SystemExit("{} error(s); {} not written".format(len(errors), os.path.relpath(out_path)))
    with open(out_path, "wb") as f:
        f.write(data)
    print("-> {} ({} bytes, {}x{})".format(os.path.relpath(out_path), len(data), d["width"], d["height"]))


if __name__ == "__main__":
    main(sys.argv[1:])
