import gc
import time

import board
import busio
import digitalio
import espcamera

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
DATA_NAMES = ["IO5", "IO6", "IO7", "IO15", "IO16", "IO17", "IO18", "IO8"]
CAM_PCLK = board.IO9
CAM_VSYNC = board.IO11
CAM_HREF = board.IO10
CAM_SDA = board.IO12
CAM_SCL = board.IO13

XCLK_HZ = 24_000_000
FRAME_SIZE = espcamera.FrameSize.QQVGA
TAKE_TIMEOUT = 2.0

OV5640_ADDR = 0x3C
REG_CHIP_ID_HIGH = 0x300A

print("bring-up 03 (esp32-s3): camera")
gc.collect()
print("heap free at start: {} bytes".format(gc.mem_free()))

pwrdn = digitalio.DigitalInOut(CAM_PWRDN)
pwrdn.switch_to_output(False)
reset = digitalio.DigitalInOut(CAM_RESET)
reset.switch_to_output(False)
time.sleep(0.01)
reset.value = True
time.sleep(0.05)

i2c = busio.I2C(scl=CAM_SCL, sda=CAM_SDA)
while not i2c.try_lock():
    pass
try:
    found = i2c.scan()
    print("i2c devices:", [hex(a) for a in found])
    if OV5640_ADDR not in found:
        print("!! 0x3c not on the bus - check XCLK jumper, SDA/SCL/3V3/GND, RESET, PWRDN")
    else:
        idbuf = bytearray(2)
        i2c.writeto_then_readfrom(
            OV5640_ADDR,
            bytes([REG_CHIP_ID_HIGH >> 8, REG_CHIP_ID_HIGH & 0xFF]),
            idbuf,
        )
        chip_id = (idbuf[0] << 8) | idbuf[1]
        print("chip id: 0x{:04x} ({})".format(chip_id, "ok" if chip_id == 0x5640 else "UNEXPECTED"))
finally:
    i2c.unlock()

pwrdn.deinit()
reset.deinit()

t0 = time.monotonic()
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
    framebuffer_count=1,
    grab_mode=espcamera.GrabMode.LATEST,
)
gc.collect()
print("driver up in {:.2f}s: sensor {}, max frame size {}".format(
    time.monotonic() - t0, cam.sensor_name, cam.max_frame_size))
print("heap free after init: {} bytes".format(gc.mem_free()))


def take():
    t = time.monotonic()
    frame = cam.take(TAKE_TIMEOUT)
    dt = time.monotonic() - t
    if frame is None:
        print("!! take() timed out after {:.1f}s - no frame arrived.".format(TAKE_TIMEOUT))
        print("   init worked, so I2C is fine: suspect PCLK (IO9), VSYNC (IO11), HREF (IO10)")
        return None, dt
    return frame, dt


def structure(buf, w, h):
    stride = w * 2

    mismatch = 0
    pairs = 0
    for y in range(h // 4, min(h // 4 + 16, h - 1)):
        a = y * stride
        b = a + stride
        for x in range(0, stride, 2):
            pairs += 1
            if buf[a + x] != buf[b + x] or buf[a + x + 1] != buf[b + x + 1]:
                mismatch += 1

    base = (h // 2) * stride
    edges = 0
    in_edge = False
    prev = (buf[base] << 8) | buf[base + 1]
    for x in range(1, w):
        cur = (buf[base + x * 2] << 8) | buf[base + x * 2 + 1]
        step = abs(cur - prev) > 0x0400
        if step and not in_edge:
            edges += 1
        in_edge = step
        prev = cur

    pct = 100.0 * mismatch / pairs if pairs else 0.0
    print("  structure: {:.1f}% row-to-row mismatch, {} band edges across a row"
          .format(pct, edges))
    if pct < 5 and 4 <= edges <= 12:
        print("  -> clean colour bars. The parallel bus is carrying data intact.")
    elif pct > 30:
        print("  -> rows do not repeat: data is being corrupted in transit.")
        print("     bus integrity or sync, not a broken wire.")
    else:
        print("  -> pattern is present but not clean; see the numbers above.")


def analyse(label, check_structure=False):
    frame, dt = take()
    if frame is None:
        return None
    w, h = frame.width, frame.height
    buf = bytes(frame)[: w * h * 2]

    ever_high = 0
    ever_low = 0xFF
    lo = 0xFF
    hi = 0x00
    total = 0
    for b in buf:
        ever_high |= b
        ever_low &= b
        if b < lo:
            lo = b
        if b > hi:
            hi = b
        total += b

    print()
    print("--- {} ---".format(label))
    print("{}x{}, {} bytes, take() {:.3f}s, byte range {}..{}, mean {:.1f}".format(
        w, h, len(buf), dt, lo, hi, total / len(buf)))

    bad = []
    for bit in range(8):
        mask = 1 << bit
        high = bool(ever_high & mask)
        low = not (ever_low & mask)
        if high and low:
            state = "toggling"
        elif high:
            state = "STUCK HIGH"
            bad.append(bit)
        else:
            state = "STUCK LOW"
            bad.append(bit)
        print("  bit {} = D{} ({}): {}".format(bit, bit + 2, DATA_NAMES[bit], state))
    if check_structure:
        structure(buf, w, h)
    return bad


cam.colorbar = True
take()
time.sleep(0.2)
bad = analyse("internal colour-bar test pattern", check_structure=True)
if bad is None:
    pass
elif bad:
    print("!! suspect wires: " + ", ".join(
        "D{} ({})".format(b + 2, DATA_NAMES[b]) for b in bad))
    print("   with the test pattern on, every data line should toggle.")
else:
    print("all 8 data lines toggling - D2..D9 are good")

cam.colorbar = False
take()
time.sleep(0.2)
analyse("live sensor (point at something with contrast)")
print()
print("if the live frame is flat but the test pattern was fine, the bus is ok")
print("and the problem is optics/exposure, not wiring.")

n = 30
t0 = time.monotonic()
got = 0
for _ in range(n):
    if cam.take(TAKE_TIMEOUT) is not None:
        got += 1
dt = time.monotonic() - t0
print()
print("{} of {} frames in {:.2f}s = {:.1f} fps (camera only, {})".format(
    got, n, dt, got / dt if dt else 0, FRAME_SIZE))

print()
print("looping live captures - ctrl-c to stop")
while True:
    analyse("live")
    time.sleep(2)
