#!/usr/bin/env python3

import argparse
import difflib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = "/tmp/bendcam-sim"
sys.path.insert(0, HERE)

import fakes  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402


def extract(rev, dest):
    os.makedirs(dest, exist_ok=True)
    for name in ("code.py", "willow.py"):
        path = os.path.join(dest, name)
        if rev == "WORKTREE":
            src = os.path.join(REPO, "src", name)
            data = open(src, "rb").read() if os.path.exists(src) else None
        else:
            r = subprocess.run(["git", "show", "{}:src/{}".format(rev, name)],
                               cwd=REPO, capture_output=True)
            data = r.stdout if r.returncode == 0 else None
        if data is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as f:
                f.write(data)


def run(build, sc):
    sys.modules.pop("willow", None)
    w = fakes.World(sc)
    fakes.REPO_UI = os.path.join(REPO, "src", "ui.bin")
    g = fakes.install(w)
    g["__name__"] = "__main__"
    sys.path.insert(0, build)
    try:
        src = open(os.path.join(build, "code.py")).read()
        exec(compile(src, "code.py", "exec"), g)
        w.add("end: ran out")
    except fakes.Stop:
        w.add("end: stopped")
    except fakes.Reset:
        w.add("end: reset")
    except Exception as err:
        w.add("end: raised", type(err).__name__, err)
    finally:
        sys.path.remove(build)
    return [mask_traceback(ln) for ln in w.trace]


def mask_traceback(line):
    head = "Traceback (most recent call last):"
    if head not in line:
        return line
    line = re.sub(r"^(file write \S+) \d+", r"\1 N", line)
    sep = "\n" if "\n" in line else "\\n"
    parts = line.split(sep)
    i = next(j for j, p in enumerate(parts) if head in p)
    last = [p for p in parts[i + 1 :] if p.strip() and not p.startswith(" ")]
    return sep.join(parts[: i + 1] + ["  ..."] + last[-1:])


KINDS = ("i2c w", "file", "nvm", "ble", "storage", "sdcard", "camera", "print")
LOOSE = re.compile(r"--- frame|panel 2[ab] 4 |panel 2c 153600 |print: .*fps \(|wdt feed")


def by_kind(a, b):
    out = {}
    for k in KINDS:
        sa = [ln for ln in a if ln.startswith(k) and not LOOSE.match(ln)]
        sb = [ln for ln in b if ln.startswith(k) and not LOOSE.match(ln)]
        if sa != sb:
            out[k] = (sa, sb)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", default="main")
    ap.add_argument("--b", default="WORKTREE")
    ap.add_argument("--show", action="store_true", help="print b's traces, no diff")
    ap.add_argument("--by-kind", action="store_true",
                    help="compare each kind of line in order, ignoring frames")
    ap.add_argument("--context", type=int, default=3)
    ap.add_argument("--max", type=int, default=60, help="diff lines shown per scenario")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    names = args.names or list(SCENARIOS)
    for n in names:
        if n not in SCENARIOS:
            raise SystemExit("no scenario {}; have {}".format(n, ", ".join(SCENARIOS)))

    builds = {}
    for side, rev in (("a", args.a), ("b", args.b)):
        if side == "a" and args.show:
            continue
        builds[side] = os.path.join(OUT, side, "build")
        extract(rev, builds[side])

    same = 0
    for n in names:
        traces = {}
        for side, build in builds.items():
            traces[side] = run(build, SCENARIOS[n])
            with open(os.path.join(OUT, side, n + ".txt"), "w") as f:
                f.write("\n".join(traces[side]) + "\n")
        if args.show:
            print("\n".join(traces["b"]))
            continue
        if args.by_kind:
            kinds = by_kind(traces["a"], traces["b"])
            if not kinds:
                same += 1
                print("same  {:14} in order, kind by kind".format(n))
                continue
            print("DIFF  {:14} {}".format(n, ", ".join(kinds)))
            for k, (sa, sb) in kinds.items():
                d = list(difflib.unified_diff(sa, sb, args.a, args.b, n=args.context,
                                              lineterm=""))[2:]
                for line in d[: args.max]:
                    print("      " + line)
            continue
        diff = list(difflib.unified_diff(traces["a"], traces["b"], args.a, args.b,
                                         n=args.context, lineterm=""))
        if not diff:
            same += 1
            print("same  {:14} {} lines, {}".format(n, len(traces["a"]), traces["a"][-1]))
            continue
        print("DIFF  {:14} {} vs {} lines".format(n, len(traces["a"]), len(traces["b"])))
        for line in diff[: args.max]:
            print("      " + line)
        if len(diff) > args.max:
            print("      ... {} more; {}/{{a,b}}/{}.txt".format(len(diff) - args.max, OUT, n))
    if not args.show:
        print("{} of {} scenarios the same".format(same, len(names)))
        sys.exit(0 if same == len(names) else 1)


if __name__ == "__main__":
    main()
