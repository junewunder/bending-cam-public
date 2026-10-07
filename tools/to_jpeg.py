#!/usr/bin/env python3

import os
import sys

from PIL import Image

JPEG_QUALITY = 90


def convert(bmp, quality=JPEG_QUALITY):
    jpg = os.path.splitext(bmp)[0] + ".jpg"
    with Image.open(bmp) as im:
        im.convert("RGB").save(jpg, "JPEG", quality=quality)
    return jpg


def bmps(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(".bmp"):
                    yield os.path.join(p, name)
        else:
            yield p


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    failed = 0
    done = 0
    for bmp in bmps(argv):
        try:
            print("{} -> {}".format(bmp, convert(bmp)))
            done += 1
        except OSError as err:
            print("!! {}: {}".format(bmp, err), file=sys.stderr)
            failed += 1
    if not done and not failed:
        print("no .bmp files in {}".format(" ".join(argv)), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
