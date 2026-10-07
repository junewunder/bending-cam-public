import gc
import json
import math
import os
import struct
import time

import microcontroller
import micropython
import supervisor
from watchdog import WatchDogMode

microcontroller.watchdog.mode = None

import _bleio  # noqa: E402 - everything slow comes after the disarm above
import analogio  # noqa: E402
import board  # noqa: E402
import busio  # noqa: E402
import digitalio  # noqa: E402
import displayio  # noqa: E402
import espcamera  # noqa: E402
import espidf  # noqa: E402
import keypad  # noqa: E402
import sdcardio  # noqa: E402
import storage  # noqa: E402
import traceback  # noqa: E402
import ulab.numpy as np  # noqa: E402
from adafruit_st7789 import ST7789  # noqa: E402
from fourwire import FourWire  # noqa: E402
from willow import Component, comp, create, emit, on, prop, ref, state, tick  # noqa: E402

CAM_RESET = board.IO21
CAM_PWRDN = board.IO4
CAM_DATA = [
    board.IO5,
    board.IO6,
    board.IO7,
    board.IO15,
    board.IO16,
    board.IO17,
    board.IO18,
    board.IO8,
]
SHUTTER = board.IO1
BOOT_BUTTON = board.IO0
CAM_PCLK = board.IO9
CAM_VSYNC = board.IO11
CAM_HREF = board.IO10
CAM_SDA = board.IO12
CAM_SCL = board.IO13
KNOB = board.IO2

TFT_MISO = board.IO48
SD_CS = board.IO42
TFT_SCK = board.IO47
TFT_MOSI = board.IO38
TFT_CS = board.IO39
TFT_RST = board.IO40
TFT_DC = board.IO41

PANEL_W = 320
PANEL_H = 240
ROTATION = 270

PANEL_MADCTL = 0x20

UI_FLIP_Y = True

SPI_BAUD = 40_000_000

XCLK_HZ = 24_000_000
FRAME_SIZE = espcamera.FrameSize.QVGA
PREVIEW_W = 320
PREVIEW_H = 240
TAKE_TIMEOUT = 2.0

FRAMEBUFFER_COUNT = 2

SENSOR_PLL_MULT = 20
SENSOR_PCLK_DIV = 5

FLIP_X = True
FLIP_Y = True

STILL_LOCK = True
LOCK_SETTLE_FRAMES = 30
SHUTTER_THIRDS = 30
EXPOSURE_MODES = ["auto", "lock", "manual"]
WB_MODES = ["auto", "lock", "sun", "cloud", "office", "home", "manual"]
WB_PRESETS = {
    "sun": (0x5E0, 0x410, 0x540),
    "cloud": (0x650, 0x410, 0x4F0),
    "office": (0x520, 0x410, 0x660),
    "home": (0x420, 0x3F0, 0x710),
}

KNOB_ON = False
KNOB_SETTING = "ev"
KNOB_HYSTERESIS = 0.3
KNOB_SMOOTH = 0.25

SETTINGS = (
    {"k": "shift", "label": "Byte shift", "kind": "bool", "group": "Bends",
     "when": "live", "default": False},
    {"k": "exposure", "label": "Exposure", "kind": "enum", "group": "Exposure",
     "when": "live", "opts": EXPOSURE_MODES, "default": 0},
    {"k": "ev", "label": "Bias (auto), 1/3 stops", "kind": "int", "group": "Exposure",
     "when": "live", "min": -6, "max": 6, "needs": {"exposure": [0]}, "default": 0},
    {"k": "exposure_value", "label": "Shutter (manual), 1/3 stops", "kind": "int",
     "group": "Exposure", "when": "live", "min": 0, "max": SHUTTER_THIRDS,
     "needs": {"exposure": [2]}, "default": SHUTTER_THIRDS},
    {"k": "iso", "label": "ISO (manual)", "kind": "int", "group": "Exposure",
     "when": "live", "min": 100, "max": 1550, "step": 50, "needs": {"exposure": [2]},
     "default": 400},
    {"k": "wb", "label": "White balance", "kind": "enum", "group": "White balance",
     "when": "live", "opts": WB_MODES, "default": 0},
    {"k": "wb_r", "label": "Red (manual), 1024 = 1x", "kind": "int",
     "group": "White balance", "when": "live", "min": 256, "max": 3072, "step": 32,
     "needs": {"wb": [6]}, "default": 1024},
    {"k": "wb_g", "label": "Green (manual), 1024 = 1x", "kind": "int",
     "group": "White balance", "when": "live", "min": 256, "max": 3072, "step": 32,
     "needs": {"wb": [6]}, "default": 1024},
    {"k": "wb_b", "label": "Blue (manual), 1024 = 1x", "kind": "int",
     "group": "White balance", "when": "live", "min": 256, "max": 3072, "step": 32,
     "needs": {"wb": [6]}, "default": 1024},
)
ROWS = {row["k"]: row for row in SETTINGS}
SETTINGS_PROTO = 1
SETTINGS_SAVE_S = 3.0
SETTINGS_LINE_MAX = 244
LIVE_S = 2.0

DROUGHT_MISSES = 3
REBUILD_BACKOFF_S = 4.0
REBUILD_BACKOFF_MAX_S = 60.0
DROUGHT_SAVE_S = 0.5

SHUTTER_SCAN_S = 0.020
SHUTTER_DEBOUNCE = 2
SHUTTER_STALE_S = 2.0

STILL_SCREEN_SUFFIX = "_screen"
STILL_SIZE = espcamera.FrameSize.XGA
STILL_BYTES = 1024 * 768 * 2
STILL_PLL = (16, 2)
STILL_HEAP_MARGIN = 16_384
STILL_DISCARD_FRAMES = 1

BMP_PIXEL_OFFSET = 512
SAVE_SLICE_BYTES = 32_768

SD_BAUD = 24_000_000
SD_MOUNT = "/sd"
STILL_PREFIX = "IMG_"
STILL_TMP = "/sd/_partial.tmp"
SCREEN_TMP = "/sd/_screen.tmp"
SD_UNSTICK_BAUD = 400_000
SD_UNSTICK_S = 1.0
SD_RETRY_S = 5.0
_ENOSPC = 28
_EACCES = 13
_ENOENT = 2
_TICKS_MASK = (1 << 29) - 1

UI_PATH = "/ui.bin"
SLOT_CARD = "card"
SLOT_SIGNAL = "signal"
STATUS_SAVING = "saving"
STATUS_REFUSED = "refused"
STATUS_SAVED = "saved"
STATUS_FAILED = "failed"
STATUS_NO_CARD = "no_card"
STATUS_FULL = "full"
STATUS_FROZEN = "frozen"
STATUS_NO_SIGNAL = "no_signal"
STATUS_FLASH_S = 1.0
STATUS_FAILED_S = 3.0
UI_HOLD_FRAMES = 3
BENCH_UI = False
BENCH_HOLD_S = 6.0
BENCH_AUTO = False
BENCH_PRESS_ROUNDS = 30

BLE_LINK = True
BLE_SEND = True
BLE_NAME = b"bendcam"
BLE_UUID_FMT = "b3c1{:04x}-5eed-4a11-8c4e-6c0ffee00001"
BLE_WINDOW = 8
BLE_ACK_WAIT_S = 0.25

REVIEW_IDLE_S = 120.0
REVIEW_TICK_S = 0.02

WATCHDOG_TIMEOUT = 10.0
BOOTLOOP_LIMIT = 3
HEALTHY_S = 30
LOG_PATH = "/sd/log.txt"

FROZEN_TAPS = 32
FROZEN_FRAMES = 20

_NVM_BASE = 0x80
_NVM_MAGIC = b"\xbc\x03"
_OFF_BOOTS = 2
_OFF_CRASHES = 3
_OFF_BOOTLOOP = 4
_OFF_SAFE_NEW = 5
_OFF_SAFE_REASON = 6
_NVM_LEN = 22
_NVM_DEV_ONCE = 0x96
_DEV_ONCE = 0xD5
_NVM_SETTINGS = 0x400
_NVM_SETTINGS_LEN = 0x400
_SETTINGS_MAGIC = b"\xbc\x5e"

_CASET = 0x2A
_RASET = 0x2B
_RAMWR = 0x2C
_MADCTL = 0x36

_SC_PLL_CTRL2 = 0x3036
_PCLK_RATIO = 0x3824
_AEC_EXPOSURE = 0x3500
_AEC_GAIN = 0x350A
_AEC_MANUAL = 0x3503
_AWB_GAINS = 0x3400
_AWB_MANUAL = 0x3406
_AEC_TARGETS = (0x3A0F, 0x3A10, 0x3A11, 0x3A1B, 0x3A1E, 0x3A1F)
_SC_PLL_CTRL0 = 0x3034
_SC_SCLK = 0x3108
_TIMING_HTS = 0x380C
_TIMING_VTS = 0x380E


def make_display(spi):
    bus = FourWire(
        spi,
        command=TFT_DC,
        chip_select=TFT_CS,
        reset=TFT_RST,
        baudrate=SPI_BAUD,
    )
    display = ST7789(bus, width=PANEL_W, height=PANEL_H, rotation=ROTATION)
    display.auto_refresh = False
    display.root_group = None
    bus.send(_MADCTL, bytes((PANEL_MADCTL,)))
    return display, bus


def make_camera(i2c):
    cam = espcamera.Camera(
        data_pins=CAM_DATA,
        pixel_clock_pin=CAM_PCLK,
        vsync_pin=CAM_VSYNC,
        href_pin=CAM_HREF,
        i2c=i2c,
        external_clock_pin=None,
        external_clock_frequency=XCLK_HZ,
        powerdown_pin=CAM_PWRDN,
        reset_pin=CAM_RESET,
        pixel_format=espcamera.PixelFormat.RGB565,
        frame_size=FRAME_SIZE,
        framebuffer_count=FRAMEBUFFER_COUNT,
        grab_mode=espcamera.GrabMode.LATEST,
    )
    set_orientation(cam)
    set_preview_pll(i2c, cam)
    return cam


def reset_sensor():
    pin = digitalio.DigitalInOut(CAM_RESET)
    try:
        pin.switch_to_output(value=False)
        time.sleep(0.05)
        pin.value = True
        time.sleep(0.05)
    finally:
        pin.deinit()


def set_orientation(cam):
    cam.hmirror = FLIP_X
    cam.vflip = FLIP_Y


