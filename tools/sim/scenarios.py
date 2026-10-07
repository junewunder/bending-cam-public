import json
import struct


def saved_settings(d):
    body = json.dumps(d, separators=(",", ":")).encode()
    return {0x400: b"\xbc\x5e" + struct.pack("<H", len(body)) + body}


def boot_counts(boots, crashes, in_a_row):
    return {0x80: b"\xbc\x03" + bytes((boots, crashes, in_a_row)) + bytes(17)}


SCENARIOS = {
    "idle": dict(frames=70),
    "press": dict(frames=170, at={40: ["press"]}),
    "presses": dict(
        frames=300,
        at={40: ["press", "press"], 42: ["press"], 44: ["press", "press", "press"]},
    ),
    "no_ram": dict(frames=90, at={30: ["ram 100000"], 31: ["press"],
                                  50: ["ram 4000000"], 51: ["press"]}),
    "pull_mid_save": dict(frames=420, at={30: ["press"], 45: ["pull"], 130: ["insert"]}),
    "no_card": dict(frames=260, card=False, at={20: ["press"], 60: ["insert"],
                                                 80: ["press"]}),
    "full": dict(frames=170, capacity=400_000, at={30: ["press"], 100: ["press"]}),
    "drought": dict(frames=130, miss=[(20, 34)], at={25: ["press"], 40: ["press"]}),
    "drought_pull": dict(frames=160, miss=[(40, 60)], at={
        20: ["press"], 24: ["pull"], 30: ["connect"], 32: ['write {"k":"ev","v":2}'],
        50: ["insert"]}),
    "frozen": dict(frames=100, frozen=[(10, 50)]),
    "ble": dict(
        frames=420,
        at={
            10: ["connect"],
            14: ['write {"get":"all"}'],
            40: ["press"],
            50: ['write {"k":"exposure","v":2}'],
            60: ['write {"k":"wb","v":6}'],
            80: ['write {"k":"iso","v":800}\n{"k":"ev","v":3}'],
            100: ['write {"k":"shift","v":true}'],
            130: ['write {"k":"shift","v":false}'],
            150: ["write not json"],
            160: ['write {"reset":"all"}'],
            170: ['write {"k":"nope","v":1}'],
            200: ["boot"],
            230: ["connect", "skip on"],
            240: ["press"],
            300: ["skip off", "disconnect"],
            310: ["connect"],
        },
    ),
    "review": dict(
        frames=260,
        at={
            5: ["connect"],
            8: ['write {"get":"all"}'],
            20: ["press"],
            30: ["press"],
            60: ['write {"review":"next"}'],
            140: ['write {"review":"enter"}'],
            150: ['write {"review":"enter"}'],
            170: ['write {"review":"enter"}'],
            180: ["connect", 'write {"review":"enter"}'],
            190: ['write {"review":"enter"}'],
            200: ["pull", 'write {"review":"enter"}'],
            210: ["insert"],
        },
        then={
            140: [(0.1, 'write {"review":"prev"}'), (0.2, 'write {"review":"prev","by":3}'),
                  (0.3, 'write {"review":"next","by":"x"}'),
                  (0.4, 'write {"review":"send","files":["IMG_0001.bmp","IMG_0001_screen.bmp","log.txt"]}'),
                  (0.5, 'write {"review":"send","files":"IMG_0001.bmp"}'),
                  (0.6, 'write {"review":"zoom"}'), (0.7, 'write {"review":"enter"}'),
                  (0.8, "press")],
            150: [(0.1, 'write {"review":"prev"}'), (0.3, "disconnect")],
            170: [(0.1, 'write {"review":"exit"}'), (0.2, 'write {"review":"exit"}'),
                  (0.3, 'write {"review":"next"}')],
            180: [(0.1, 'write {"review":"prev"}'), (121.0, 'write {"review":"next"}')],
            190: [(0.1, "pull"), (0.2, 'write {"review":"prev"}')],
        },
    ),
    "review_landing": dict(
        frames=120,
        at={5: ["connect"], 20: ["press"], 22: ["press"],
            24: ['write {"review":"enter"}']},
        then={24: [(0.1, "rm IMG_0001_screen.bmp"), (0.5, 'write {"review":"prev"}'),
                   (1.0, 'write {"review":"next"}'), (8.0, 'write {"review":"exit"}')]},
    ),
    "lock": dict(frames=130, nvm=saved_settings({"exposure": 1, "wb": 1}),
                 at={60: ["press"]}),
    "held": dict(frames=40, shutter_held=True,
                 nvm=saved_settings({"exposure": 2, "shift": True})),
    "crash": dict(frames=60, at={25: ["i2c_fail"]}),
    "bootloop": dict(frames=10, reset="SOFTWARE", nvm=boot_counts(9, 9, 3)),
    "field": dict(frames=40, field=True, at={10: ["press"]}),
}
