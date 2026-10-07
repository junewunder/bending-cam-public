#!/usr/bin/env python3

import argparse
import asyncio
import json
import sys
import time

from bleak import BleakClient, BleakScanner

NAME = "bendcam"
SETTINGS = "b3c10006-5eed-4a11-8c4e-6c0ffee00001"
PROTO = 1
WAIT_S = 5.0


def newest(client, uuid):
    chars = [ch for s in client.services for ch in s.characteristics if ch.uuid == uuid]
    if not chars:
        raise SystemExit("connected, but the camera has no settings service")
    return max(chars, key=lambda ch: ch.handle)


def value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


async def main(args):
    dev = await BleakScanner.find_device_by_name(NAME, timeout=30)
    if dev is None:
        raise SystemExit(f"no '{NAME}' advertising")
    async with BleakClient(dev) as client:
        char = newest(client, SETTINGS)
        lines = asyncio.Queue()
        got = bytearray()

        def on_notify(_, d):
            got.extend(d)
            while b"\n" in got:
                i = got.index(b"\n")
                lines.put_nowait((time.monotonic(), json.loads(bytes(got[:i]))))
                del got[: i + 1]

        await client.start_notify(char, on_notify)

        async def send(msg):
            await client.write_gatt_char(char, json.dumps(msg).encode() + b"\n", response=True)

        async def until(done, wait=WAIT_S):
            out = []
            end = time.monotonic() + wait
            while time.monotonic() < end:
                try:
                    t, m = await asyncio.wait_for(lines.get(), end - time.monotonic())
                except asyncio.TimeoutError:
                    break
                out.append((t, m))
                if done(m, out):
                    return out
            return out

        t0 = time.monotonic()
        await send({"get": "all"})
        dump = await until(lambda m, _: "end" in m)
        if not dump or "end" not in dump[-1][1]:
            raise SystemExit(f"no complete dump in {WAIT_S:.0f}s; got {[m for _, m in dump]}")
        proto = dump[0][1].get("proto")
        rows = [m for _, m in dump[1:-1]]
        n = dump[-1][1]["end"]
        dt = dump[-1][0] - t0
        print(f"proto {proto}, {len(rows)} of {n} settings in {dt:.2f}s")
        if proto != PROTO or len(rows) != n:
            raise SystemExit("!! the dump is not what this tool speaks")
        table = {r["k"]: r for r in rows}
        for r in rows:
            extra = {k: v for k, v in r.items() if k not in ("k", "label", "kind", "v")}
            print(f"  {r['k']:12} {r.get('v', '')!s:8} {r['kind']:6} {r['label']}  {extra}")

        if args.reset:
            want = {k for k, r in table.items() if r["kind"] != "action"}
            await send({"reset": "all"})
            echoes = await until(lambda _, out: {m.get("k") for _, m in out} >= want)
        elif args.send:
            await send(json.loads(args.send))
            echoes = await until(lambda m, _: True)
        elif args.key:
            row = table.get(args.key)
            v = None if args.value is None else value(args.value)
            if row and row["kind"] == "enum" and isinstance(v, str):
                v = row["opts"].index(v)
            await send({"k": args.key} if v is None else {"k": args.key, "v": v})
            echoes = await until(lambda m, _: m.get("k") == args.key)
        else:
            return
        t1 = time.monotonic()
        for t, m in echoes:
            print(f"<- {json.dumps(m)}  ({t - t1:+.2f}s)")
        if not echoes:
            print(f"!! no answer in {WAIT_S:.0f}s")
            sys.exit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("key", nargs="?", help="the setting to change, or the action to run")
    p.add_argument("value", nargs="?", help="JSON (true, 3) or an enum's option name")
    p.add_argument("--reset", action="store_true", help="every setting to its default")
    p.add_argument("--send", help="a raw JSON message; prints the first reply")
    asyncio.run(main(p.parse_args()))
