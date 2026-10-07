#!/usr/bin/env python3

import base64
import glob
import os
import subprocess
import sys
import time

from push_code import park

CHUNK = 384
TIMEOUT = 300

SD_PINS = {
    "espressif_esp32s3_devkitc_1_n8r8": ("IO47", "IO38", "IO48", "IO42"),
}
SD_BAUD = 24_000_000


def run_on_board(script, timeout=TIMEOUT, stop_at=b"\nEND\r\n"):
    ports = sorted(glob.glob("/dev/ttyACM*"))
    if not ports:
        raise SystemExit("no /dev/ttyACM* -- is the board plugged in?")
    port = os.environ.get("PORT") or ports[-1]

    subprocess.run(
        ["stty", "-F", port, "115200", "raw", "-echo", "clocal", "hupcl"], check=True
    )

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    def write_all(data):
        deadline = time.time() + 30
        while data:
            try:
                data = data[os.write(fd, data) :]
            except BlockingIOError:
                if time.time() > deadline:
                    raise
                time.sleep(0.02)

    try:
        park(fd)

        write_all(b"\x05")
        time.sleep(0.2)
        for line in script.splitlines():
            write_all(line.encode() + b"\r\n")
        write_all(b"\x04")

        buf = b""
        started = time.time()
        first_byte = None
        while time.time() - started < timeout:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                chunk = b""
            if chunk:
                buf += chunk
                if first_byte is None and b"BEGIN" in buf:
                    first_byte = time.time()
                if stop_at in buf:
                    break
            else:
                time.sleep(0.005)
    finally:
        try:
            write_all(b"\x04")
        except OSError:
            pass
        os.close(fd)
    return buf.decode(errors="replace"), (first_byte or started)


def extract(text):
    if "BEGIN\r\n" not in text or "END" not in text:
        print("transfer did not complete. Board said:\n", file=sys.stderr)
        print(text[-800:], file=sys.stderr)
        raise SystemExit(1)
    i = text.index("BEGIN\r\n") + len("BEGIN\r\n")
    j = text.find("\r\nEND\r\n", i - 2)
    if j < 0:
        raise SystemExit("no END line in the board's output")
    return text[i:j]


REMOUNT = """
import os, board, busio, sdcardio, storage
_pins = %r.get(board.board_id)
if _pins is None:
    print("!! no SD pins known for board", board.board_id)
elif os.statvfs("/sd")[2] == os.statvfs("/")[2]:
    try:
        _spi = busio.SPI(clock=getattr(board, _pins[0]), MOSI=getattr(board, _pins[1]), MISO=getattr(board, _pins[2]))
        _card = sdcardio.SDCard(_spi, getattr(board, _pins[3]), baudrate=%d)
        storage.mount(storage.VfsFat(_card), "/sd")
    except Exception as _e:
        print("!! could not mount the card:", _e)
""" % (SD_PINS, SD_BAUD)

LS = """
import os
print("BEG" + "IN")
try:
    names = sorted(os.listdir({0!r}))
except OSError as e:
    names = None
    print("cannot list {0}: {{}}".format(e))
if names is not None and not names:
    print("(empty)")
for name in names or []:
    try:
        print("{{:>9}}  {{}}".format(os.stat({0!r} + "/" + name)[6], name))
    except OSError as e:
        print("        ?  {{}}".format(name))
print("E" + "ND")
"""

CAT = """
import binascii
f = open({!r}, "rb")
print("BEG" + "IN")
while True:
    b = f.read({})
    if not b:
        break
    print(binascii.b2a_base64(b).decode().strip())
f.close()
print("E" + "ND")
"""


def main():
    args = sys.argv[1:]

    if len(args) == 2 and args[0] == "--ls":
        text, _ = run_on_board(REMOUNT + LS.format(args[1]), timeout=30)
        listing = extract(text).strip()
        print(listing if listing else "(empty)")
        return 0

    if len(args) != 2:
        print(__doc__.strip())
        return 2

    remote, local = args
    text, t0 = run_on_board(REMOUNT + CAT.format(remote, CHUNK))
    payload = b""
    for line in extract(text).replace("\r", "").split("\n"):
        line = line.strip()
        if line:
            payload += base64.b64decode(line)

    with open(local, "wb") as f:
        f.write(payload)

    secs = time.time() - t0
    print(
        "{} -> {}: {} bytes in {:.1f}s ({:.1f} KB/s)".format(
            remote, local, len(payload), secs, len(payload) / 1024 / max(secs, 1e-3)
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
