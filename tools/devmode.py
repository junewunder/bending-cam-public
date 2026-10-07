#!/usr/bin/env python3

import os
import subprocess
import time

from push_code import HARD_RESET, REPO, opened, park, paste_unanswered

WAIT_S = 40


def mounted():
    r = subprocess.run(["just", "_drive"], cwd=REPO, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    d = mounted()
    if d:
        print("already in dev mode: CIRCUITPY at", d)
        return
    fd = opened()
    park(fd)
    paste_unanswered(fd, HARD_RESET)
    try:
        os.close(fd)
    except OSError:
        pass
    print("reset; waiting for CIRCUITPY...")
    for _ in range(WAIT_S):
        time.sleep(1)
        d = mounted()
        if d:
            print("-> dev mode: CIRCUITPY at", d)
            return
    raise SystemExit(
        "CIRCUITPY did not appear within %ds. Is src/boot.py on the board the "
        "current one? Without serial: press reset twice for safe mode, which skips "
        "boot.py." % WAIT_S
    )


if __name__ == "__main__":
    main()