def set_preview_pll(i2c, cam):
    set_pll(i2c, cam, SENSOR_PLL_MULT, SENSOR_PCLK_DIV)


def set_pll(i2c, cam, mult, pclk_div):
    sensor_write(i2c, cam.address, _SC_PLL_CTRL2, mult)
    sensor_write(i2c, cam.address, _PCLK_RATIO, pclk_div)


def sensor_write(i2c, addr, reg, value):
    if not i2c.try_lock():
        raise RuntimeError("camera I2C bus is locked")
    try:
        i2c.writeto(addr, bytes((reg >> 8, reg & 0xFF, value)))
    finally:
        i2c.unlock()


def sensor_read(i2c, addr, reg, n):
    buf = bytearray(n)
    if not i2c.try_lock():
        raise RuntimeError("camera I2C bus is locked")
    try:
        i2c.writeto_then_readfrom(addr, bytes((reg >> 8, reg & 0xFF)), buf)
    finally:
        i2c.unlock()
    return buf


def set_window(bus, x0, y0, x1, y1):
    bus.send(_CASET, bytes((x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)))
    bus.send(_RASET, bytes((y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)))


def unstick_sd(spi, cs):
    one = bytearray(1)
    ff = b"\xff"
    while not spi.try_lock():
        pass
    try:
        spi.configure(baudrate=SD_UNSTICK_BAUD)
        cs.switch_to_output(value=False)
        t0 = time.monotonic()
        polls = 0
        while time.monotonic() - t0 < SD_UNSTICK_S:
            spi.write_readinto(ff, one)
            polls += 1
            if one[0] == 0xFF:
                break
        cs.value = True
        spi.write(ff * 16)
        if polls > 1:
            print("sd: busy for {} polls, last 0x{:02x}".format(polls, one[0]))
    finally:
        spi.unlock()


def sd_answers(spi, cs):
    r = bytearray(8)
    while not spi.try_lock():
        pass
    try:
        spi.configure(baudrate=SD_UNSTICK_BAUD)
        cs.value = False
        spi.write(b"\x40\x00\x00\x00\x00\x95")
        spi.readinto(r, write_value=0xFF)
        cs.value = True
        spi.write(b"\xff")
    finally:
        spi.unlock()
    return any(b != 0xFF for b in r)


def bmp_header(w, h):
    if w * 2 % 4:
        raise ValueError("odd capture width {}: BMP row padding unhandled".format(w))
    pixel_bytes = w * h * 2
    offset = BMP_PIXEL_OFFSET
    return struct.pack(
        "<2sIHHIIiiHHIIiiIIIII",
        b"BM",
        offset + pixel_bytes,
        0,
        0,
        offset,
        40,
        w,
        h,
        1,
        16,
        3,
        pixel_bytes,
        2835,
        2835,
        0,
        0,
        0xF800,
        0x07E0,
        0x001F,
    ) + bytes(BMP_PIXEL_OFFSET - 66)


def bmp_order(buf):
    np.frombuffer(buf, dtype=np.uint16).byteswap(inplace=True)


def shot_number(name):
    if not (name.startswith(STILL_PREFIX) and name.endswith(".bmp")):
        return 0
    rest = name[len(STILL_PREFIX) :]
    i = 0
    while i < len(rest) and rest[i].isdigit():
        i += 1
    return int(rest[:i]) if i else 0


def scan_still_seq():
    return max([shot_number(name) for name in os.listdir(SD_MOUNT)] + [0])


def still_path(n, suffix=""):
    return "{}/{}{:04d}{}.bmp".format(SD_MOUNT, STILL_PREFIX, n, suffix)


def remove_temps():
    for tmp in (SCREEN_TMP, STILL_TMP):
        try:
            os.remove(tmp)
        except OSError:
            pass


def load_ui(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:4] != b"BCUI" or d[4] != 1:
        raise ValueError("{} is not a version-1 ui.bin: re-run `just ui`".format(path))
    w, h, count = struct.unpack_from("<HHB", d, 5)
    if (w, h) != (PANEL_W, PANEL_H) or (w, h) != (PREVIEW_W, PREVIEW_H):
        raise ValueError("{} is {}x{}; it must match the panel and the preview".format(path, w, h))
    o = 10
    art = {}
    for _ in range(count):
        o += 1 + d[o]
        name = str(d[o + 1 : o + 1 + d[o]], "ascii")
        o += 1 + d[o]
        repeats, n_images, n_steps = d[o], d[o + 1], d[o + 2]
        o += 3
        images = []
        for _ in range(n_images):
            (n_runs,) = struct.unpack_from("<H", d, o)
            o += 2
            spans = []
            for _ in range(n_runs):
                x, y, n = struct.unpack_from("<HHH", d, o)
                o += 6
                if UI_FLIP_Y:
                    y = PANEL_H - 1 - y
                spans.append((x, y, n * 2))
            size = sum(s[2] for s in spans)
            pix = memoryview(d)[o : o + size]
            under = memoryview(bytearray(size))
            o += size
            runs = []
            po = 0
            for x, y, nb in spans:
                vo = (y * PREVIEW_W + x) * 2
                runs.append((x, y, nb, vo, vo + nb, under[po : po + nb], pix[po : po + nb]))
                po += nb
            images.append(runs or None)
        steps = []
        for _ in range(n_steps):
            steps.append(images[d[o]])
            o += 3
        art[name] = (steps, repeats)
    return art


def shutter_held():
    pin = digitalio.DigitalInOut(SHUTTER)
    try:
        pin.switch_to_input(pull=digitalio.Pull.UP)
        for _ in range(SHUTTER_DEBOUNCE + 2):
            if pin.value:
                return False
            time.sleep(SHUTTER_SCAN_S)
        return True
    finally:
        pin.deinit()


nvm = microcontroller.nvm
HAVE_NVM = nvm is not None and len(nvm) >= _NVM_BASE + _NVM_LEN


def nvm_load():
    st = bytearray(nvm[_NVM_BASE : _NVM_BASE + _NVM_LEN])
    if st[:2] != _NVM_MAGIC:
        st = bytearray(_NVM_MAGIC) + bytearray(_NVM_LEN - 2)
    return st


def nvm_store(st):
    nvm[_NVM_BASE : _NVM_BASE + _NVM_LEN] = st


def fold_boot():
    reset = microcontroller.cpu.reset_reason
    run = supervisor.runtime.run_reason
    line = "boot: reset {}, run {}".format(
        str(reset).split(".")[-1], str(run).split(".")[-1])
    if not HAVE_NVM:
        return line + ", no nvm: crashes are not counted", 0
    st = nvm_load()
    cold = run == supervisor.RunReason.STARTUP
    if cold and reset == microcontroller.ResetReason.WATCHDOG:
        st[_OFF_CRASHES] = (st[_OFF_CRASHES] + 1) & 0xFF
        st[_OFF_BOOTLOOP] = min(st[_OFF_BOOTLOOP] + 1, 0xFF)
        line = "!! watchdog reset\n" + line
    elif not (cold and reset == microcontroller.ResetReason.SOFTWARE):
        st[_OFF_BOOTLOOP] = 0
    safe = bytes(st[_OFF_SAFE_REASON : _OFF_SAFE_REASON + 16]).rstrip(b"\0")
    if st[_OFF_SAFE_NEW]:
        line = "!! came back from safe mode: {}\n".format(safe.decode()) + line
        st[_OFF_SAFE_NEW] = 0
    st[_OFF_BOOTS] = (st[_OFF_BOOTS] + 1) & 0xFF
    nvm_store(st)
    line += ", boot {}, crashes {} ({} in a row), last safe mode {}".format(
        st[_OFF_BOOTS], st[_OFF_CRASHES], st[_OFF_BOOTLOOP],
        safe.decode() if safe else "none")
    return line, st[_OFF_BOOTLOOP]


def note_crash():
    if not HAVE_NVM:
        return BOOTLOOP_LIMIT
    st = nvm_load()
    st[_OFF_CRASHES] = (st[_OFF_CRASHES] + 1) & 0xFF
    st[_OFF_BOOTLOOP] = min(st[_OFF_BOOTLOOP] + 1, 0xFF)
    nvm_store(st)
    return st[_OFF_BOOTLOOP]


def reset():
    if nvm is not None and storage.getmount("/").readonly:
        nvm[_NVM_DEV_ONCE] = _DEV_ONCE
    microcontroller.reset()


def note_healthy():
    if not HAVE_NVM:
        return
    st = nvm_load()
    if st[_OFF_BOOTLOOP]:
        st[_OFF_BOOTLOOP] = 0
        nvm_store(st)


def append_log(text):
    if app is None or app.card.sd is None:
        return
    try:
        with open(LOG_PATH, "a") as f:
            f.write(text + "\n")
    except OSError as err:
        print("!! {} not written: {}".format(LOG_PATH, err))


class Watchdog:

    def __init__(self):
        self.armed = False
        self.on = False

    def set(self, on):
        if on and self.armed and not self.on:
            microcontroller.watchdog.timeout = WATCHDOG_TIMEOUT
            microcontroller.watchdog.mode = WatchDogMode.RESET
            self.on = True
        elif not on and self.on:
            microcontroller.watchdog.mode = None
            self.on = False

    def feed(self):
        if self.on:
            microcontroller.watchdog.feed()


wdt = Watchdog()


def halt(text):
    wdt.set(False)
    displayio.release_displays()
    try:
        panel = ST7789(
            FourWire((app and app.spi) or busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO),
                     command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST,
                     baudrate=SPI_BAUD),
            width=PANEL_W, height=PANEL_H, rotation=ROTATION)
        panel.root_group = displayio.CIRCUITPYTHON_TERMINAL
    except Exception as err:
        print("!! no panel for the error: {}: {}".format(type(err).__name__, err))
    print(text)
    try:
        while True:
            time.sleep(1)
    finally:
        displayio.release_displays()


def nearest(k, x):
    row = ROWS[k]
    lo, hi, step = row["min"], row["max"], row.get("step", 1)
    v = min(hi, max(lo, lo + round((x - lo) / step) * step))
    return lo + (v - lo) // step * step


