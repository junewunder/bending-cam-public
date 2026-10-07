#!/usr/bin/env python3

import argparse
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fakes  # noqa: E402
import run  # noqa: E402

KEYS = {
    "shift": [True, False, 2, "x"],
    "exposure": [0, 1, 2, 3, -1],
    "ev": [-6, 0, 6, 9, -100, 1.5],
    "exposure_value": [0, 15, 30, 31],
    "iso": [100, 400, 1550, 99, 2000],
    "wb": [0, 1, 2, 5, 6, 7],
    "wb_r": [256, 1024, 3072, 5000],
    "wb_g": [256, 1024, 3072],
    "wb_b": [256, 2000, 3072],
    "nope": [1],
}
REVIEW = ['{"review":"enter"}', '{"review":"next"}', '{"review":"prev"}',
          '{"review":"next","by":3}', '{"review":"prev","by":-2}', '{"review":"exit"}',
          json.dumps({"review": "send", "files": ["IMG_{:04d}{}.bmp".format(n, s)
                                                   for n in range(1, 13) for s in ("", "_screen")]}),
          '{"review":"send","files":7}', '{"review":"zoom"}']


def scenario(seed):
    r = random.Random(seed)
    frames = r.randrange(150, 700)
    at = {}
    then = {}

    def put(f, act):
        at.setdefault(f, []).append(act)

    card = r.random() > 0.1
    connected = False
    inserted = card
    for f in range(frames):
        x = r.random()
        if x < 0.02:
            put(f, "press")
        elif x < 0.025 and f + 1 < frames:
            put(f, "press")
            put(f + 1, "press")
        elif x < 0.03:
            put(f, "pull" if inserted else "insert")
            inserted = not inserted
        elif x < 0.04:
            put(f, "disconnect" if connected else "connect")
            connected = not connected
        elif x < 0.055:
            k = r.choice(list(KEYS))
            put(f, 'write {}'.format(json.dumps({"k": k, "v": r.choice(KEYS[k])})))
        elif x < 0.06:
            put(f, "write " + r.choice(REVIEW))
        elif x < 0.07:
            put(f, "connect")
            connected = True
            put(f, 'write {"review":"enter"}')
            t = 0.0
            for _ in range(r.randrange(1, 10)):
                t += r.choice((0.05, 0.3, 1.0, 5.0))
                act = r.choice(["write " + REVIEW[-3]] * 3 + ["write " + r.choice(REVIEW)] * 5
                               + ["press", "pull", "insert", "disconnect"])
                then.setdefault(f, []).append((t, act))
        elif x < 0.073:
            put(f, 'write {"get":"all"}')
        elif x < 0.075:
            put(f, "boot")
        elif x < 0.077:
            put(f, r.choice(["skip on", "skip off"]))
        elif x < 0.078:
            put(f, "ram {}".format(r.choice((100_000, 2_000_000, 4_000_000))))
        elif x < 0.0785:
            put(f, 'write {"reset":"all"}')
        elif x < 0.079:
            put(f, "write not json")
    sc: dict = dict(frames=frames, at=at, then=then, card=card)
    if r.random() < 0.2:
        a = r.randrange(frames)
        sc["miss"] = [(a, a + r.randrange(2, 30))]
    if r.random() < 0.1:
        a = r.randrange(frames)
        sc["frozen"] = [(a, a + r.randrange(5, 60))]
    if r.random() < 0.1:
        sc["capacity"] = r.choice((200_000, 2_000_000, 5_000_000))
    return sc


def execute(build, sc):
    sys.modules.pop("willow", None)
    w = fakes.World(sc)
    fakes.REPO_UI = os.path.join(run.REPO, "src", "ui.bin")
    g = fakes.install(w)
    g["__name__"] = "__main__"
    sys.path.insert(0, build)
    try:
        exec(compile(open(os.path.join(build, "code.py")).read(), "code.py", "exec"), g)
        w.add("end: ran out")
    except fakes.Stop:
        w.add("end: stopped")
    except fakes.Reset:
        w.add("end: reset")
    except Exception as err:
        w.add("end: raised", type(err).__name__, err)
    finally:
        sys.path.remove(build)
    w.app = g.get("app")
    return w


SHOT = re.compile(r"IMG_(\d+)(_screen)?\.bmp$")
STILL_SIZE = 512 + 1024 * 768 * 2
SCREEN_SIZE = 512 + 320 * 240 * 2


