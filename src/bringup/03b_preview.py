import gc
import time

import board
import busio
import displayio
import espcamera
from adafruit_st7789 import ST7789
from fourwire import FourWire

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
CAM_PCLK = board.IO9
CAM_VSYNC = board.IO11
CAM_HREF = board.IO10
CAM_SDA = board.IO12
CAM_SCL = board.IO13

TFT_MISO = board.IO48
TFT_SCK = board.IO47
TFT_MOSI = board.IO38
TFT_CS = board.IO39
TFT_RST = board.IO40
TFT_DC = board.IO41

PANEL_W = 320
PANEL_H = 240
ROTATION = 270
PANEL_MADCTL = 0x20

SPI_BAUD = 40_000_000

XCLK_HZ = 24_000_000
FRAME_SIZE = espcamera.FrameSize.QVGA
TAKE_TIMEOUT = 2.0

FLIP_X = True
FLIP_Y = True

BYTE_SWAP = False

_CASET = 0x2A
_RASET = 0x2B
_RAMWR = 0x2C
_MADCTL = 0x36

print("bring-up 03b (esp32-s3): live preview")

displayio.release_displays()
spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=SPI_BAUD)
display = ST7789(bus, width=PANEL_W, height=PANEL_H, rotation=ROTATION)
display.auto_refresh = False
display.root_group = None
bus.send(_MADCTL, bytes((PANEL_MADCTL,)))
print("panel up at {} Hz SPI".format(SPI_BAUD))

i2c = busio.I2C(scl=CAM_SCL, sda=CAM_SDA)
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
cam.hmirror = FLIP_X
cam.vflip = FLIP_Y
gc.collect()
print("camera up: {}, heap free {}".format(cam.sensor_name, gc.mem_free()))

frame = cam.take(TAKE_TIMEOUT)
if frame is None:
    raise RuntimeError("no first frame -- run 03_camera_test.py")
W, H = frame.width, frame.height
x0 = (PANEL_W - W) // 2
y0 = (PANEL_H - H) // 2
x1 = x0 + W - 1
y1 = y0 + H - 1
print("frame {}x{} at panel ({},{})".format(W, H, x0, y0))

if W % 16:
    raise ValueError("width {} pads its rows; the raw blit would shear".format(W))

bus.send(_CASET, bytes((x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)))
bus.send(_RASET, bytes((y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)))

swapped = bytearray(W * H * 2) if BYTE_SWAP else None

frames = 0
misses = 0
take_s = 0.0
send_s = 0.0
t_report = time.monotonic()
while True:
    t = time.monotonic()
    frame = cam.take(TAKE_TIMEOUT)
    t2 = time.monotonic()
    take_s += t2 - t
    if frame is None:
        misses += 1
        print("!! take() timed out ({} so far)".format(misses))
        continue

    if BYTE_SWAP:
        raw = memoryview(frame)
        src = bytes(raw)
        swapped[0::2] = src[1::2]
        swapped[1::2] = src[0::2]
        bus.send(_RAMWR, swapped)
    else:
        bus.send(_RAMWR, frame)
    send_s += time.monotonic() - t2

    frames += 1
    if frames % 60 == 0:
        now = time.monotonic()
        dt = now - t_report
        print("{:.1f} fps  take {:.0f} ms  send {:.0f} ms  misses {}".format(
            60 / dt, 1000 * take_s / 60, 1000 * send_s / 60, misses))
        take_s = send_s = 0.0
        t_report = now
