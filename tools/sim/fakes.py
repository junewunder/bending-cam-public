import errno
import os as _real_os
import struct
import sys
import types
import zlib

REPO_UI = ""

FRAME_S = 0.006
BLIT_S = 0.033
CARD_BYTES_S = 1_000_000
MAX_SLEEP_S = 600
QVGA = (320, 240)
XGA = (1024, 768)


class Reset(BaseException):
    pass


class Stop(KeyboardInterrupt):
    pass


def crc(b):
    return "{:08x}".format(zlib.crc32(bytes(b)))


def module(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m


class Enum:
    def __init__(self, cls, name):
        self.cls = cls
        self.name = name

    def __repr__(self):
        return "{}.{}".format(self.cls, self.name)

    __str__ = __repr__


class Card:

    def __init__(self, capacity):
        self.files = {}
        self.capacity = capacity
        self.inserted = True

    def used(self):
        return sum(len(b) for b in self.files.values())


class File:
    def __init__(self, w, path, mode):
        self.w = w
        self.path = path
        self.name = path.rsplit("/", 1)[-1]
        self.card = w.mounted
        self.pos = 0
        self.closed = False
        w.check_card(self.card)
        files = self.card.files
        if "w" in mode:
            files[self.name] = bytearray()
        elif "a" in mode:
            files.setdefault(self.name, bytearray())
            self.pos = len(files[self.name])
        elif self.name not in files:
            raise OSError(errno.ENOENT, "no such file")
        w.clock.advance(0.002)
        w.add("file", "open", path, mode)

    def buf(self):
        self.w.check_card(self.card)
        if self.name not in self.card.files:
            raise OSError(errno.ENOENT, "removed while open")
        return self.card.files[self.name]

    def write(self, data):
        seen = data.replace("\n", "\\n") if isinstance(data, str) else None
        data = data.encode() if isinstance(data, str) else bytes(data)
        b = self.buf()
        if self.card.used() + len(data) > self.card.capacity:
            self.w.add("file", "write", self.path, len(data), "ENOSPC")
            raise OSError(errno.ENOSPC, "full")
        b[self.pos : self.pos + len(data)] = data
        self.pos += len(data)
        self.w.clock.advance(len(data) / CARD_BYTES_S)
        self.w.add("file", "write", self.path, len(data), seen or crc(data))
        return len(data)

    def readinto(self, into):
        b = self.buf()
        n = min(len(into), len(b) - self.pos)
        into[:n] = b[self.pos : self.pos + n]
        self.pos += n
        self.w.clock.advance(n / CARD_BYTES_S)
        return n

    def read(self, n=-1):
        b = self.buf()
        end = len(b) if n < 0 else min(len(b), self.pos + n)
        out = bytes(b[self.pos : end])
        self.pos = end
        return out

    def seek(self, pos):
        self.pos = pos

    def tell(self):
        return self.pos

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.w.add("file", "close", self.path)
        self.w.check_card(self.card)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Bitmap(bytearray):
    def __init__(self, size, fill):
        super().__init__(bytes((fill,)) * (size[0] * size[1] * 2))
        self.width, self.height = size


class Char:
    def __init__(self, w, uuid, initial):
        self.w = w
        self.uuid = uuid[4:8]
        self._value = bytes(initial)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = bytes(v)
        self._value = v
        self.w.notified(self, v)


class Connection:
    def __init__(self, w):
        self.w = w
        self.max_packet_length = 244

    def disconnect(self):
        self.w.add("ble", "disconnect")
        self.w.ble_connected = False


class Adapter:
    def __init__(self, w):
        self.w = w
        self._enabled = False
        self.advertising = False

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, v):
        self._enabled = v
        self.w.add("ble", "enabled", v)

    @property
    def connected(self):
        return self.w.ble_connected

    @property
    def connections(self):
        return (self.w.conn,) if self.w.ble_connected else ()

    def start_advertising(self, data, connectable=True):
        self.advertising = True
        self.w.add("ble", "advertise", crc(data))

    def stop_advertising(self):
        self.advertising = False
        self.w.add("ble", "stop advertising")