def check(w):
    bad = []
    tr = w.trace
    if tr[-1] != "end: stopped":
        bad.append("run ended: " + tr[-1])
    if w.preview < w.sc["frames"]:
        bad.append("took {} of {} frames".format(w.preview, w.sc["frames"]))
    for ln in tr:
        if "Traceback" in ln or "!! crash" in ln:
            bad.append("crashed: " + ln[:200])
            break
    if w.wdt_gap > 10.0:
        bad.append("watchdog unfed for {:.1f}s".format(w.wdt_gap))
    seen = set()
    last = 0
    for ln in tr:
        m = re.match(r"file rename \S+ (/sd/\S+)$", ln)
        if not m:
            continue
        name = m.group(1)
        if name in seen:
            bad.append("written twice: " + name)
        seen.add(name)
        s = SHOT.search(name)
        if s and s.group(2):
            n = int(s.group(1))
            if n <= last:
                bad.append("shot {} after shot {}".format(n, last))
            last = n
    captured = [int(n) for n in re.findall(r"print: captured shot (\d+)", "\n".join(tr))]
    text = "\n".join(tr)
    for n in captured:
        name = "IMG_{:04d}.bmp".format(n)
        if ("saved /sd/" + name) in text or ("/sd/" + name + " lost") in text:
            continue
        if "stills not written" in text:
            continue
        bad.append("shot {}'s still neither saved nor lost".format(n))
    for name, data in w.card.files.items():
        s = SHOT.search(name)
        if s:
            want = SCREEN_SIZE if s.group(2) else STILL_SIZE
            if len(data) != want:
                bad.append("{} is {} bytes, not {}".format(name, len(data), want))
    for ln in tr:
        if ln.startswith("ble settings "):
            body = ln[len("ble settings "):]
            if not body:
                continue
            try:
                if type(json.loads(body)) is not dict:
                    raise ValueError
            except ValueError:
                bad.append("phone line not a JSON object: " + body[:80])
            if len(body) + 2 > 244:
                bad.append("phone line over 244 bytes: " + body[:80])
    owed = {}
    for ln in tr:
        m = re.match(r"print: saved /sd/(\S+) ", ln)
        if m:
            owed[m.group(1)] = 1
        elif ln.startswith("ble settings ") and '"queued":[' in ln:
            for name in json.loads(ln[len("ble settings "):])["queued"]:
                owed[name] = 1
        else:
            m = re.match(r"print: ble: sent /sd/(\S+) ", ln)
            if m:
                name = m.group(1)
                if owed.get(name, 0) < 1:
                    bad.append("sent again unasked: " + name)
                owed[name] = owed.get(name, 0) - 1
    for m in re.finditer(r"print: ble: sent (\S+) \((\d+) bytes\)", text):
        name = m.group(1).rsplit("/", 1)[-1]
        if name in w.card.files and len(w.card.files[name]) != int(m.group(2)):
            bad.append("sent {} as {} bytes, card has {}".format(
                name, m.group(2), len(w.card.files[name])))
    app = w.app
    ob = app and getattr(app, "outbox", None)
    if ob:
        for q, what in ((ob.queue, "queue"), (ob.aside, "aside")):
            dup = {p for p in q if q.count(p) > 1}
            if dup:
                bad.append("outbox {} holds twice: {}".format(what, sorted(dup)))
        both = set(ob.queue) & set(ob.aside)
        if both:
            bad.append("queued and set aside: {}".format(sorted(both)))
        for p in ob.queue + ob.aside:
            if p.rsplit("/", 1)[-1] not in w.card.files:
                bad.append("outbox holds {}, not on the card".format(p))
    if app:
        for label, ls in app._w_root.listeners.items():
            if len(ls) > 2 * 8:
                bad.append("{} listeners on {}".format(len(ls) // 2, label))
    open_ = False
    for i, ln in enumerate(tr):
        if ln == "print: review: open":
            open_ = True
        elif ln.startswith("print: review: closed"):
            open_ = False
        elif open_ and ln.startswith("--- frame"):
            bad.append("a frame taken during review")
            break
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", default="WORKTREE")
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    fakes.MAX_SLEEP_S = 2000
    build = os.path.join(run.OUT, "fuzz", "build")
    run.extract(args.build, build)
    seeds = [args.seed] if args.seed is not None else range(args.first, args.first + args.seeds)
    failed = 0
    for seed in seeds:
        sc = scenario(seed)
        w = execute(build, sc)
        bad = check(w)
        if args.show:
            print(json.dumps(sc, indent=1))
            print("\n".join(run.mask_traceback(ln) for ln in w.trace))
        if bad:
            failed += 1
            print("FAIL seed {}: {}".format(seed, "; ".join(bad[:4])))
    print("{} of {} seeds failed".format(failed, len(seeds)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
