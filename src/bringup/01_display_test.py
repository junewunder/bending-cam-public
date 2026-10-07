import time

import board
import busio
import displayio
from fourwire import FourWire
from adafruit_st7789 import ST7789

TFT_MISO = board.IO48
TFT_SCK = board.IO47
TFT_MOSI = board.IO38
TFT_CS = board.IO39
TFT_RST = board.IO40
TFT_DC = board.IO41

PANEL_W = 320
PANEL_H = 240
ROTATION = 270
SPI_BAUD = 24_000_000

BARS = [
    0xFFFFFF,
    0xFFFF00,
    0x00FFFF,
    0x00FF00,
    0xFF00FF,
    0xFF0000,
    0x0000FF,
    0x000000,
]

print("bring-up 01 (esp32-s3): display")

displayio.release_displays()
spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=SPI_BAUD)
display = ST7789(bus, width=PANEL_W, height=PANEL_H, rotation=ROTATION)
display.auto_refresh = False
print("display up: {}x{}".format(display.width, display.height))

root = displayio.Group()

cell_w = PANEL_W // 8
cell_h = PANEL_H // 6
bars_bmp = displayio.Bitmap(8, 6, len(BARS))
bars_pal = displayio.Palette(len(BARS))
for i, colour in enumerate(BARS):
    bars_pal[i] = colour
    for y in range(6):
        bars_bmp[i, y] = i
bars_group = displayio.Group(scale=cell_w)
bars_group.append(displayio.TileGrid(bars_bmp, pixel_shader=bars_pal))
root.append(bars_group)

border_bmp = displayio.Bitmap(PANEL_W, PANEL_H, 2)
border_pal = displayio.Palette(2)
border_pal[0] = 0x000000
border_pal[1] = 0xFFFFFF
border_pal.make_transparent(0)
for x in range(PANEL_W):
    border_bmp[x, 0] = 1
    border_bmp[x, PANEL_H - 1] = 1
for y in range(PANEL_H):
    border_bmp[0, y] = 1
    border_bmp[PANEL_W - 1, y] = 1
root.append(displayio.TileGrid(border_bmp, pixel_shader=border_pal))

BLOCK = 24
block_bmp = displayio.Bitmap(BLOCK, BLOCK, 1)
block_pal = displayio.Palette(1)
block_pal[0] = 0xFF0000
block = displayio.TileGrid(block_bmp, pixel_shader=block_pal, x=10, y=10)
root.append(block)

display.root_group = root
display.refresh(minimum_frames_per_second=0)

print("bars: white yellow cyan green magenta red blue black")
print("cell size {}x{} (bars are {} wide)".format(cell_w, cell_h, cell_w))

dx, dy = 3, 2
frames = 0
t0 = time.monotonic()
while True:
    block.x += dx
    block.y += dy
    if block.x <= 0 or block.x >= PANEL_W - BLOCK:
        dx = -dx
    if block.y <= 0 or block.y >= PANEL_H - BLOCK:
        dy = -dy
    display.refresh(minimum_frames_per_second=0)

    frames += 1
    if frames == 60:
        now = time.monotonic()
        print("{:.1f} fps".format(frames / (now - t0)))
        frames = 0
        t0 = now