class Settings(Component):

    values = ref(lambda: {row["k"]: row["default"] for row in SETTINGS
                          if row["kind"] != "action"})
    connected = prop()
    keep = ref(lambda: False)
    char = ref(lambda: None)
    link = ref(lambda: None)
    read_live = ref(lambda: dict)
    mine = ref(lambda: b"")
    up = ref(lambda: False)
    out = ref(lambda: [])
    dump = ref(lambda: [])
    dirty = ref(lambda: False)
    shown = ref(lambda: {})
    note = ref(lambda: "")

    @on()
    def listen(self):
        self.bind("settings:save", self.save)
        self.bind("settings:live", self.send_live)
        self.bind("setting", self.asked)
        self.bind("settings:reply", self.reply)

    @on("connected")
    def link_changed(self):
        if self.connected:
            self.after(0, "settings:live")
            return
        self.cancel("settings:live")
        if self.up:
            self.lost()

    def open(self, defaults_only):
        for row in SETTINGS:
            for k, vs in row.get("needs", {}).items():
                if k not in self.values or any(self.check(k, v) != (v, None) for v in vs):
                    raise ValueError("settings: {} needs {} = {}".format(row["k"], k, vs))
        self.keep = defaults_only
        if defaults_only:
            self.note = "settings: shutter held at boot, all at defaults; the saved ones are kept"
            print(self.note)
            return
        for k, v in self.stored().items():
            if k in self.values:
                v, err = self.check(k, v)
                if err:
                    print("!! settings: saved {} ignored: {}".format(k, err))
                else:
                    self.values[k] = v
        changed = [k for k in self.values if self.values[k] != ROWS[k]["default"]]
        self.note = "settings: {} changed from default: {}".format(
            len(changed), ", ".join(changed) or "none")
        print(self.note)

    def line(self, k):
        row = ROWS[k]
        d = {n: row[n] for n in row if n != "default"}
        if k in self.values:
            d["v"] = self.values[k]
        return d

    def encode(self, d):
        b = json.dumps(d, separators=(",", ":")).encode() + b"\r\n"
        if len(b) > SETTINGS_LINE_MAX:
            raise ValueError("settings line over {} bytes: {}".format(SETTINGS_LINE_MAX, b))
        return b

    def check(self, k, v):
        row = ROWS[k]
        kind = row["kind"]
        if kind == "bool":
            if v in (0, 1):
                return bool(v), None
        elif type(v) is int:
            if kind == "enum":
                if 0 <= v < len(row["opts"]):
                    return v, None
                return self.values[k], "no option {}".format(v)
            if kind == "int":
                lo, hi = row["min"], row["max"]
                step = row.get("step", 1)
                v = min(hi, max(lo, v))
                return lo + (v - lo) // step * step, None
        return self.values[k], "not a {}: {}".format(kind, v)

    def active(self, k):
        for n, vs in ROWS[k].get("needs", {}).items():
            if self.values[n] not in vs:
                return False
        return True

    def send_live(self, _):
        if not self.connected:
            return
        if self.dump:
            self.after(0, "settings:live")
            return
        self.after(LIVE_S, "settings:live")
        for k, x in self.read_live().items():
            if k in ROWS and not self.active(k):
                v = nearest(k, x)
                if self.shown.get(k) != v:
                    self.shown[k] = v
                    self.out.append({"k": k, "live": v})

    def attach(self, link, read_live):
        self.link = link
        self.read_live = read_live
        C = _bleio.Characteristic
        self.char = C.add_to_service(
            _bleio.Service(_bleio.UUID(BLE_UUID_FMT.format(5))),
            _bleio.UUID(BLE_UUID_FMT.format(6)),
            properties=C.WRITE | C.WRITE_NO_RESPONSE | C.NOTIFY,
            read_perm=_bleio.Attribute.OPEN, write_perm=_bleio.Attribute.OPEN,
            max_length=512, fixed_length=False)
        for row in SETTINGS:
            self.encode(self.line(row["k"]))

    def sending(self):
        return bool(self.out or self.dump)

    def pump(self, lines=1):
        if self.char and self.link.adapter.connected:
            try:
                self.up = True
                self.receive()
                self.send(lines)
            except (IndexError, ConnectionError, _bleio.BluetoothError):
                self.lost()

    def lost(self):
        self.up = False
        self.shown.clear()
        self.out.clear()
        self.dump.clear()
        self.char.value = self.mine = b""

    def receive(self):
        v = bytes(self.char.value or b"")
        if v == self.mine:
            return
        self.mine = v
        for msg in v.split(b"\n"):
            if not msg.strip():
                continue
            try:
                d = json.loads(msg)
                if type(d) is not dict:
                    raise ValueError("not an object")
            except ValueError as err:
                print("!! settings: bad message {}: {}".format(msg[:40], err))
                self.out.append({"err": "bad message"})
                continue
            self.handle(d)
        if not self.sending():
            self.out.append({})

    def reply(self, d):
        if self.up:
            self.out.append(d)

    def handle(self, d):
        if "review" in d:
            self.emit("review", d)
            return
        if d.get("get") == "all":
            self.dump = [None] + [row["k"] for row in SETTINGS] + [len(SETTINGS)]
            return
        if d.get("reset") == "all":
            for k, row in ROWS.items():
                if k in self.values:
                    self.change(k, row["default"])
            return
        k = d.get("k")
        if type(k) is not str or k not in ROWS:
            self.out.append({"k": k, "err": "no such setting"})
            return
        if ROWS[k]["kind"] == "action":
            print("settings: {}".format(k))
            self.emit("action:" + k)
            self.out.append({"k": k})
            return
        if "v" not in d:
            self.out.append({"k": k, "v": self.values[k], "err": "no value"})
            return
        self.change(k, d["v"])

    def asked(self, kv):
        self.change(kv[0], kv[1])

    def change(self, k, v):
        v, err = self.check(k, v)
        echo = {"k": k, "v": v}
        if err:
            echo["err"] = err
        if self.up:
            self.out.append(echo)
        if err or v == self.values[k]:
            return
        self.values[k] = v
        print("settings: {} = {}".format(k, v))
        self.emit("setting:changed", k)
        self.dirty = True
        self.cancel("settings:save")
        self.after(SETTINGS_SAVE_S, "settings:save")
        if self.connected:
            self.cancel("settings:live")
            self.after(0, "settings:live")

    def send(self, lines):
        for _ in range(lines):
            if self.out:
                d = self.out.pop(0)
            elif self.dump:
                k = self.dump.pop(0)
                if k is None:
                    d = {"proto": SETTINGS_PROTO}
                elif type(k) is int:
                    d = {"end": k}
                else:
                    d = self.line(k)
            else:
                return
            b = self.encode(d)
            size = self.link.adapter.connections[0].max_packet_length
            for i in range(0, len(b), size):
                self.char.value = self.mine = b[i : i + size]

    def stored(self):
        if nvm is None or len(nvm) < _NVM_SETTINGS + _NVM_SETTINGS_LEN:
            return {}
        head = bytes(nvm[_NVM_SETTINGS : _NVM_SETTINGS + 4])
        if head[:2] != _SETTINGS_MAGIC:
            return {}
        n = struct.unpack("<H", head[2:])[0]
        try:
            d = json.loads(bytes(nvm[_NVM_SETTINGS + 4 : _NVM_SETTINGS + 4 + n]))
        except ValueError as err:
            print("!! settings: saved copy unreadable, using defaults: {}".format(err))
            return {}
        return d if type(d) is dict else {}

    def save(self, _=None):
        self.dirty = False
        if self.keep:
            print("settings: not saved -- this boot is on defaults (shutter held)")
            return
        if nvm is None or len(nvm) < _NVM_SETTINGS + _NVM_SETTINGS_LEN:
            print("!! settings: no nvm, changes last until reset")
            return
        body = json.dumps(self.values, separators=(",", ":")).encode()
        blob = _SETTINGS_MAGIC + struct.pack("<H", len(body)) + body
        if len(blob) > _NVM_SETTINGS_LEN:
            print("!! settings: {} bytes won't fit nvm's {}; not saved".format(
                len(blob), _NVM_SETTINGS_LEN))
            return
        if bytes(nvm[_NVM_SETTINGS : _NVM_SETTINGS + len(blob)]) == blob:
            return
        nvm[_NVM_SETTINGS : _NVM_SETTINGS + len(blob)] = blob
        print("settings: saved to nvm")

    def close(self):
        if self.dirty:
            self.save()


class Shutter(Component):

    KEYS = ("shutter", "boot")

    keys = ref(lambda: None)
    event = ref(lambda: keypad.Event())
    presses = ref(lambda: [])

    def open(self):
        self.keys = keypad.Keys((SHUTTER, BOOT_BUTTON), value_when_pressed=False, pull=True,
                                interval=SHUTTER_SCAN_S, debounce_threshold=SHUTTER_DEBOUNCE)

    @on()
    def listen(self):
        self.bind("shutter", self.pressed)

    def pressed(self, t):
        self.presses.append(t)

    def poll(self):
        ev = self.event
        lost = self.keys.events.overflowed
        while self.keys.events.get_into(ev):
            if ev.pressed and not emit(self.app, self.KEYS[ev.key_number], ev.timestamp):
                lost = True
        if lost:
            self.keys.events.clear()
            print("!! shutter queue overflowed: presses lost")
            self.emit("keys:lost")

    def refuse_stale(self):
        now = supervisor.ticks_ms()
        limit = int(SHUTTER_STALE_S * 1000)
        fresh = [t for t in self.presses if (now - t) & _TICKS_MASK <= limit]
        stale = len(self.presses) - len(fresh)
        if stale:
            self.presses[:] = fresh
            print("!! {} press(es) refused: waited over {:.1f}s".format(stale, SHUTTER_STALE_S))
            self.emit("press:refused")


