#!/usr/bin/env python3

import argparse
import errno
import glob
import os
import subprocess
import sys
import termios
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = "/dev/sda1"


def port():
    ports = sorted(glob.glob("/dev/ttyACM*"))
    if not ports:
        raise SystemExit("no /dev/ttyACM* -- is the board plugged in?")
    p = os.environ.get("PORT") or ports[-1]
    subprocess.run(
        ["stty", "-F", p, "115200", "raw", "-echo", "clocal", "hupcl"], check=True
    )
    return p


def opened():
    return os.open(port(), os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)


def write_all(fd, data):
    deadline = time.time() + 30
    while data:
        try:
            data = data[os.write(fd, data) :]
        except BlockingIOError:
            if time.time() > deadline:
                raise
            time.sleep(0.02)


PARK_TIMEOUT = 30
PARK_QUIET_S = 5
PARK_SETTLE_S = 0.5


def park(fd):
    termios.tcflush(fd, termios.TCIFLUSH)
    write_all(fd, b"\x03")
    buf = b""
    end = time.time() + PARK_TIMEOUT
    heard = time.time()
    while time.time() < end:
        try:
            d = os.read(fd, 65536)
        except BlockingIOError:
            d = b""
        if d:
            buf += d
            heard = time.time()
            if b"any key" in buf:
                buf = b""
                write_all(fd, b"\x03")
        elif buf.rstrip(b" ").endswith(b">>>"):
            if time.time() - heard > PARK_SETTLE_S:
                return
            time.sleep(0.05)
        elif time.time() - heard > PARK_QUIET_S:
            heard = time.time()
            write_all(fd, b"\x03")
        else:
            time.sleep(0.05)
    print("!! no REPL prompt after %ds; carrying on" % PARK_TIMEOUT, file=sys.stderr)


def run_on_board(fd, script, timeout=30):
    write_all(fd, b"\x05")
    time.sleep(0.2)
    for line in (script + '\nprint("<<" + "DONE>>")').splitlines():
        write_all(fd, line.encode() + b"\r\n")
    write_all(fd, b"\x04")
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            d = os.read(fd, 65536)
        except OSError as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
            time.sleep(0.05)
            continue
        if d:
            buf += d
            if b"<<DONE>>" in buf:
                break
    out = buf.decode("utf-8", "replace")
    if "<<DONE>>" not in out:
        raise SystemExit("board did not answer:\n" + out[-800:])
    return out


def paste_unanswered(fd, script):
    write_all(fd, b"\x05")
    time.sleep(0.2)
    for line in script.splitlines():
        write_all(fd, line.encode() + b"\r\n")
    write_all(fd, b"\x04")


NVM_DEV_ONCE = 0x96
DEV_ONCE = 0xD5
HARD_RESET = (
    "import microcontroller\n"
    "microcontroller.nvm[%d] = %d\n"
    "microcontroller.reset()\n" % (NVM_DEV_ONCE, DEV_ONCE)
)


def drive():
    r = subprocess.run(
        ["just", "_drive"], cwd=REPO, capture_output=True, text=True
    )
    if r.returncode:
        raise SystemExit("no CIRCUITPY: " + r.stderr.strip())
    return r.stdout.strip()


def push(fd, src, name="code.py"):
    data = open(src, "rb").read()
    dest = os.path.join(drive(), name)
    park(fd)
    subprocess.run(["cp", src, dest], check=True)
    subprocess.run(["sync"], check=True)
    subprocess.run(
        ["udisksctl", "unmount", "-b", DEV], capture_output=True, text=True
    )
    time.sleep(1)

    out = run_on_board(
        fd,
        'import os\n'
        '_d = open("/%s","rb").read()\n'
        'print("BOARD_SIZE", len(_d))\n'
        'print("BOARD_SUM", sum(_d) & 0xFFFFFFFF)' % name,
    )

    def pick(tag):
        vals = [
            line.split()[-1]
            for line in out.splitlines()
            if line.strip().startswith(tag) and line.split()[-1].isdigit()
        ]
        if not vals:
            raise SystemExit("no %s in board output:\n%s" % (tag, out[-600:]))
        return int(vals[-1])

    got = (pick("BOARD_SIZE"), pick("BOARD_SUM"))
    want = (len(data), sum(data) & 0xFFFFFFFF)
    if got != want:
        raise SystemExit(
            "VERIFY FAILED -- board has %s, host sent %s.\n"
            "The copy was lost. Is the board really at the REPL?" % (got, want)
        )
    print("-> %s verified on the board: %d bytes, checksum %d" % (name, *got))


def follow(fd, seconds, log=None, soft_reboot=True):
    if soft_reboot:
        write_all(fd, b"\x04")
    end = time.time() + seconds
    out = open(log, "wb", buffering=0) if log else None
    while time.time() < end:
        try:
            d = os.read(fd, 65536)
            if not d:
                raise OSError(errno.EIO, "tty hung up")
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                time.sleep(0.05)
                continue
            try:
                os.close(fd)
            except OSError:
                pass
            time.sleep(0.5)
            try:
                fd = opened()
            except (SystemExit, OSError, subprocess.CalledProcessError):
                continue
            sys.stdout.write("\n--- [reattached after reset] ---\n")
            continue
        sys.stdout.write(d.decode("utf-8", "replace"))
        sys.stdout.flush()
        if out:
            out.write(d)
    if out:
        out.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", help="the file to deploy")
    ap.add_argument("--as", dest="name", default="code.py",
                    help="name to land under on the drive (default code.py)")
    ap.add_argument("--reset", action="store_true",
                    help="hard-reset afterwards. settings.toml is read once at "
                         "boot, so a soft reload will NOT pick it up.")
    ap.add_argument("--follow", type=float, default=30.0,
                    help="seconds of console to capture after Ctrl-D (0 = none)")
    ap.add_argument("--log", default=None, help="also write the console to this file")
    args = ap.parse_args()

    fd = opened()
    push(fd, args.src, args.name)
    if args.reset:
        print("--- hard reset (so settings.toml is re-read) ---")
        paste_unanswered(fd, HARD_RESET)
        time.sleep(3)
        try:
            os.close(fd)
        except OSError:
            pass
        for _ in range(20):
            try:
                fd = opened()
                break
            except (SystemExit, OSError, subprocess.CalledProcessError):
                time.sleep(0.5)
        else:
            raise SystemExit("board never came back after the reset")
    if args.follow > 0:
        print("--- running, %gs of console ---" % args.follow)
        follow(fd, args.follow, args.log, soft_reboot=not args.reset)
    drive()


if __name__ == "__main__":
    main()
