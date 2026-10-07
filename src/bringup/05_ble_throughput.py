import time

import _bleio
from _bleio import UUID, Attribute, Characteristic, Service

NAME = b"bendcam"
UUID_FMT = "b3c1{:04x}-5eed-4a11-8c4e-6c0ffee00001"
WINDOW = 8
ACK_WAIT_S = 0.25

adapter = _bleio.adapter
adapter.enabled = True
service = Service(UUID(UUID_FMT.format(1)))
data = Characteristic.add_to_service(
    service,
    UUID(UUID_FMT.format(2)),
    properties=Characteristic.NOTIFY,
    read_perm=Attribute.OPEN,
    write_perm=Attribute.NO_ACCESS,
    max_length=512,
    fixed_length=False,
)
ctl = Characteristic.add_to_service(
    service,
    UUID(UUID_FMT.format(3)),
    properties=Characteristic.WRITE | Characteristic.WRITE_NO_RESPONSE,
    read_perm=Attribute.OPEN,
    write_perm=Attribute.OPEN,
    max_length=8,
    fixed_length=False,
    initial_value=b"\x00",
)


def acked():
    v = bytes(ctl.value)
    return int.from_bytes(v, "little") if len(v) == 4 else 0


def serve_one():
    ctl.value = b"\x00"
    adapter.start_advertising(
        bytes((2, 1, 6, len(NAME) + 1, 9)) + NAME, connectable=True
    )
    print("advertising as", NAME.decode(), adapter.address)
    while not adapter.connected:
        time.sleep(0.05)
    adapter.stop_advertising()
    conn = adapter.connections[0]
    print("connected")

    while conn.connected:
        v = bytes(ctl.value)
        if len(v) == 5 and v[:1] == b"G":
            n = int.from_bytes(v[1:], "little")
            break
        time.sleep(0.02)
    else:
        print("disconnected before a request")
        return

    size = conn.max_packet_length
    print("request", n, "bytes; packet", size, "interval", conn.connection_interval)
    chunk = bytearray(size)
    sent = 0
    rewinds = 0
    t = time.monotonic()
    while conn.connected:
        base = acked()
        if base >= n:
            break
        sent = max(sent, base)
        while sent < n and sent < base + WINDOW * size:
            k = min(size, n - sent)
            chunk[0:4] = sent.to_bytes(4, "little")
            data.value = chunk if k == size else chunk[:k]
            sent += k
        deadline = time.monotonic() + ACK_WAIT_S
        while acked() == base and time.monotonic() < deadline and conn.connected:
            pass
        if acked() == base:
            sent = base
            rewinds += 1
    dt = time.monotonic() - t
    got = acked()
    print(
        "delivered", got, "in", round(dt, 2), "s =",
        round(got / dt / 1024, 1), "KB/s, rewinds", rewinds,
    )
    time.sleep(1)
    for c in adapter.connections:
        c.disconnect()


while True:
    serve_one()