class Saver(Component):

    queue = ref(lambda: [])
    card = ref(lambda: None)
    f = ref(lambda: None)
    off = ref(lambda: 0)
    t0 = ref(lambda: 0.0)

    def open(self, card):
        self.card = card

    @on()
    def listen(self):
        self.bind("still:captured", self.captured)
        self.bind("card:going", self.drop)
        self.bind("card:full", self.drop)
        self.bind("card:remounted", self.remounted)

    def captured(self, still):
        n, buf, w, h, t0 = still
        self.queue.append([still_path(n), buf, w, h, False])
        print("captured shot {} in {:.2f}s, {} pending".format(
            n, time.monotonic() - t0, len(self.queue)))

    def remounted(self, _):
        print("sd remounted, {} stills pending".format(len(self.queue)))

    def reserve(self):
        gc.collect()
        try:
            buf = bytearray(STILL_BYTES)
        except MemoryError:
            buf = None
        largest = espidf.heap_caps_get_largest_free_block()
        if buf is None or largest < STILL_BYTES + STILL_HEAP_MARGIN:
            print("!! press refused: {} stills pending, largest block {}".format(
                len(self.queue), largest))
            return None
        return buf

    def write_now(self, path, frame, shifted):
        raw = memoryview(frame).cast("B")
        n = len(raw)
        buf = bytearray(n)
        if shifted:
            buf[: n - 2] = raw[1 : n - 1]
        else:
            buf[:] = raw
        bmp_order(buf)
        t0 = time.monotonic()
        with open(SCREEN_TMP, "wb") as f:
            f.write(bmp_header(frame.width, frame.height))
            f.write(buf)
            size = f.tell()
        os.rename(SCREEN_TMP, path)
        return time.monotonic() - t0, size

    def drop(self, _=None):
        if self.f:
            try:
                self.f.close()
            except OSError:
                pass
            self.f = None

    def pump(self):
        if not self.queue or self.card.sd is None:
            return False
        try:
            self._pump()
        except OSError as err:
            self.drop()
            if err.errno in (_ENOSPC, _EACCES):
                print("!! {} lost: the card is full".format(self.queue.pop(0)[0]))
            else:
                print("!! {} stills kept for the next mount".format(len(self.queue)))
            self.emit("card:error", err)
        return True

    def _pump(self):
        still = self.queue[0]
        path, buf, w, h, swapped = still
        if self.f is None:
            if not swapped:
                bmp_order(buf)
                still[4] = True
            self.f = open(STILL_TMP, "wb")
            self.f.write(bmp_header(w, h))
            self.off = 0
            self.t0 = time.monotonic()
            return
        n = min(SAVE_SLICE_BYTES, len(buf) - self.off)
        self.f.write(memoryview(buf)[self.off : self.off + n])
        self.off += n
        if self.off < len(buf):
            return
        size = self.f.tell()
        self.f.close()
        self.f = None
        os.rename(STILL_TMP, path)
        self.queue.pop(0)
        self.emit("still:saved", path)
        print("saved {} {}x{} ({} bytes) in {:.2f}s, {} pending".format(
            path, w, h, size, time.monotonic() - self.t0, len(self.queue)))

    def finish(self):
        card = self.card
        if not self.queue or card.sd is None:
            return
        print("finishing {} stills before stopping".format(len(self.queue)))
        kbd_intr = getattr(micropython, "kbd_intr", None)
        if kbd_intr:
            kbd_intr(-1)
        try:
            wdt.set(True)
            self.drop()
            while self.queue and card.sd is not None:
                wdt.feed()
                self.pump()
        finally:
            wdt.set(False)
            if kbd_intr:
                kbd_intr(3)


class Link(Component):

    connected, set_connected = state(False)
    adapter = ref(lambda: None)
    adv = ref(lambda: b"")

    def open(self):
        self.adapter = _bleio.adapter
        self.adapter.enabled = True
        self.adv = bytes((2, 1, 6, len(BLE_NAME) + 1, 9)) + BLE_NAME

    @on()
    def listen(self):
        self.bind("boot", self.drop)

    @on("connected")
    def report(self):
        print("ble: {}".format("connected" if self.connected else "not connected"))

    def poll(self):
        a = self.adapter
        self.set_connected(a.connected)
        if not a.connected and not a.advertising:
            a.start_advertising(self.adv, connectable=True)

    def drop(self, _=None):
        if not self.adapter.connected:
            print("ble: BOOT pressed, nothing connected, already advertising")
            return
        for c in self.adapter.connections:
            c.disconnect()
        print("ble: BOOT pressed, link dropped")

    def close(self):
        if self.adapter is None:
            return
        if self.adapter.connected:
            for c in self.adapter.connections:
                c.disconnect()
        deadline = time.monotonic() + 2
        while self.adapter.connected and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.adapter.connected:
            print("!! ble: link still up after 2s -- resetting rather than disabling")
            reset()
        if self.adapter.advertising:
            self.adapter.stop_advertising()
        self.adapter.enabled = False


class Outbox(Component):

    connected = prop()

    _HEADER = b"\xff\xff\xff\xff"
    _SKIP = 0xFFFFFFFF

    adapter = ref(lambda: None)
    card = ref(lambda: None)
    data = ref(lambda: None)
    ctl = ref(lambda: None)
    queue = ref(lambda: [])
    aside = ref(lambda: [])
    f = ref(lambda: None)
    fid = ref(lambda: 0)
    pkt = ref(lambda: bytearray(512))
    pkt_view = ref(lambda: None)
    size = base = sent = ref(lambda: 0)
    t = started = ref(lambda: 0.0)

    @on()
    def listen(self):
        self.bind("screen:saved", self.add)
        self.bind("still:saved", self.add)
        self.bind("card:going", self.drop)
        self.bind("outbox:request", self.request)

    def open(self, adapter, card):
        self.adapter = adapter
        self.card = card
        C = _bleio.Characteristic
        self.data = C.add_to_service(
            _bleio.Service(_bleio.UUID(BLE_UUID_FMT.format(1))),
            _bleio.UUID(BLE_UUID_FMT.format(2)), properties=C.NOTIFY,
            read_perm=_bleio.Attribute.OPEN, write_perm=_bleio.Attribute.NO_ACCESS,
            max_length=512, fixed_length=False)
        self.ctl = C.add_to_service(
            _bleio.Service(_bleio.UUID(BLE_UUID_FMT.format(4))),
            _bleio.UUID(BLE_UUID_FMT.format(3)),
            properties=C.WRITE | C.WRITE_NO_RESPONSE,
            read_perm=_bleio.Attribute.OPEN, write_perm=_bleio.Attribute.OPEN,
            max_length=8, fixed_length=False, initial_value=b"\x00")
        self.pkt_view = memoryview(self.pkt)

    def add(self, path):
        self.queue.append(path)

    def request(self, paths):
        busy = self.queue[0] if self.f else None
        paths = [p for p in paths if p != busy]
        for p in paths:
            for q in (self.queue, self.aside):
                while p in q:
                    q.remove(p)
        at = 1 if busy else 0
        self.queue[at:at] = paths

    @on("connected")
    def link_changed(self):
        if self.connected:
            return
        self.drop()
        if self.aside:
            self.queue[:0] = self.aside
            self.aside = []

    def drop(self, _=None):
        if self.f:
            try:
                self.f.close()
            except OSError:
                pass
            self.f = None

    def _acked(self):
        v = bytes(self.ctl.value)
        if len(v) != 6:
            return -1
        fid, off = struct.unpack("<HI", v)
        return off if fid == self.fid else -1

    def _send_header(self):
        name = self.queue[0].rsplit("/", 1)[-1].encode()
        self.data.value = self._HEADER + struct.pack(
            "<HIH", self.fid, self.size, len(self.queue) - 1) + name
        self.t = time.monotonic()

    def pump(self, window):
        try:
            return self._pump(window)
        except (IndexError, ConnectionError, _bleio.BluetoothError) as err:
            print("!! ble: send interrupted: {}: {}".format(type(err).__name__, err))
            self.drop()
            return True
        except OSError as err:
            print("!! ble: send interrupted: {}: {}".format(type(err).__name__, err))
            self.drop()
            if err.errno == _ENOENT:
                print("!! ble: {} is gone, skipped".format(self.queue.pop(0)))
            else:
                self.emit("card:error", err)
            return True

    def _pump(self, window):
        a = self.adapter
        if not a.connected:
            return False
        if self.f is None:
            if not self.queue or self.card.sd is None:
                return False
            path = self.queue[0]
            self.f = open(path, "rb")
            self.size = os.stat(path)[6]
            self.fid = (self.fid + 1) & 0xFFFF
            self.base = self.sent = 0
            self.started = time.monotonic()
            self._send_header()
            return True

        now = time.monotonic()
        base = self._acked()
        if base < 0:
            if now - self.t > BLE_ACK_WAIT_S:
                self._send_header()
            return False
        if base == self._SKIP:
            self.aside.append(self.queue.pop(0))
            print("ble: skipped {} for this connection".format(self.aside[-1]))
            self.drop()
            return False
        if base >= self.size:
            dt = now - self.started
            print("ble: sent {} ({} bytes) in {:.1f}s, {:.1f} KB/s".format(
                self.queue.pop(0), self.size, dt, self.size / dt / 1024))
            self.drop()
            return False
        if base != self.base:
            self.base = base
            self.t = now
        elif now - self.t > BLE_ACK_WAIT_S:
            self.sent = base
            self.t = now
        self.sent = max(self.sent, base)
        payload = min(a.connections[0].max_packet_length, 512) - 4
        limit = min(self.size, base + window * payload)
        if self.sent >= limit:
            return False
        self.f.seek(self.sent)
        while self.sent < limit:
            k = self.f.readinto(self.pkt_view[4 : 4 + min(payload, limit - self.sent)])
            if not k:
                break
            self.pkt[0:4] = struct.pack("<I", self.sent)
            self.data.value = self.pkt_view[: 4 + k]
            self.sent += k
        return True


