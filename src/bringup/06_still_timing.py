import gc
import os
import struct
import time

import board
import busio
import digitalio
import displayio
import espcamera
import espidf
import sdcardio
import storage
import ulab.numpy as np
from adafruit_st7789 import ST7789
from fourwire import FourWire

CAM_RESET = board.IO21
CAM_PWRDN = board.IO4
CAM_DATA = [board.IO5, board.IO6, board.IO7, board.IO15,
            board.IO16, board.IO17, board.IO18, board.IO8]
CAM_PCLK = board.IO9
CAM_VSYNC = board.IO11
CAM_HREF = board.IO10
CAM_SDA = board.IO12
CAM_SCL = board.IO13
TFT_MISO = board.IO48
SD_CS = board.IO42
TFT_SCK = board.IO47
TFT_MOSI = board.IO38
TFT_CS = board.IO39
TFT_RST = board.IO40
TFT_DC = board.IO41

SPI_BAUD = 40_000_000
PANEL_MADCTL = 0x20
PREVIEW_PLL = (20, 5)
STILL_PLL = (16, 2)
FLIP = True
STILL_DISCARD_FRAMES = 1
STILL_CHUNK_ROWS = 16
SD_BAUD = 24_000_000
BMP_PIXEL_OFFSET = 512
TAKE_TIMEOUT = 2.0

SHOTS = 3
WRITE_CHUNKS = (0, 262_144, 65_536, 16_384)
BAUDS = (10_000_000, 13_333_333, 16_000_000, 20_000_000, 24_000_000,
         26_666_667, 40_000_000)
QUEUE_PROBE_MAX = 6
W, H = 1024, 768
STILL_BYTES = W * H * 2
TMP = "/sd/_probe06.tmp"
OUT = "/sd/_probe06.bmp"


def ms(t):
    return "{:.0f}ms".format(t * 1000)


def heap():
    gc.collect()
    return "largest block {}, free {}".format(
        espidf.heap_caps_get_largest_free_block(), espidf.heap_caps_get_free_size())


def set_pll(mult, div):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(cam.address, bytes((0x30, 0x36, mult)))
        i2c.writeto(cam.address, bytes((0x38, 0x24, div)))
    finally:
        i2c.unlock()


def to_preview():
    cam.reconfigure(frame_size=espcamera.FrameSize.QVGA,
                    pixel_format=espcamera.PixelFormat.RGB565, framebuffer_count=2)
    cam.hmirror = cam.vflip = FLIP
    set_pll(*PREVIEW_PLL)


def to_still():
    cam.reconfigure(frame_size=espcamera.FrameSize.XGA,
                    pixel_format=espcamera.PixelFormat.RGB565, framebuffer_count=1)


def preview(n=10):
    bus.send(0x2A, bytes((0, 0, 0x01, 0x3F)))
    bus.send(0x2B, bytes((0, 0, 0, 0xEF)))
    for _ in range(n):
        f = cam.take(TAKE_TIMEOUT)
        if f is not None:
            bus.send(0x2C, np.frombuffer(f, dtype=np.uint8))


def header():
    return struct.pack(
        "<2sIHHIIiiHHIIiiIIIII", b"BM", BMP_PIXEL_OFFSET + STILL_BYTES, 0, 0,
        BMP_PIXEL_OFFSET, 40, W, H, 1, 16, 3, STILL_BYTES, 2835, 2835, 0, 0,
        0xF800, 0x07E0, 0x001F) + bytes(BMP_PIXEL_OFFSET - 66)


def mount(baud):
    global card
    card = sdcardio.SDCard(spi, sd_cs, baudrate=baud)
    storage.mount(storage.VfsFat(card), "/sd")


def unmount():
    global card
    storage.umount("/sd")
    card.deinit()
    card = None


def readback(path, src):
    chunk = bytearray(65_536)
    mv = memoryview(chunk)
    cnp = np.frombuffer(chunk, dtype=np.uint8)
    with open(path, "rb") as f:
        f.seek(BMP_PIXEL_OFFSET)
        off = 0
        while off < STILL_BYTES:
            n = f.readinto(mv[: min(len(chunk), STILL_BYTES - off)])
            if not n:
                return False
            if not np.all(cnp[:n] == src[off : off + n]):
                print("   mismatch in bytes {}..{}".format(off, off + n))
                return False
            off += n
    return os.stat(path)[6] == BMP_PIXEL_OFFSET + STILL_BYTES


