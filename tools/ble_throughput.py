#!/usr/bin/env python3

import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

NAME = "bendcam"
DATA = "b3c10002-5eed-4a11-8c4e-6c0ffee00001"
CTL = "b3c10003-5eed-4a11-8c4e-6c0ffee00001"
ACK_EVERY = 4


def newest(client, uuid):
    chars = [ch for s in client.services for ch in s.characteristics if ch.uuid == uuid]
    return max(chars, key=lambda ch: ch.handle)


async def main(n):
    dev = await BleakScanner.find_device_by_name(NAME, timeout=30)
    if dev is None:
        raise SystemExit(f"no '{NAME}' advertising -- is bring-up 05 running?")
    async with BleakClient(dev) as client:
        await client._backend._acquire_mtu()  # pyright: ignore[reportAttributeAccessIssue]
        data, ctl = newest(client, DATA), newest(client, CTL)
        acks = asyncio.Queue()
        st = {"exp": 0, "packets": 0, "gaps": 0, "t0": None}

        def on_packet(_, d):
            if st["t0"] is None:
                st["t0"] = time.monotonic()
            off = int.from_bytes(d[:4], "little")
            if off == st["exp"]:
                st["exp"] += len(d)
                st["packets"] += 1
                if st["packets"] % ACK_EVERY == 0 or st["exp"] >= n:
                    acks.put_nowait(st["exp"])
            elif off > st["exp"]:
                st["gaps"] += 1
                acks.put_nowait(st["exp"])

        await client.start_notify(data, on_packet)
        await client.write_gatt_char(ctl, b"G" + n.to_bytes(4, "little"), response=True)
        last = None
        while st["exp"] < n:
            try:
                a = await asyncio.wait_for(acks.get(), 5)
            except asyncio.TimeoutError:
                print("stalled at", st["exp"])
                break
            if a != last:
                await client.write_gatt_char(ctl, a.to_bytes(4, "little"), response=False)
                last = a
        dt = time.monotonic() - (st["t0"] or time.monotonic())
        print(
            f"mtu {client.mtu_size}: {st['exp']} of {n} bytes in {dt:.2f} s"
            f" = {st['exp'] / max(dt, 1e-9) / 1024:.1f} KB/s, gaps {st['gaps']}"
        )


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 400_000))