class Card(Component):

    mounted, set_mounted = state(False)
    full, set_full = state(False)
    pending = prop()
    spi: "busio.SPI" = ref(lambda: None)  # pyright: ignore[reportAssignmentType] -- open() sets it
    cs = ref(lambda: None)
    sd: "sdcardio.SDCard | None" = ref(lambda: None)
    seq = ref(lambda: 0)
    next_retry = ref(lambda: 0.0)

    @on()
    def listen(self):
        self.bind("card:retry", self.retry)
        self.bind("card:error", self.failed)
        self.bind("screen:saved", self.written)
        self.bind("still:saved", self.written)

    @on("mounted", "pending")
    def retrying(self):
        self.cancel("card:retry")
        if not self.mounted and self.pending:
            self.after(max(0.0, self.next_retry - time.monotonic()), "card:retry")

    def render(self):
        if not self.mounted:
            return STATUS_NO_CARD
        return STATUS_FULL if self.full else None

    def open(self, spi):
        self.spi = spi

    def written(self, _):
        self.set_full(False)

    def claim(self):
        if not self.remount():
            return 0
        self.seq += 1
        return self.seq

    def attach(self, probe):
        spi = self.spi
        try:
            if self.cs is None:
                self.cs = digitalio.DigitalInOut(SD_CS)
            unstick_sd(spi, self.cs)
            if probe and not sd_answers(spi, self.cs):
                return None
            sd = sdcardio.SDCard(spi, self.cs, baudrate=SD_BAUD)
        except ValueError as err:
            print("!! sd bus/pin conflict:", err)
            return None
        except OSError as err:
            print("!! sd unusable:", err, "-- see memory/sd-bring-up.md")
            return None
        try:
            storage.mount(storage.VfsFat(sd), SD_MOUNT)
        except OSError as err:
            print("!! sd won't mount (FAT16/32 only):", err)
            sd.deinit()
            return None
        print("sd mounted at", SD_MOUNT)
        return sd

    def up(self, sd):
        self.sd = sd
        self.set_mounted(True)
        self.set_full(False)
        remove_temps()
        self.seq = max(self.seq, scan_still_seq())

    def unmount(self):
        self.emit("card:going")
        try:
            storage.umount(SD_MOUNT)
        except OSError as err:
            print("!! sd umount: {}".format(err))
        self.sd.deinit()
        self.sd = None
        self.set_mounted(False)
        print("sd unmounted")

    def failed(self, err):
        print("!! save failed: {}: {}".format(type(err).__name__, err))
        if err.errno in (_ENOSPC, _EACCES):
            self.set_full(True)
            self.emit("card:full")
            remove_temps()
        elif self.sd is not None:
            self.unmount()

    def remount(self, probe=False):
        if self.sd is None:
            sd = self.attach(probe)
            if sd is None:
                return False
            self.up(sd)
        return True

    def retry(self, _):
        if self.sd is not None or not self.pending:
            return
        t0 = time.monotonic()
        self.next_retry = t0 + SD_RETRY_S
        self.emit("bus")
        try:
            if self.remount(probe=True):
                self.emit("card:remounted")
            else:
                print("sd: no card, retry took {:.0f} ms".format(
                    (time.monotonic() - t0) * 1000))
        except OSError as err:
            self.emit("card:error", err)
        if self.sd is None:
            self.after(SD_RETRY_S, "card:retry")