def write_whole(src_bytes, chunk):
    mv = memoryview(src_bytes)
    t0 = time.monotonic()
    with open(TMP, "wb") as f:
        f.write(header())
        if chunk:
            for o in range(0, STILL_BYTES, chunk):
                f.write(mv[o : o + chunk])
        else:
            f.write(mv)
    t1 = time.monotonic()
    try:
        os.remove(OUT)
    except OSError:
        pass
    os.rename(TMP, OUT)
    return t1 - t0, time.monotonic() - t1


def swap_in_place(u8):
    u16 = np.frombuffer(u8, dtype=np.uint16)
    if hasattr(u16, "byteswap"):
        u16.byteswap(inplace=True)
        return "ndarray.byteswap"
    lo = u8[0::2].copy()
    u8[0::2] = u8[1::2]
    u8[1::2] = lo
    return "strided, one half-size temp"


print("bring-up 06 (v3): still timing")
import ulab  # noqa: E402

print("ulab", ulab.__version__, "| byteswap:",
      hasattr(np.frombuffer(bytearray(2), dtype=np.uint16), "byteswap"))

displayio.release_displays()
spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO)
sd_cs = digitalio.DigitalInOut(SD_CS)
card = None
mount(SD_BAUD)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=SPI_BAUD)
display = ST7789(bus, width=320, height=240, rotation=270)
display.auto_refresh = False
display.root_group = None
bus.send(0x36, bytes((PANEL_MADCTL,)))

i2c = busio.I2C(scl=CAM_SCL, sda=CAM_SDA)
cam = espcamera.Camera(
    data_pins=CAM_DATA, pixel_clock_pin=CAM_PCLK, vsync_pin=CAM_VSYNC,
    href_pin=CAM_HREF, i2c=i2c, external_clock_pin=None,
    external_clock_frequency=24_000_000, powerdown_pin=CAM_PWRDN,
    reset_pin=CAM_RESET, pixel_format=espcamera.PixelFormat.RGB565,
    frame_size=espcamera.FrameSize.QVGA, framebuffer_count=2,
    grab_mode=espcamera.GrabMode.LATEST)
cam.hmirror = cam.vflip = FLIP
set_pll(*PREVIEW_PLL)
print("camera up;", heap())
preview(60)

