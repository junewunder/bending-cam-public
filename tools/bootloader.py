#!/usr/bin/env python3

import subprocess
import sys
import time

from push_code import opened, park, paste_unanswered

REQUEST = (
    "import microcontroller\n"
    "microcontroller.on_next_reset(microcontroller.RunMode.BOOTLOADER)\n"
    "microcontroller.reset()\n"
)


def main():
    fd = opened()
    park(fd)
    paste_unanswered(fd, REQUEST)
    print("asked the board for download mode; waiting for the ROM loader's port...")

    deadline = time.time() + 20
    while time.time() < deadline:
        r = subprocess.run(["just", "_download_port"], capture_output=True, text=True)
        if r.returncode == 0:
            print("-> %s" % r.stdout.strip())
            print("   now: just flash")
            return 0
        time.sleep(1)

    print(
        "no download-mode port after 20s.\n"
        "Fall back to the buttons: hold BOOT, tap RST, release BOOT.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