class Sensor:

    def __init__(self):
        self.regs = {}
        for base, vals in (
            (0x3034, (0x18, 0x21, 0x14, 0x13)),
            (0x3108, (0x01,)),
            (0x380C, (0x07, 0x68)),
            (0x380E, (0x03, 0xD8)),
            (0x3500, (0x00, 0x37, 0x50)),
            (0x350A, (0x00, 0x54)),
            (0x3400, (0x04, 0x74, 0x04, 0x00, 0x07, 0xE6)),
            (0x3A0F, (0x38, 0x30, 0x61)),
            (0x3A1B, (0x38,)),
            (0x3A1E, (0x30, 0x10)),
        ):
            for i, v in enumerate(vals):
                self.regs[base + i] = v


class World:
    def __init__(self, sc):
        self.sc = sc
        self.trace = []
        self.clock = Clock()
        self.card = Card(sc.get("capacity", 1 << 30))
        self.card.inserted = sc.get("card", True)
        self.mounted = None
        self.sensor = Sensor()
        self.nvm = Nvm(self, sc.get("nvm_size", 4096))
        for off, blob in sc.get("nvm", {}).items():
            bytearray.__setitem__(self.nvm, slice(off, off + len(blob)), blob)
        self.ram = sc.get("ram", 4_000_000)
        self.keys = []
        self.ble_connected = False
        self.conn = Connection(self)
        self.chars = {}
        self.phone = {"fid": None, "skip": False}
        self.preview = 0
        self.still = False
        self.i2c_fail = False
        self.fill = 0
        self.timed = []
        self.wdt_fed = None
        self.wdt_gap = 0.0
        self.app = None

    def add(self, *ev):
        self.trace.append(" ".join(str(e) for e in ev))

    def check_card(self, card):
        if card is None or not card.inserted or card is not self.mounted:
            raise OSError(errno.EIO, "card gone")

    def notified(self, ch, v):
        if ch.uuid == "0006":
            self.add("ble", "settings", v.decode("utf-8", "replace").rstrip())
        elif ch.uuid == "0003":
            return
        elif ch.uuid == "0002":
            self.phone_data(v)

    def phone_data(self, v):
        if v[:4] == b"\xff\xff\xff\xff":
            fid, size, left = struct.unpack_from("<HIH", v, 4)
            self.add("ble", "header", fid, size, left, v[12:].decode())
            self.phone["fid"] = fid
            off = 0xFFFFFFFF if self.phone["skip"] else 0
        else:
            (off,) = struct.unpack_from("<I", v)
            self.add("ble", "data", off, len(v) - 4, crc(v[4:]))
            off += len(v) - 4
        self.chars["0003"]._value = struct.pack("<HI", self.phone["fid"], off)


    def next_frame(self):
        n = self.preview
        self.preview += 1
        if n >= self.sc["frames"]:
            raise Stop()
        self.due()
        self.add("--- frame", n)
        for act in self.sc.get("at", {}).get(n, ()):
            self.act(act)
        for secs, act in self.sc.get("then", {}).get(n, ()):
            self.timed.append((self.clock.t + secs, act))
        self.timed.sort(key=lambda ta: ta[0])
        if any(a <= n < b for a, b in self.sc.get("miss", ())):
            self.clock.advance(2.0)
            return None
        self.clock.advance(FRAME_S)
        if not any(a <= n < b for a, b in self.sc.get("frozen", ())):
            self.fill = (self.fill + 1) & 0xFF
        return Bitmap(QVGA, self.fill)

    def due(self):
        while self.timed and self.timed[0][0] <= self.clock.t:
            self.act(self.timed.pop(0)[1])

    def act(self, act):
        self.add("scenario", act)
        name, _, arg = act.partition(" ")
        if name == "press":
            self.keys.append((0, self.clock.ms()))
        elif name == "boot":
            self.keys.append((1, self.clock.ms()))
        elif name == "pull":
            self.card.inserted = False
        elif name == "insert":
            self.card.inserted = True
        elif name == "ram":
            self.ram = int(arg)
        elif name == "connect":
            self.ble_connected = True
        elif name == "disconnect":
            self.ble_connected = False
        elif name == "write":
            self.chars["0006"]._value = arg.encode()
        elif name == "skip":
            self.phone["skip"] = arg == "on"
        elif name == "rm":
            self.card.files.pop(arg, None)
        elif name == "i2c_fail":
            self.i2c_fail = True
        else:
            raise ValueError("unknown scenario action " + act)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def advance(self, dt):
        self.t += dt

    def ms(self):
        return int(self.t * 1000) & ((1 << 29) - 1)