try:
    print("\n== A: code.py's path, {} shots".format(SHOTS))
    for shot in range(SHOTS):
        preview()
        t = [time.monotonic()]
        to_still()
        t.append(time.monotonic())
        cam.hmirror = cam.vflip = FLIP
        set_pll(*STILL_PLL)
        t.append(time.monotonic())
        for _ in range(STILL_DISCARD_FRAMES):
            cam.take(TAKE_TIMEOUT)
        t.append(time.monotonic())
        buf = cam.take(TAKE_TIMEOUT)
        t.append(time.monotonic())
        if buf is None:
            print("!! still timed out")
            to_preview()
            continue
        src = np.frombuffer(buf, dtype=np.uint8)
        row = W * 2
        cb = row * STILL_CHUNK_ROWS
        out = bytearray(cb)
        onp = np.frombuffer(out, dtype=np.uint8)
        swap_s = write_s = 0.0
        t_open = time.monotonic()
        with open(TMP, "wb") as f:
            f.write(header())
            for off in range(0, STILL_BYTES, cb):
                a = time.monotonic()
                onp[0::2] = src[off + 1 : off + cb : 2]
                onp[1::2] = src[off : off + cb : 2]
                b = time.monotonic()
                f.write(out)
                write_s += time.monotonic() - b
                swap_s += b - a
        t_closed = time.monotonic()
        try:
            os.remove(OUT)
        except OSError:
            pass
        os.rename(TMP, OUT)
        t.append(time.monotonic())
        src = buf = out = onp = None
        to_preview()
        t.append(time.monotonic())
        print("shot {}: reconfigure {}, orient+pll {}, discard {}, take {} | "
              "swap {}, write {}, open/close/other {}, rename {} | back {} | total {}".format(
                  shot, ms(t[1] - t[0]), ms(t[2] - t[1]), ms(t[3] - t[2]),
                  ms(t[4] - t[3]), ms(swap_s), ms(write_s),
                  ms(t_closed - t_open - swap_s - write_s), ms(t[5] - t_closed),
                  ms(t[6] - t[5]), ms(t[6] - t[0])))

    print("\n== B/C: copy out of the driver, whole-still swap, big writes")
    preview()
    print("before still:", heap())
    to_still()
    cam.hmirror = cam.vflip = FLIP
    set_pll(*STILL_PLL)
    for _ in range(STILL_DISCARD_FRAMES):
        cam.take(TAKE_TIMEOUT)
    buf = cam.take(TAKE_TIMEOUT)
    if buf is None:
        raise RuntimeError("no still frame within TAKE_TIMEOUT")
    print("still in the driver:", heap())
    src = memoryview(buf).cast("B")
    t0 = time.monotonic()
    copy = bytearray(STILL_BYTES)
    t1 = time.monotonic()
    copy[:] = src
    t2 = time.monotonic()
    ref = bytearray(copy)
    rnp = np.frombuffer(ref, dtype=np.uint8)
    t3 = time.monotonic()
    rnp[0::2] = np.frombuffer(buf, dtype=np.uint8)[1::2]
    rnp[1::2] = np.frombuffer(buf, dtype=np.uint8)[0::2]
    t4 = time.monotonic()
    print("alloc {}, memcpy out of the Bitmap {}, bytearray(copy) {}, ulab copy+swap {}".format(
        ms(t1 - t0), ms(t2 - t1), ms(t3 - t2), ms(t4 - t3)))
    ref = rnp
    cnp = np.frombuffer(copy, dtype=np.uint8)
    src = buf = None
    t4 = time.monotonic()
    to_preview()
    print("back to preview in {} holding 2 copies:".format(ms(time.monotonic() - t4)), heap())
    preview()
    t5 = time.monotonic()
    how = swap_in_place(cnp)
    print("in-place swap ({}): {}".format(how, ms(time.monotonic() - t5)))
    print("  equals copy+swap:", bool(np.all(cnp == ref)))
    for sl in (65_536, 262_144):
        t5 = time.monotonic()
        for o in range(0, STILL_BYTES, sl):
            np.frombuffer(copy, dtype=np.uint16, offset=o, count=sl // 2).byteswap(inplace=True)
        a = time.monotonic() - t5
        for o in range(0, STILL_BYTES, sl):
            np.frombuffer(copy, dtype=np.uint16, offset=o, count=sl // 2).byteswap(inplace=True)
        print("  swap in {} B slices: {} ({} each), round trip exact: {}".format(
            sl, ms(a), ms(a * sl / STILL_BYTES), bool(np.all(cnp == ref))))
    for chunk in WRITE_CHUNKS:
        w, r = write_whole(copy, chunk)
        ok = readback(OUT, ref)
        print("write in {}: {} + rename {}, {:.0f} KB/s, read-back {}".format(
            "one call" if not chunk else "{} B".format(chunk), ms(w), ms(r),
            STILL_BYTES / w / 1024, "matches" if ok else "!! MISMATCH"))
        preview(3)
    ref = None

    held = []
    try:
        while len(held) < QUEUE_PROBE_MAX:
            held.append(bytearray(STILL_BYTES))
    except MemoryError:
        pass
    print("queue: {} more XGA buffers fit beside the preview and this copy;".format(len(held)),
          heap())
    held = None
    preview()
    print("preview after holding them: ok")

    print("\n== D: SD_BAUD sweep, whole still in one write")
    ref = cnp
    for baud in BAUDS:
        unmount()
        try:
            mount(baud)
        except OSError as err:
            print("{:>10}: won't mount: {}".format(baud, err))
            continue
        w, _ = write_whole(copy, 0)
        t = time.monotonic()
        ok = readback(OUT, ref)
        r = time.monotonic() - t
        print("{:>10}: write {} ({:.0f} KB/s), read+compare {}, {}".format(
            baud, ms(w), STILL_BYTES / w / 1024, ms(r), "matches" if ok else "!! MISMATCH"))
        preview(3)
    unmount()
    mount(SD_BAUD)
finally:
    for p in (TMP, OUT):
        try:
            os.remove(p)
        except OSError:
            pass

print("\ndone. preview continues; push code.py back when finished.")
while True:
    preview(30)
