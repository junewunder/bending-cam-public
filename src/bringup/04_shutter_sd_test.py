import os
import time

import board
import busio
import digitalio
import displayio
import sdcardio
import storage

TFT_MISO = board.IO48
TFT_SCK = board.IO47
TFT_MOSI = board.IO38
SD_CS = board.IO42
SHUTTER = board.IO1

print("bring-up 04 (esp32-s3): shutter + sd")

shutter = digitalio.DigitalInOut(SHUTTER)
shutter.switch_to_input(pull=digitalio.Pull.UP)
print("shutter idle reads {} (should be True - pressing pulls it low)".format(shutter.value))

displayio.release_displays()
spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI, MISO=TFT_MISO)

sd_ok = False
card = None
try:
    card = sdcardio.SDCard(spi, SD_CS)
    vfs = storage.VfsFat(card)
    storage.mount(vfs, "/sd")
    sd_ok = True
except OSError as err:
    print("!! sd mount failed:", err)
    print("   check the card is inserted and formatted FAT32, and SD_CS")

if sd_ok:
    print("card: {} blocks ({:.1f} GB)".format(card.count(), card.count() * 512 / 1e9))
    print("/sd contents:", os.listdir("/sd"))
    with open("/sd/shutter_log.txt", "a") as f:
        f.write("--- boot {} (esp32-s3) ---\n".format(time.monotonic()))
    print("wrote to /sd/shutter_log.txt")

    payload = bytes(i & 0xFF for i in range(32768))
    t = time.monotonic()
    with open("/sd/_bringup04.bin", "wb") as f:
        for _ in range(8):
            f.write(payload)
    w = time.monotonic() - t
    t = time.monotonic()
    ok = True
    with open("/sd/_bringup04.bin", "rb") as f:
        for _ in range(8):
            if f.read(len(payload)) != payload:
                ok = False
    r = time.monotonic() - t
    os.remove("/sd/_bringup04.bin")
    print("262144-byte file: write {:.2f}s, read {:.2f}s, read-back {}".format(
        w, r, "matches" if ok else "!! MISMATCH"))

print("press the shutter")

presses = 0
was_pressed = False
while True:
    pressed = not shutter.value
    if pressed and not was_pressed:
        presses += 1
        line = "press {} at {:.2f}s".format(presses, time.monotonic())
        print(line)
        if sd_ok:
            with open("/sd/shutter_log.txt", "a") as f:
                f.write(line + "\n")
    was_pressed = pressed
    time.sleep(0.02)