class Nvm(bytearray):

    def __init__(self, w, n):
        super().__init__(n)
        self.w = w

    def __setitem__(self, k, v):
        bytearray.__setitem__(self, k, v)
        if isinstance(k, slice):
            self.w.add("nvm", hex(k.start), crc(v))
        else:
            self.w.add("nvm", hex(k), v)


def install(w):
    clock = w.clock

    def sleep(s):
        clock.advance(s)
        w.due()
        if clock.t > 1000.0 + MAX_SLEEP_S:
            w.add("sleeping for good")
            raise Stop()

    time_m = module("time", monotonic=lambda: clock.t, sleep=sleep,
                    monotonic_ns=lambda: int(clock.t * 1e9))
    gc_m = module("gc", collect=lambda: None, mem_free=lambda: 7_700_000,
                  mem_alloc=lambda: 100_000, enable=lambda: None,
                  disable=lambda: None)
    mp_m = module("micropython", kbd_intr=lambda x: w.add("kbd_intr", x))

    def card_path(path):
        if not path.startswith("/sd/") and path != "/sd":
            raise OSError(errno.ENOENT, path)
        if w.mounted is None:
            raise OSError(errno.ENOENT, path)
        w.check_card(w.mounted)
        return path[4:]

    def listdir(path):
        card_path(path + "/")
        return sorted(w.mounted.files)

    def remove(path):
        name = card_path(path)
        if name not in w.mounted.files:
            raise OSError(errno.ENOENT, path)
        del w.mounted.files[name]
        w.add("file", "remove", path)

    def rename(a, b):
        na, nb = card_path(a), card_path(b)
        w.mounted.files[nb] = w.mounted.files.pop(na)
        w.add("file", "rename", a, b)

    def stat(path):
        name = card_path(path)
        if name not in w.mounted.files:
            raise OSError(errno.ENOENT, path)
        return (0, 0, 0, 0, 0, 0, len(w.mounted.files[name]))

    os_m = module("os", listdir=listdir, remove=remove, rename=rename, stat=stat)
    os_m.__getattr__ = lambda name: getattr(_real_os, name)  # type: ignore[attr-defined]

    def open_(path, mode="r"):
        if path == "/ui.bin":
            import io

            with open(REPO_UI, "rb") as f:
                return io.BytesIO(f.read())
        card_path(path)
        return File(w, path, mode)

    class Watchdog:
        timeout = 0

        def __init__(self):
            self._mode = None

        @property
        def mode(self):
            return self._mode

        @mode.setter
        def mode(self, v):
            self._mode = v
            w.wdt_fed = clock.t if v else None
            w.add("wdt", "mode", v)

        def feed(self):
            if w.wdt_fed is not None:
                w.wdt_gap = max(w.wdt_gap, clock.t - w.wdt_fed)
                w.wdt_fed = clock.t
            w.add("wdt", "feed")

    RR = {n: Enum("microcontroller.ResetReason", n)
          for n in ("POWER_ON", "SOFTWARE", "WATCHDOG", "RESET_PIN")}

    def reset():
        w.add("reset")
        raise Reset()

    mc_m = module(
        "microcontroller",
        watchdog=Watchdog(),
        nvm=w.nvm,
        cpu=types.SimpleNamespace(reset_reason=RR[w.sc.get("reset", "POWER_ON")]),
        ResetReason=types.SimpleNamespace(**RR),
        reset=reset,
    )
    RUN = {n: Enum("supervisor.RunReason", n) for n in ("STARTUP", "REPL_RELOAD")}
    sup_m = module(
        "supervisor",
        runtime=types.SimpleNamespace(autoreload=True,
                                      run_reason=RUN[w.sc.get("run", "STARTUP")]),
        RunReason=types.SimpleNamespace(**RUN),
        ticks_ms=clock.ms,
    )
    wd_m = module("watchdog", WatchDogMode=types.SimpleNamespace(RESET="RESET"))

    class VfsFat:
        def __init__(self, sd):
            self.sd = sd

    def mount(vfs, path):
        if not vfs.sd.card.inserted:
            raise OSError(errno.EIO, "mount failed")
        w.mounted = vfs.sd.card
        w.add("storage", "mount", path)

    def umount(path):
        w.mounted = None
        w.add("storage", "umount", path)

    storage_m = module(
        "storage", VfsFat=VfsFat, mount=mount, umount=umount,
        getmount=lambda p: types.SimpleNamespace(readonly=not w.sc.get("field", False)),
    )

    class SPI:
        def __init__(self, clock=None, MOSI=None, MISO=None):
            w.add("spi", "new")

        def try_lock(self):
            return True

        def unlock(self):
            pass

        def configure(self, baudrate=0, **kw):
            w.add("spi", "configure", baudrate)

        def write(self, b):
            w.add("spi", "write", crc(b))

        def write_readinto(self, out, into):
            into[0] = 0xFF

        def readinto(self, buf, write_value=0):
            for i in range(len(buf)):
                buf[i] = 0xFF
            if w.card.inserted:
                buf[1] = 0x01
            w.add("spi", "cmd0", "answered" if w.card.inserted else "silent")

    class I2C:
        def __init__(self, scl=None, sda=None):
            w.add("i2c", "new")

        def try_lock(self):
            return True

        def unlock(self):
            pass

        def _fail(self):
            if w.i2c_fail:
                w.i2c_fail = False
                raise OSError(errno.EIO, "sensor gone")

        def writeto(self, addr, b):
            self._fail()
            reg = b[0] << 8 | b[1]
            for i, v in enumerate(b[2:]):
                w.sensor.regs[reg + i] = v
            w.add("i2c", "w {:04x}".format(reg), bytes(b[2:]).hex())

        def writeto_then_readfrom(self, addr, out, into):
            self._fail()
            reg = out[0] << 8 | out[1]
            for i in range(len(into)):
                into[i] = w.sensor.regs.get(reg + i, 0)
            w.add("i2c", "r {:04x}".format(reg), len(into))

    busio_m = module("busio", SPI=SPI, I2C=I2C)

    class DigitalInOut:
        def __init__(self, pin):
            self.pin = pin

        @property
        def value(self):
            if self.pin == "IO1":
                return not w.sc.get("shutter_held", False)
            return True

        @value.setter
        def value(self, v):
            pass

        def switch_to_output(self, value=False):
            pass

        def switch_to_input(self, pull=None):
            pass

        def deinit(self):
            pass

    digitalio_m = module("digitalio", DigitalInOut=DigitalInOut,
                         Pull=types.SimpleNamespace(UP="UP", DOWN="DOWN"))
    board_m = module("board")
    board_m.__getattr__ = lambda name: name  # type: ignore[attr-defined]

    class SDCard:
        def __init__(self, spi, cs, baudrate=0):
            if not w.card.inserted:
                w.add("sdcard", "none")
                raise OSError(errno.ENODEV, "no SD card")
            self.card = w.card
            w.add("sdcard", "new", baudrate)

        def deinit(self):
            w.add("sdcard", "deinit")

    sdcardio_m = module("sdcardio", SDCard=SDCard)

    class FourWire:
        def __init__(self, spi, **kw):
            w.add("panel", "bus")

        def send(self, cmd, data):
            data = bytes(data)
            if len(data) > 1000:
                clock.advance(BLIT_S * len(data) / 153600)
            w.add("panel", "{:02x}".format(cmd), len(data), crc(data))

    class ST7789:
        def __init__(self, bus, **kw):
            w.add("panel", "init")
            self.auto_refresh = True
            self.root_group = None

    displayio_m = module("displayio", release_displays=lambda: w.add("displayio release"),
                         CIRCUITPYTHON_TERMINAL="terminal")
    fourwire_m = module("fourwire", FourWire=FourWire)
    st7789_m = module("adafruit_st7789", ST7789=ST7789)

    FS = types.SimpleNamespace(QVGA=QVGA, XGA=XGA)

    class Camera:
        address = 0x3C
        sensor_name = "OV5640"

        def __init__(self, frame_size=QVGA, **kw):
            self.size = frame_size
            w.still = frame_size != QVGA
            w.add("camera", "new", frame_size)

        def __setattr__(self, k, v):
            if k in ("hmirror", "vflip"):
                w.add("camera", k, v)
            object.__setattr__(self, k, v)

        def take(self, timeout):
            if w.still:
                clock.advance(0.3)
                w.add("camera", "take still")
                return Bitmap(XGA, 0x5A)
            return w.next_frame()

        def reconfigure(self, frame_size=QVGA, **kw):
            self.size = frame_size
            w.still = frame_size != QVGA
            w.add("camera", "reconfigure", frame_size)

        def deinit(self):
            w.add("camera", "deinit")

    espcamera_m = module(
        "espcamera", Camera=Camera, FrameSize=FS,
        PixelFormat=types.SimpleNamespace(RGB565="RGB565"),
        GrabMode=types.SimpleNamespace(LATEST="LATEST"),
    )
    espidf_m = module("espidf", heap_caps_get_largest_free_block=lambda: w.ram,
                      heap_caps_get_free_size=lambda: w.ram + 100_000)

    class Swap:
        def __init__(self, buf):
            self.buf = buf

        def byteswap(self, inplace=False):
            b = self.buf
            b[0::2], b[1::2] = b[1::2], b[0::2]

    def frombuffer(buf, dtype=None):
        return memoryview(buf).cast("B") if dtype == "uint8" else Swap(buf)

    np_m = module("ulab.numpy", frombuffer=frombuffer, uint8="uint8", uint16="uint16")
    ulab_m = module("ulab", numpy=np_m)

    class Event:
        key_number = 0
        pressed = False
        timestamp = 0

    class Events:
        overflowed = False

        def get_into(self, ev):
            if not w.keys:
                return False
            ev.key_number, ev.timestamp = w.keys.pop(0)
            ev.pressed = True
            return True

        def clear(self):
            w.keys.clear()

    class Keys:
        def __init__(self, pins, **kw):
            self.events = Events()

    keypad_m = module("keypad", Keys=Keys, Event=Event)
    analogio_m = module("analogio", AnalogIn=lambda pin: types.SimpleNamespace(value=0))

    class Characteristic:
        NOTIFY = 1
        WRITE = 2
        WRITE_NO_RESPONSE = 4

        @staticmethod
        def add_to_service(service, uuid, initial_value=b"", **kw):
            c = Char(w, uuid, initial_value)
            w.chars[c.uuid] = c
            w.add("ble", "characteristic", c.uuid)
            return c

    class BluetoothError(Exception):
        pass

    bleio_m = module(
        "_bleio", adapter=Adapter(w), Characteristic=Characteristic,
        Service=lambda uuid: uuid, UUID=lambda s: s,
        Attribute=types.SimpleNamespace(OPEN=1, NO_ACCESS=0),
        BluetoothError=BluetoothError,
    )

    for m in (time_m, gc_m, mp_m, os_m, mc_m, sup_m, wd_m, storage_m, busio_m,
              digitalio_m, board_m, sdcardio_m, displayio_m, fourwire_m, st7789_m,
              espcamera_m, espidf_m, np_m, ulab_m, keypad_m, analogio_m, bleio_m):
        sys.modules[m.__name__] = m

    def print_(*args, sep=" ", end="\n"):
        w.add("print:", sep.join(str(a) for a in args))

    return {"open": open_, "print": print_}
