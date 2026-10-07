#!/usr/bin/env python3

import asyncio
import os
import struct
import sys
import time

from bleak import BleakClient, BleakScanner

NAME = "bendcam"
DATA = "b3c10002-5eed-4a11-8c4e-6c0ffee00001"
CTL = "b3c10003-5eed-4a11-8c4e-6c0ffee00001"
HEADER = 0xFFFFFFFF
SKIP = 0xFFFFFFFF
ACK_EVERY = 4


def newest(client, uuid):
    chars = [ch for s in client.services for ch in s.characteristics if ch.uuid == uuid]
    return max(chars, key=lambda ch: ch.handle)


async def session(outdir, screens_only):
    dev = await BleakScanner.find_device_by_name(NAME, timeout=30)
    if dev is None:
        print(f"no '{NAME}' advertising; retrying")
        return
    disconnected = asyncio.Event()
    async with BleakClient(dev, disconnected_callback=lambda _: disconnected.set()) as client:
        data, ctl = newest(client, DATA), newest(client, CTL)
        acks = asyncio.Queue()
        cur = {}
        done = {}

        def ack(off, fid=None):
            acks.put_nowait(struct.pack("<HI", cur["fid"] if fid is None else fid, off))

        def on_packet(_, d):
            off = struct.unpack_from("<I", d)[0]
            if off == HEADER:
                fid, size, queued = struct.unpack_from("<HIH", d, 4)
                name = bytes(d[12:]).decode()
                cur.clear()
                if screens_only and "_screen" not in name:
                    print(f"-- {name} skipped, {queued} more queued", flush=True)
                    ack(SKIP, fid)
                    return
                cur.update(fid=fid, size=size, name=name,
                           buf=bytearray(size), exp=0, n=0, t0=time.monotonic())
                print(f"<- {name} ({size} bytes, {queued} more queued)", flush=True)
                ack(0)
            elif not cur:
                if done:
                    ack(done["size"], done["fid"])
                return
            elif off == cur["exp"]:
                body = d[4:]
                cur["buf"][off : off + len(body)] = body
                cur["exp"] += len(body)
                cur["n"] += 1
                if cur["exp"] >= cur["size"]:
                    ack(cur["exp"])
                    path = os.path.join(outdir, cur["name"])
                    with open(path, "wb") as f:
                        f.write(cur["buf"])
                    dt = time.monotonic() - cur["t0"]
                    print(f"   saved {path} in {dt:.1f}s, {cur['size'] / dt / 1024:.1f} KB/s",
                          flush=True)
                    done.update(fid=cur["fid"], size=cur["size"])
                    cur.clear()
                elif cur["n"] % ACK_EVERY == 0:
                    ack(cur["exp"])
                    if cur["n"] % 400 == 0:
                        print(f"   {cur['exp'] * 100 // cur['size']}%", flush=True)
            else:
                ack(cur["exp"])

        await client.start_notify(data, on_packet)
        print(f"connected to {dev.address}; waiting for stills", flush=True)
        while not disconnected.is_set():
            try:
                msg = await asyncio.wait_for(acks.get(), 1)
            except asyncio.TimeoutError:
                continue
            await client.write_gatt_char(ctl, msg, response=False)
    print("disconnected")


async def main(outdir, screens_only):
    os.makedirs(outdir, exist_ok=True)
    while True:
        try:
            await session(outdir, screens_only)
        except Exception as err:
            print("!!", type(err).__name__, err)
        await asyncio.sleep(1)


args = sys.argv[1:]
screens = "--screens" in args
args = [a for a in args if a != "--screens"]
try:
    asyncio.run(main(args[0] if args else "stills", screens))
except KeyboardInterrupt:
    pass