class Panel(Component):

    byte_shift = prop()
    card = prop()
    saving = prop()
    display = ref(lambda: None)
    bus = ref(lambda: None)
    art = ref(lambda: {})
    since = ref(lambda: {})
    painted = ref(lambda: {})
    flashing = ref(lambda: None)
    stale = ref(lambda: False)
    card_img = ref(lambda: None)
    signal_img = ref(lambda: None)

    @on()
    def listen(self):
        self.bind("panel:flash", self.flash_over)
        self.bind("keys:lost", self.failed)
        self.bind("still:failed", self.failed)
        self.bind("card:error", self.failed)
        self.bind("press:refused", self.refused)
        self.bind("still:saved", self.saved)
        self.bind("camera:dry", self.went_dark)
        self.bind("bus", self.moved)

    def failed(self, _):
        self.flash(STATUS_FAILED, STATUS_FAILED_S)

    def refused(self, _):
        self.flash(STATUS_REFUSED, STATUS_FAILED_S)

    def saved(self, _):
        self.flash(STATUS_SAVED, STATUS_FLASH_S)

    def moved(self, _):
        self.stale = True

    def open(self, spi):
        self.display, self.bus = make_display(spi)
        try:
            self.art = load_ui(UI_PATH)
            print("status art: {} statuses from {}".format(len(self.art), UI_PATH))
        except (OSError, ValueError, IndexError) as err:
            self.art = {}
            line = "!! no status art, nothing will show: {}".format(err)
            print(line)
            append_log(line)

    def shift(self):
        return 1 if self.byte_shift else 0

    @on("byte_shift")
    def reanchor(self):
        if self.bus:
            self.anchor()

    def anchor(self):
        set_window(self.bus, _X0, _Y0, _X1, _Y1)
        self.stale = False

    def stamp(self, view, img):
        frame = memoryview(view)
        k = self.shift()
        for _, _, _, a, b, under, pix in img:
            s = frame[a + k : b + k]
            under[:] = s
            s[:] = pix

    def unstamp(self, view, img):
        frame = memoryview(view)
        k = self.shift()
        for _, _, _, a, b, under, _ in img:
            frame[a + k : b + k][:] = under

    def show(self, view):
        if self.shift():
            self.anchor()
            self.bus.send(_RAMWR, view[1:])
        else:
            self.bus.send(_RAMWR, view)

    def blit(self, view, card, signal):
        if self.stale:
            self.anchor()
        self.card_img = card_img = self.ui_frame(SLOT_CARD, card)
        self.signal_img = signal_img = self.ui_frame(SLOT_SIGNAL, signal)
        if card_img:
            self.stamp(view, card_img)
        if signal_img:
            self.stamp(view, signal_img)
        self.show(view)
        if signal_img:
            self.unstamp(view, signal_img)
        if card_img:
            self.unstamp(view, card_img)

    def flash(self, status, secs):
        self.flashing = status
        self.since.pop(SLOT_CARD, None)
        self.cancel("panel:flash")
        self.after(secs, "panel:flash")

    def flash_over(self, _):
        self.flashing = None

    def card_status(self):
        if self.flashing:
            return self.flashing
        if self.card:
            return self.card
        if self.saving:
            return STATUS_SAVING
        return None

    def show_saving(self, view, shown):
        img = self.ui_frame(SLOT_CARD, STATUS_SAVING)
        if shown and shown is not img:
            self.draw_runs(shown, under=memoryview(view))
        if img:
            self.draw_runs(img)

    def ui_frame(self, slot, status):
        if status is None:
            self.since.pop(slot, None)
            return None
        began = self.since.get(slot)
        if began is None or began[0] != status:
            began = self.since[slot] = [status, 0]
        else:
            began[1] += 1
        if status not in self.art:
            return None
        steps, repeats = self.art[status]
        i = began[1] // UI_HOLD_FRAMES
        if repeats and i >= len(steps) * repeats:
            return steps[-1]
        return steps[i % len(steps)]

    def draw_runs(self, img, black=False, under=None):
        self.stale = True
        k = self.shift()
        for x, y, nb, a, b, _, pix in img:
            set_window(self.bus, x, y, x + nb // 2 - 1, y)
            if under is not None:
                pix = under[a + k : b + k]
            elif black:
                pix = _BLACK[:nb]
            self.bus.send(_RAMWR, pix)

    def paint(self, shown):
        for slot, status in shown.items():
            img = self.ui_frame(slot, status)
            last = self.painted.get(slot)
            if img is last:
                continue
            if last:
                self.draw_runs(last, black=True)
            if img:
                self.draw_runs(img)
            self.painted[slot] = img

    def went_dark(self, _=None):
        self.painted[SLOT_CARD] = self.card_img
        self.painted[SLOT_SIGNAL] = self.signal_img


class Review(Component):

    connected = prop()
    card = ref(lambda: None)
    bus = ref(lambda: None)
    sends = ref(lambda: False)
    active = ref(lambda: False)
    shots = ref(lambda: [])
    files = ref(lambda: {})
    i = ref(lambda: -1)
    listed = ref(lambda: False)
    buf = ref(lambda: None)
    dirty = ref(lambda: False)

    def open(self, card, bus, sends):
        self.card = card
        self.bus = bus
        self.sends = sends

    @on()
    def listen(self):
        self.bind("review", self.command)
        self.bind("review:idle", self.idle)
        self.bind("card:going", self.gone)
        self.bind("screen:saved", self.moved)
        self.bind("still:saved", self.moved)

    @on("connected")
    def link_changed(self):
        if not self.connected and self.active:
            self.close("phone gone")

    def reply(self, d):
        self.emit("settings:reply", d)

    def moved(self, _):
        self.listed = False

    def gone(self, _):
        if self.active:
            self.close("no card")

    def idle(self, _):
        if self.active:
            self.close("idle")

    def failed(self, err):
        self.close("card failed")
        self.emit("card:error", err)

    def close(self, why):
        if self.active:
            self.active = self.listed = self.dirty = False
            self.shots = []
            self.files = {}
            self.i = -1
            self.buf = None
            self.cancel("review:idle")
            self.emit("bus")
            print("review: closed ({})".format(why))
        self.reply({"review": None, "why": why})

    def command(self, d):
        cmd = d["review"]
        if cmd == "exit":
            self.close("phone")
            return
        if not self.active:
            if cmd != "enter":
                self.reply({"review": None, "err": "not reviewing"})
                return
            if self.card.sd is None:
                self.reply({"review": None, "err": "no card"})
                return
            self.active = True
            print("review: open")
        self.cancel("review:idle")
        self.after(REVIEW_IDLE_S, "review:idle")
        try:
            if not self.listed:
                self.scan()
        except OSError as err:
            self.failed(err)
            return
        if not self.shots:
            self.close("no stills on the card")
            return
        by = d.get("by", 1)
        by = by if type(by) is int and by > 0 else 1
        err = None
        queued = None
        if cmd == "next":
            self.step(by)
        elif cmd == "prev":
            self.step(-by)
        elif cmd == "send":
            if self.sends:
                queued = self.send(d.get("files"))
            else:
                err = "this camera sends no stills"
        elif cmd != "enter":
            err = "no such command"
        line = self.line()
        if queued is not None:
            line["queued"] = queued
        elif err:
            line["err"] = err
        self.reply(line)

    def scan(self):
        on = self.shots[self.i] if self.shots else None
        files = {}
        for name in os.listdir(SD_MOUNT):
            n = shot_number(name)
            if n:
                files.setdefault(n, []).append(name)
        for names in files.values():
            names.sort(key=lambda s: STILL_SCREEN_SUFFIX not in s)
        self.files = files
        self.shots = sorted(files)
        self.listed = True
        i = self.shots.index(on) if on in files else len(self.shots) - 1
        if i != self.i or on not in files:
            self.dirty = True
        self.i = i

    def step(self, by):
        i = min(len(self.shots) - 1, max(0, self.i + by))
        if i != self.i:
            self.i = i
            self.dirty = True

    def send(self, names):
        if type(names) is not list:
            return []
        mine = self.files[self.shots[self.i]]
        names = [n for n in mine if n in names]
        self.emit("outbox:request", ["{}/{}".format(SD_MOUNT, n) for n in names])
        return names

    def line(self) -> dict:
        n = self.shots[self.i]
        return {"review": {
            "shot": "{}{:04d}".format(STILL_PREFIX, n), "i": self.i + 1,
            "n": len(self.shots), "files": self.files[n]}}

    def pump(self):
        if not self.active:
            return
        try:
            if not self.listed:
                self.scan()
                if not self.shots:
                    self.close("no stills on the card")
                    return
                self.reply(self.line())
            if self.dirty:
                self.draw()
        except OSError as err:
            self.failed(err)

    def draw(self):
        self.dirty = False
        size = PREVIEW_W * PREVIEW_H * 2
        if self.buf is None:
            self.buf = bytearray(size)
        ok = False
        try:
            with open(still_path(self.shots[self.i], STILL_SCREEN_SUFFIX), "rb") as f:
                head = f.read(54)
                off, _, w, h, _, bpp = struct.unpack_from("<IIiiHH", head, 10)
                if (w, h, bpp) == (PREVIEW_W, PREVIEW_H, 16):
                    f.seek(off)
                    ok = f.readinto(self.buf) == size
        except OSError as err:
            if err.errno != _ENOENT:
                raise
        if ok:
            bmp_order(self.buf)
            set_window(self.bus, _X0, _Y0, _X1, _Y1)
            self.bus.send(_RAMWR, self.buf)
            return
        print("review: {} has no {} copy to show".format(
            self.shots[self.i], STILL_SCREEN_SUFFIX))
        for y in range(_Y0, _Y1 + 1):
            set_window(self.bus, _X0, y, _X1, y)
            self.bus.send(_RAMWR, _BLACK[: PREVIEW_W * 2])


class Camera(Component):

    i2c = ref(lambda: None)
    cam = ref(lambda: None)
    first_t: "float | None" = ref(lambda: None)
    misses = ref(lambda: 0)
    dry = ref(lambda: 0)
    dry_t = ref(lambda: 0.0)
    rebuilds = ref(lambda: 0)
    rebuild_gap = ref(lambda: REBUILD_BACKOFF_S)
    next_rebuild = ref(lambda: 0.0)
    taps = ref(lambda: [i * (PREVIEW_W * PREVIEW_H * 2 // FROZEN_TAPS)
                        for i in range(FROZEN_TAPS)])
    now_taps = ref(lambda: bytearray(FROZEN_TAPS))
    last_taps = ref(lambda: bytearray(FROZEN_TAPS))
    identical = ref(lambda: 0)

    def open(self):
        reset_sensor()
        self.i2c = busio.I2C(scl=CAM_SCL, sda=CAM_SDA)
        self.cam = make_camera(self.i2c)

    def take(self):
        f = self.cam.take(TAKE_TIMEOUT)
        if f is None:
            return None, None
        return f, np.frombuffer(f, dtype=np.uint8)

    def rebuild(self):
        wdt.feed()
        self.cam.deinit()
        gc.collect()
        self.cam = make_camera(self.i2c)
        self.emit("camera:reset")
        wdt.feed()

    def missed(self, t):
        if not self.dry:
            self.dry_t = t
            self.emit("camera:dry")
        self.dry += 1
        self.misses += 1
        print("!! take() timed out ({} in a row, {} so far)".format(self.dry, self.misses))
        if self.first_t is not None and self.dry == 1:
            print("!! no first frame: a sync bend, or see src/bringup/03_camera_test.py")

    def capture(self, snap):
        gc.collect()
        largest = espidf.heap_caps_get_largest_free_block()
        print("heap: largest block {}, free {}".format(
            largest, espidf.heap_caps_get_free_size()))
        if largest < STILL_BYTES + STILL_HEAP_MARGIN:
            print("!! shot skipped: no {}-byte block for the still".format(STILL_BYTES))
            return None
        self.cam.reconfigure(
            frame_size=STILL_SIZE,
            pixel_format=espcamera.PixelFormat.RGB565,
            framebuffer_count=1,
        )
        set_orientation(self.cam)
        if STILL_PLL:
            set_pll(self.i2c, self.cam, *STILL_PLL)
        self.emit("camera:still", snap)
        for _ in range(STILL_DISCARD_FRAMES):
            self.cam.take(TAKE_TIMEOUT)
        buf = self.cam.take(TAKE_TIMEOUT)
        if buf is None:
            print("!! still capture timed out")
        return buf

    def take_still(self, n, buf, snap):
        t0 = time.monotonic()
        try:
            wdt.feed()
            still = self.capture(snap)
            if still is None:
                self.emit("still:failed")
                return
            buf[:] = memoryview(still).cast("B")
            self.emit("still:captured", (n, buf, still.width, still.height, t0))
        finally:
            self.cam.reconfigure(
                frame_size=FRAME_SIZE,
                pixel_format=espcamera.PixelFormat.RGB565,
                framebuffer_count=FRAMEBUFFER_COUNT,
            )
            set_orientation(self.cam)
            set_preview_pll(self.i2c, self.cam)
            self.emit("camera:preview", snap)

    def rebuild_due(self):
        return self.dry >= DROUGHT_MISSES and time.monotonic() >= self.next_rebuild

    def rebuild_dry(self):
        self.rebuilds += 1
        tr = time.monotonic()
        self.rebuild()
        line = "!! no frames for {:.0f}s: camera rebuilt ({} this drought) in {:.2f}s".format(
            tr - self.dry_t, self.rebuilds, time.monotonic() - tr)
        print(line)
        append_log(line)
        self.next_rebuild = time.monotonic() + self.rebuild_gap
        self.rebuild_gap = min(self.rebuild_gap * 2, REBUILD_BACKOFF_MAX_S)

    def arrived(self, frame, t, tc):
        if self.first_t is not None:
            if (frame.width, frame.height) != (PREVIEW_W, PREVIEW_H):
                raise ValueError("frame is {}x{}: FRAME_SIZE and PREVIEW_W/H disagree".format(
                    frame.width, frame.height))
            print("first frame in {:.2f}s".format(tc - self.first_t))
            self.first_t = None
        if not self.dry:
            return False
        line = "frames back after {:.1f}s: {} misses in a row, {} rebuilds".format(
            t - self.dry_t, self.dry, self.rebuilds)
        print(line)
        if self.rebuilds:
            append_log(line)
        self.dry = self.rebuilds = 0
        self.rebuild_gap = REBUILD_BACKOFF_S
        self.next_rebuild = 0.0
        return True

    def frozen(self):
        return self.identical >= FROZEN_FRAMES

    def watch(self, frame):
        raw = memoryview(frame).cast("B")
        now_taps = self.now_taps
        taps = self.taps
        for i in range(FROZEN_TAPS):
            now_taps[i] = raw[taps[i]]
        if now_taps == self.last_taps:
            self.identical += 1
            if self.identical == FROZEN_FRAMES:
                print("!! picture frozen: {} identical frames".format(self.identical))
        else:
            if self.identical >= FROZEN_FRAMES:
                print("   picture moving again")
            self.identical = 0
        self.now_taps, self.last_taps = self.last_taps, now_taps


class Look(Component):

    EXPOSURE_KEYS = ("exposure", "ev", "exposure_value", "iso")
    WB_KEYS = ("wb", "wb_r", "wb_g", "wb_b")

    exp_due, set_exp_due = state(0)
    wb_due, set_wb_due = state(0)
    camera = ref(lambda: None)
    values = ref(lambda: {})
    held_exp = ref(lambda: None)
    held_wb = ref(lambda: None)
    targets = ref(lambda: [])
    frames = ref(lambda: 0)
    exp_mode = ref(lambda: None)
    wb_mode = ref(lambda: None)

    def open(self, camera, values):
        self.camera = camera
        self.values = values

    def setting(self, k):
        return self.values[k]

    def write(self, reg, value):
        c = self.camera
        sensor_write(c.i2c, c.cam.address, reg, value)

    def read(self, reg, n):
        c = self.camera
        return sensor_read(c.i2c, c.cam.address, reg, n)

    def put(self, reg, data):
        for i, b in enumerate(data):
            self.write(reg + i, b)

    def fresh(self):
        self.frames = 0
        self.targets = [self.read(r, 1)[0] for r in _AEC_TARGETS]

    @on()
    def listen(self):
        self.bind("frame", self.settle)
        self.bind("camera:reset", self.reset)
        self.bind("camera:still", self.still)
        self.bind("camera:preview", self.restore)
        self.bind("setting:changed", self.changed)

    def reset(self, _):
        self.fresh()
        self.apply_exposure()
        self.apply_wb()

    def still(self, snap):
        if snap:
            self.hold_for_still(snap)

    def settle(self, _):
        if self.frames < LOCK_SETTLE_FRAMES:
            self.frames += 1
            if self.frames == LOCK_SETTLE_FRAMES:
                self.apply_exposure()
                self.apply_wb()

    def settling(self):
        return self.frames < LOCK_SETTLE_FRAMES

    def changed(self, k):
        if k in self.EXPOSURE_KEYS:
            self.set_exp_due(bump)
        elif k in self.WB_KEYS:
            self.set_wb_due(bump)

    @on("exp_due")
    def exposure_changed(self):
        self.apply_exposure()

    @on("wb_due")
    def wb_changed(self):
        self.apply_wb()

    def read_exposure(self):
        b = self.read(_AEC_EXPOSURE, 3)
        g = self.read(_AEC_GAIN, 2)
        return (b[0] & 0x0F) << 16 | b[1] << 8 | b[2], (g[0] & 0x03) << 8 | g[1]

    def read_wb(self):
        b = self.read(_AWB_GAINS, 6)
        return tuple((b[i] & 0x0F) << 8 | b[i + 1] for i in (0, 2, 4))

    def hold_exposure(self, exp, gain):
        self.write(_AEC_MANUAL, 0x03)
        self.put(_AEC_EXPOSURE, (exp >> 16 & 0x0F, exp >> 8 & 0xFF, exp & 0xFF))
        self.put(_AEC_GAIN, (gain >> 8 & 0x03, gain & 0xFF))

    def hold_wb(self, gains):
        self.write(_AWB_MANUAL, 0x01)
        for i, g in enumerate(gains):
            self.put(_AWB_GAINS + 2 * i, (g >> 8 & 0x0F, g & 0xFF))

    def live(self):
        exp, gain = self.read_exposure()
        vts = self.read(_TIMING_VTS, 2)
        top = (vts[0] << 8 | vts[1]) - 4
        r, g, b = self.read_wb()
        return {
            "exposure_value": SHUTTER_THIRDS + 3 * math.log(max(16, exp) / 16 / top) / math.log(2),
            "iso": gain * 100 / 16,
            "wb_r": r, "wb_g": g, "wb_b": b,
        }

    def seed(self, keys):
        live = self.live()
        if "iso" in keys:
            t = nearest("exposure_value", live["exposure_value"])
            live["iso"] *= 2 ** ((live["exposure_value"] - t) / 3)
        for k in keys:
            self.emit("setting", (k, nearest(k, live[k])))

    def apply_exposure(self):
        mode = EXPOSURE_MODES[self.setting("exposure")]
        if mode == "manual" and self.exp_mode not in (None, "manual"):
            self.seed(("exposure_value", "iso"))
        self.exp_mode = mode
        if mode != "lock":
            self.held_exp = None
        k = 2 ** (self.setting("ev") / 3)
        for reg, t in zip(_AEC_TARGETS, self.targets):
            self.write(reg, min(255, max(1, round(t * k))))
        if mode == "auto" or (mode == "lock" and self.held_exp is None and self.settling()):
            self.write(_AEC_MANUAL, 0x00)
            return
        if mode == "lock":
            if self.held_exp is None:
                self.held_exp = self.read_exposure()
                print("look: exposure locked at {} lines, gain {}".format(
                    self.held_exp[0] >> 4, self.held_exp[1]))
            self.hold_exposure(*self.held_exp)
            return
        top = self.read(_TIMING_VTS, 2)
        top = (top[0] << 8 | top[1]) - 4
        lines = max(1, round(top * 2 ** ((self.setting("exposure_value") - SHUTTER_THIRDS) / 3)))
        self.hold_exposure(lines << 4, self.setting("iso") * 16 // 100)

    def apply_wb(self):
        mode = WB_MODES[self.setting("wb")]
        if mode == "manual" and self.wb_mode not in (None, "manual"):
            self.seed(("wb_r", "wb_g", "wb_b"))
        self.wb_mode = mode
        if mode != "lock":
            self.held_wb = None
        if mode == "auto" or (mode == "lock" and self.held_wb is None and self.settling()):
            self.write(_AWB_MANUAL, 0x00)
            return
        if mode == "lock":
            if self.held_wb is None:
                self.held_wb = self.read_wb()
                print("look: white balance locked at {}".format(self.held_wb))
            gains = self.held_wb
        elif mode == "manual":
            gains = (self.setting("wb_r"), self.setting("wb_g"), self.setting("wb_b"))
        else:
            gains = WB_PRESETS[mode]
        self.hold_wb(gains)

    def line_s(self):
        b = self.read(_SC_PLL_CTRL0, 4)
        bit_div = (b[0] & 0x0F) / 2 if b[0] & 0x0F in (8, 10) else 1
        sys_div = b[1] >> 4 or 16
        root_div = (b[3] >> 4 & 1) + 1
        sclk_div = 1 << (self.read(_SC_SCLK, 1)[0] & 0x03)
        sysclk = XCLK_HZ * b[2] / (b[3] & 0x0F) / sys_div / root_div * 2 / bit_div / sclk_div
        hts = self.read(_TIMING_HTS, 2)
        return (hts[0] << 8 | hts[1]) / sysclk

    def snapshot(self):
        return self.read_exposure(), self.read_wb(), self.line_s()

    def hold_for_still(self, snap):
        (exp, gain), gains, line = snap
        still_exp = round(exp * line / self.line_s())
        vts = self.read(_TIMING_VTS, 2)
        top = ((vts[0] << 8 | vts[1]) - 4) << 4
        if still_exp > top:
            print("!! still exposure {} lines clamped to the frame's {}".format(
                still_exp >> 4, top >> 4))
            still_exp = top
        self.hold_exposure(still_exp, gain)
        self.hold_wb(gains)
        print("look: {} lines x gain {} ({:.1f} ms), awb {}; still {} lines".format(
            exp >> 4, gain, (exp >> 4) * line * 1000, gains, still_exp >> 4))

    def restore(self, snap):
        if snap:
            self.hold_exposure(*snap[0])
            self.hold_wb(snap[1])
        self.apply_exposure()
        self.apply_wb()


class Knob(Component):

    adc = ref(lambda: None)
    k = ref(lambda: "")
    values = ref(lambda: [])
    i = ref(lambda: None)
    pos = ref(lambda: None)

    def open(self, pin, k):
        self.adc = analogio.AnalogIn(pin)
        self.k = k
        row = ROWS[k]
        if row["kind"] == "int":
            self.values = list(range(row["min"], row["max"] + 1, row.get("step", 1)))
        elif row["kind"] == "enum":
            self.values = list(range(len(row["opts"])))
        else:
            raise ValueError("a knob can't turn {} setting {}".format(row["kind"], k))

    @on()
    def listen(self):
        self.bind("frame", self.turned)

    def turned(self, _):
        x = self.adc.value / 65535
        self.pos = x if self.pos is None else self.pos + (x - self.pos) * KNOB_SMOOTH
        p = self.pos * len(self.values)
        i = self.i
        if i is not None and i - KNOB_HYSTERESIS <= p < i + 1 + KNOB_HYSTERESIS:
            return
        self.i = min(len(self.values) - 1, int(p))
        self.emit("setting", (self.k, self.values[self.i]))


class UiBench(Component):

    phases = ref(lambda: [])
    i = ref(lambda: -1)
    shot = ref(lambda: False)
    end = t0 = cap = blit = ref(lambda: 0.0)
    frames = ref(lambda: 0)

    def open(self):
        card = (STATUS_SAVING, STATUS_SAVED, STATUS_REFUSED, STATUS_FAILED,
                STATUS_NO_CARD, STATUS_FULL)
        p: list = [("none", None, None)]
        p += [(s, s, None) for s in card]
        p += [(s, None, s) for s in (STATUS_FROZEN, STATUS_NO_SIGNAL)]
        p.append(("refused+no_signal", STATUS_REFUSED, STATUS_NO_SIGNAL))
        p.append(("shot", "shot", None))
        p.append(("after shot", None, None))
        self.phases = p
        self.advance()

    @on()
    def listen(self):
        for label in ("still:saved", "still:failed", "press:refused", "card:error"):
            self.bind(label, self.shot_over)

    def shot_over(self, _):
        self.shot = True

    def advance(self):
        self.i += 1
        self.shot = False
        self.restart()
        self.end = self.t0 + BENCH_HOLD_S
        if self.i == len(self.phases):
            print("bench done")
            return
        name, card, signal = self.phases[self.i]
        if card == "shot":
            emit(self.app, "shutter", supervisor.ticks_ms())
            print("bench: {}".format(name))
            return
        runs = []
        art = self.app.panel.art
        for status in (card, signal):
            if status in art:
                img = art[status][0][0]
                runs.append("{} {} runs".format(status, len(img) if img else 0))
        print("bench: {} ({})".format(name, ", ".join(runs) or "no art"))

    def restart(self):
        self.frames = 0
        self.cap = self.blit = 0.0
        self.t0 = time.monotonic()

    def statuses(self):
        if self.i >= len(self.phases) or self.phases[self.i][1] == "shot":
            return None
        return self.phases[self.i][1:]

    def tick(self, cap, blit):
        if self.i >= len(self.phases):
            return
        self.frames += 1
        self.cap += cap
        self.blit += blit
        now = time.monotonic()
        if self.phases[self.i][1] == "shot":
            if not self.shot:
                return
        elif now < self.end:
            return
        n = self.frames
        secs = now - self.t0
        print("bench: {} -> {:.1f} fps over {} frames (take {:.0f}ms, blit {:.0f}ms, other {:.0f}ms)".format(
            self.phases[self.i][0], n / secs, n, self.cap / n * 1000,
            self.blit / n * 1000, (secs - self.cap - self.blit) / n * 1000))
        self.advance()


class AutoBench(Component):

    steps = ref(lambda: [])
    i = ref(lambda: 0)
    counting = ref(lambda: False)
    last = ref(lambda: -1)
    grew = ref(lambda: 0)
    n = ref(lambda: 0)
    gcs = ref(lambda: 0)
    t0 = ref(lambda: 0.0)
    found = ref(lambda: {})
    saved = ref(lambda: 0)
    refused = ref(lambda: 0)
    flip = ref(lambda: False)

    @on()
    def listen(self):
        self.bind("frame", self.sample)
        self.bind("bench:step", self.step)
        self.bind("still:saved", self.landed)
        self.bind("press:refused", self.turned_away)

    def open(self):
        self.found = dict(self.app.settings.values)
        if BENCH_AUTO == "presses":
            self.steps = ([self.settle, self.heap] + [self.press2, self.report] * BENCH_PRESS_ROUNDS
                          + [self.heap, self.done])
            self.after(0, "bench:step")
            return
        review = [self.enter, self.prev, self.prev, self.next, self.exit]
        self.steps = (
            [self.settle, self.count, self.counted, self.heap]
            + [self.press, self.report, self.press2, self.report]
            + review + [self.heap, self.press2, self.report]
            + [self.enter, self.press, self.report]
            + review * 5 + [self.heap, self.press2, self.report]
            + [self.churn, self.counted, self.restore, self.count, self.counted, self.heap]
            + [self.done])
        self.after(0, "bench:step")

    def step(self, _):
        if self.i < len(self.steps):
            self.i += 1
            self.after(self.steps[self.i - 1](), "bench:step")

    def sample(self, _):
        if self.flip:
            self.emit("setting", ("shift", not self.app.settings.values["shift"]))
        if not self.counting:
            return
        a = gc.mem_alloc()
        if self.last >= 0:
            if a >= self.last:
                self.grew += a - self.last
                self.n += 1
            else:
                self.gcs += 1
        self.last = a

    def landed(self, _):
        self.saved += 1

    def turned_away(self, _):
        self.refused += 1

    def settle(self):
        print("auto: start, settings {}".format(self.found))
        return 10.0

    def count(self):
        self.counting = True
        self.last = -1
        self.grew = self.n = self.gcs = 0
        self.t0 = time.monotonic()
        return 8.0

    def counted(self):
        self.counting = self.flip = False
        n = max(1, self.n)
        print("auto: {} frames in {:.1f}s: {} bytes a frame ({} bytes, {} gc passes)".format(
            self.n + self.gcs, time.monotonic() - self.t0, self.grew // n, self.grew, self.gcs))
        return 0.0

    def heap(self):
        gc.collect()
        print("auto: heap free {}, largest block {}".format(
            gc.mem_free(), espidf.heap_caps_get_largest_free_block()))
        return 0.0

    def press(self):
        print("auto: press")
        emit(self.app, "shutter", supervisor.ticks_ms())
        return 10.0

    def press2(self):
        print("auto: two presses")
        emit(self.app, "shutter", supervisor.ticks_ms())
        emit(self.app, "shutter", supervisor.ticks_ms())
        return 16.0

    def report(self):
        print("auto: {} stills saved, {} refused, {} pending".format(
            self.saved, self.refused, len(self.app.saver.queue)))
        self.saved = self.refused = 0
        return 0.0

    def review(self, cmd):
        print("auto: review {}".format(cmd))
        self.emit("review", {"review": cmd})
        return 0.5

    def enter(self):
        return self.review("enter") + 0.5

    def prev(self):
        return self.review("prev")

    def next(self):
        return self.review("next")

    def exit(self):
        print("auto: in review, largest block {}".format(espidf.heap_caps_get_largest_free_block()))
        return self.review("exit") + 1.5

    def churn(self):
        print("auto: byte shift flipped every frame")
        self.count()
        self.flip = True
        return 5.0

    def restore(self):
        for k, v in self.found.items():
            if self.app.settings.values[k] != v:
                self.emit("setting", (k, v))
        print("auto: settings restored")
        return 5.0

    def done(self):
        print("auto: done")
        return 0.0


_X0 = (PANEL_W - PREVIEW_W) // 2
_Y0 = (PANEL_H - PREVIEW_H) // 2
_X1 = _X0 + PREVIEW_W - 1
_Y1 = _Y0 + PREVIEW_H - 1
_BLACK = memoryview(bytes(PANEL_W * 2))


def bump(n):
    return n + 1


def setting(k):
    return lambda self: self.settings.values[k]


def connected(self):
    return bool(self.link and self.link.connected)


class Main(Component):

    link = comp(Link) if BLE_LINK else None
    settings = comp(Settings, connected=connected)
    shutter = comp(Shutter)
    saver = comp(Saver)
    outbox = comp(Outbox, connected=connected) if BLE_LINK and BLE_SEND else None
    card = comp(
        Card, pending=lambda self: bool(self.saver.queue or (self.outbox and self.outbox.queue)))
    panel = comp(Panel, byte_shift=setting("shift"), card=lambda self: self.card.rendered,
                 saving=lambda self: bool(self.saver.queue))
    review = comp(Review, connected=connected) if BLE_LINK else None
    camera = comp(Camera)
    look = comp(Look)
    knob = comp(Knob) if KNOB_ON else None
    bench = comp(UiBench) if BENCH_UI else None
    auto = comp(AutoBench) if BENCH_AUTO else None
    spi = ref(lambda: None)

    def boot(self):
        self.settings.open(defaults_only=shutter_held())
        self.shutter.open()

        displayio.release_displays()
        self.spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO)
        self.card.open(self.spi)
        self.saver.open(self.card)
        self.card.remount()
        append_log("{}\n{}".format(boot_line, self.settings.note))
        if in_a_row >= BOOTLOOP_LIMIT:
            halt("!! {} crashes in a row with no healthy run between. Not starting\n"
                 "the camera: it would only reset again. Push a fixed code.py, or\n"
                 "press reset to try once more.".format(in_a_row))

        self.panel.open(self.spi)
        self.camera.open()
        self.look.open(self.camera, self.settings.values)
        self.look.fresh()
        gc.collect()
        print("camera up: {}, heap free {}".format(self.camera.cam.sensor_name, gc.mem_free()))

        if self.link:
            self.link.open()
            if self.outbox:
                self.outbox.open(self.link.adapter, self.card)
            self.settings.attach(self.link, self.look.live)
            self.review.open(self.card, self.panel.bus, self.outbox is not None)
            self.link.poll()
            print("ble: advertising as {}".format(BLE_NAME.decode()))
        if self.knob:
            self.knob.open(KNOB, KNOB_SETTING)

        wdt.armed = True
        wdt.set(True)
        print("watchdog armed at {:.0f}s".format(WATCHDOG_TIMEOUT))
        self.set_timeout("healthy", HEALTHY_S, self.healthy)

        if PREVIEW_W % 16:
            raise ValueError("width {} pads its rows; the blit would shear".format(PREVIEW_W))
        print("preview running")

    def save_screen(self, frame, view, shown):
        self.panel.show_saving(view, shown)
        wdt.feed()
        try:
            n = self.card.claim()
            if not n:
                return 0
            path = still_path(n, STILL_SCREEN_SUFFIX)
            elapsed, size = self.saver.write_now(path, frame, self.panel.shift())
        except OSError as err:
            self.emit("card:error", err)
            return 0
        self.emit("screen:saved", path)
        print("saved {} ({} bytes) in {:.2f}s".format(path, size, elapsed))
        return n

    def review_pass(self):
        wdt.feed()
        self.shutter.poll()
        self.link.poll()
        tick(self)
        self.saver.pump()
        self.settings.pump()
        if self.outbox:
            self.outbox.pump(BLE_WINDOW - 1 if self.settings.sending() else BLE_WINDOW)
        review = self.review
        if not review.active:
            return
        if self.shutter.presses:
            self.shutter.presses.clear()
            review.close("shutter")
            return
        review.pump()
        time.sleep(REVIEW_TICK_S)

    def healthy(self, _):
        note_healthy()

    def run(self):
        camera = self.camera
        panel = self.panel
        saver = self.saver
        shutter = self.shutter
        settings = self.settings
        link = self.link
        outbox = self.outbox
        review = self.review
        bench = self.bench
        camera.first_t = time.monotonic()
        if bench:
            bench.open()
        if self.auto:
            self.auto.open()
        frames = 0
        cap_secs = 0.0
        blit_secs = 0.0
        t0 = time.monotonic()

        while True:
            if review and review.active:
                self.review_pass()
                if not review.active:
                    frames = 0
                    cap_secs = 0.0
                    blit_secs = 0.0
                    t0 = time.monotonic()
                continue
            wdt.feed()
            _t = time.monotonic()
            frame, view = camera.take()
            _tc = time.monotonic()
            cap_secs += _tc - _t
            shutter.poll()
            if link:
                link.poll()
            if frame is not None:
                emit(self, "frame")
            tick(self)

            if frame is None:
                camera.missed(_t)
                if shutter.presses:
                    print("!! {} press(es) refused: no signal".format(len(shutter.presses)))
                    shutter.presses.clear()
                    self.emit("press:refused")
                panel.paint({SLOT_SIGNAL: STATUS_NO_SIGNAL, SLOT_CARD: panel.card_status()})
                settings.pump(BLE_WINDOW)
                deadline = time.monotonic() + DROUGHT_SAVE_S
                while time.monotonic() < deadline and saver.pump():
                    pass
                if camera.rebuild_due():
                    camera.rebuild_dry()
                continue

            if camera.arrived(frame, _t, _tc):
                frames = 0
                cap_secs = 0.0
                blit_secs = 0.0
                t0 = _tc

            forced = bench.statuses() if bench else None
            if forced:
                panel.blit(view, forced[0], forced[1])
            else:
                panel.blit(view, panel.card_status(),
                           STATUS_FROZEN if camera.frozen() else None)
            _tb = time.monotonic() - _tc
            blit_secs += _tb
            if bench:
                bench.tick(_tc - _t, _tb)
            if saver.pump():
                panel.stale = True
            settings.pump()
            if outbox and outbox.pump(BLE_WINDOW - 1 if settings.sending() else BLE_WINDOW):
                panel.stale = True

            camera.watch(frame)

            shutter.refuse_stale()
            if shutter.presses:
                shutter.presses.pop(0)
                print("shutter")
                _tp = time.monotonic()
                buf = saver.reserve()
                if buf is None:
                    self.emit("press:refused")
                else:
                    snap = self.look.snapshot() if STILL_LOCK else None
                    n = self.save_screen(frame, view, panel.card_img)
                    frame = view = None
                    if n:
                        camera.take_still(n, buf, snap)
                    buf = None
                    panel.stale = True
                    print("preview back {:.2f}s after the press".format(
                        time.monotonic() - _tp))
                frames = 0
                cap_secs = 0.0
                blit_secs = 0.0
                t0 = time.monotonic()
                if bench:
                    bench.restart()

            frames += 1
            if frames == 30:
                now = time.monotonic()
                print(
                    "{:.1f} fps (take {:.0f}ms, blit {:.0f}ms, other {:.0f}ms)".format(
                        frames / (now - t0),
                        cap_secs / frames * 1000,
                        blit_secs / frames * 1000,
                        (now - t0 - cap_secs - blit_secs) / frames * 1000,
                    )
                )
                frames = 0
                cap_secs = 0.0
                blit_secs = 0.0
                t0 = now

    def close(self):
        saver = self.saver
        try:
            saver.finish()
        except BaseException as err:
            print("!! finishing saves failed: {}: {}".format(type(err).__name__, err))
        if saver.queue:
            print("!! {} stills not written: they were in RAM only".format(len(saver.queue)))
        saver.drop()
        try:
            if self.outbox:
                self.outbox.drop()
            self.settings.close()
            if self.link:
                self.link.close()
        except Exception as err:
            print("!! ble close failed: {}: {}".format(type(err).__name__, err))


print("code.py: live preview")

boot_t = time.monotonic()
app = None
failed = None

try:
    boot_line, in_a_row = fold_boot()
    field_mode = not storage.getmount("/").readonly
    supervisor.runtime.autoreload = not field_mode
    boot_line += ", field mode" if field_mode else ", dev mode"
    print(boot_line)

    app = create(Main, clock=supervisor.ticks_ms)
    app.boot()
    tick(app)
    app.run()
except Exception as err:
    failed = err
    wdt.set(False)
    in_a_row = note_crash()
    report = "".join(traceback.format_exception(err))
    print(report)
    append_log("!! crash {} in a row, {:.0f}s after boot:\n{}".format(
        in_a_row, time.monotonic() - boot_t, report))
finally:
    wdt.set(False)
    try:
        if app is not None:
            app.close()
    finally:
        displayio.release_displays()

if failed is not None:
    if in_a_row < BOOTLOOP_LIMIT:
        print("resetting")
        reset()
    halt("{}\n!! {} crashes in a row. Not resetting again: push a fixed\n"
         "code.py, or press reset to try once more.".format(report, in_a_row))
