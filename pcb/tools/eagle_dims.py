#!/usr/bin/env python3

import argparse
import math
import xml.etree.ElementTree as ET

DIMENSION, TOP, BOTTOM = "20", "1", "16"
BODY_LAYERS = ("21", "22", "51", "52")


def num(el: ET.Element, name: str, default: float | None = None) -> float:
    v = el.get(name)
    if v is None:
        if default is None:
            raise ValueError(f"<{el.tag}> has no {name} attribute")
        return default
    return float(v)


def text(el: ET.Element, name: str, default: str = "") -> str:
    return el.get(name) or default


def place(x: float, y: float, ex: float, ey: float, rot: str) -> tuple[float, float]:
    if rot.startswith("M"):
        x = -x
    angle = math.radians(float(rot.lstrip("MR") or 0))
    c, s = math.cos(angle), math.sin(angle)
    return ex + x * c - y * s, ey + x * s + y * c


class Hole:
    def __init__(
        self, part: str, package: str, x: float, y: float, drill: float, plated: bool
    ):
        self.part, self.package = part, package
        self.x, self.y, self.drill, self.plated = x, y, drill, plated


class Pad:
    def __init__(self, name: str, x: float, y: float, drill: float, kind: str):
        self.name, self.x, self.y, self.drill, self.kind = name, x, y, drill, kind


class Board:
    def __init__(self, path: str):
        board = ET.parse(path).getroot().find(".//board")
        if board is None:
            raise ValueError(f"{path} has no <board> -- is it a .sch?")
        self.board = board
        self.packages = {
            text(p, "name"): p
            for lib in board.findall(".//libraries/library")
            for p in lib.findall("packages/package")
        }
        self.elements = board.findall("elements/element")

    def _placement(self, e: ET.Element) -> tuple[float, float, str]:
        return num(e, "x"), num(e, "y"), text(e, "rot", "R0")

    def outline(self) -> tuple[float, float, float, float, float, int] | None:
        xs: list[float] = []
        ys: list[float] = []
        curves: list[ET.Element] = []
        for w in self.board.findall("plain/wire"):
            if w.get("layer") != DIMENSION:
                continue
            if w.get("curve"):
                curves.append(w)
                continue
            xs += [num(w, "x1"), num(w, "x2")]
            ys += [num(w, "y1"), num(w, "y2")]
        if not xs:
            return None
        radius = 0.0
        if curves:
            w = curves[0]
            chord = math.hypot(num(w, "x2") - num(w, "x1"), num(w, "y2") - num(w, "y1"))
            radius = chord / math.sqrt(2)
        return min(xs), min(ys), max(xs), max(ys), radius, len(curves)

    def holes(self) -> list[Hole]:
        out = [
            Hole("plain", "", num(h, "x"), num(h, "y"), num(h, "drill"), False)
            for h in self.board.findall("plain/hole")
        ]
        for e in self.elements:
            pkg = self.packages.get(text(e, "package"))
            if pkg is None:
                continue
            ex, ey, rot = self._placement(e)
            name, pname = text(e, "name"), text(e, "package")
            for h in pkg.findall("hole"):
                x, y = place(num(h, "x"), num(h, "y"), ex, ey, rot)
                out.append(Hole(name, pname, x, y, num(h, "drill"), False))
            if "MOUNTINGHOLE" in pname.upper():
                for p in pkg.findall("pad"):
                    x, y = place(num(p, "x"), num(p, "y"), ex, ey, rot)
                    out.append(Hole(name, pname, x, y, num(p, "drill"), True))
        return out

    def part(self, name: str) -> ET.Element | None:
        return next((e for e in self.elements if e.get("name") == name), None)

    def pads(self, e: ET.Element) -> list[Pad]:
        pkg = self.packages.get(text(e, "package"))
        if pkg is None:
            return []
        ex, ey, rot = self._placement(e)
        out: list[Pad] = []
        for p in pkg.findall("pad"):
            x, y = place(num(p, "x"), num(p, "y"), ex, ey, rot)
            out.append(Pad(text(p, "name"), x, y, num(p, "drill"), "THT"))
        for p in pkg.findall("smd"):
            x, y = place(num(p, "x"), num(p, "y"), ex, ey, rot)
            top = (p.get("layer") == TOP) != rot.startswith("M")
            out.append(Pad(text(p, "name"), x, y, 0.0, "SMD/top" if top else "SMD/bot"))
        return out

    def body(self, e: ET.Element) -> tuple[float, float, float, float] | None:
        pkg = self.packages.get(text(e, "package"))
        if pkg is None:
            return None
        ex, ey, rot = self._placement(e)
        pts = [
            place(num(w, a), num(w, b), ex, ey, rot)
            for w in pkg.findall("wire")
            if w.get("layer") in BODY_LAYERS
            for a, b in (("x1", "y1"), ("x2", "y2"))
        ]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


INTERESTING = (
    "HEADER",
    "1X",
    "2X",
    "FPC",
    "EYE",
    "CONN",
    "MICROSD",
    "SD",
    "PIN",
    "TFT",
    "CAM",
    "OV",
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("brd")
    ap.add_argument(
        "-p",
        "--part",
        action="append",
        default=[],
        help="dump this part's pads; repeatable",
    )
    ap.add_argument(
        "-a",
        "--all-parts",
        action="store_true",
        help="list every element, not just connectors",
    )
    args = ap.parse_args()

    b = Board(args.brd)
    box = b.outline()
    if box is None:
        print("no layer-20 outline in this file")
        return
    x0, y0, x1, y1, radius, ncurve = box
    corners = f"   corner r{radius:.2f} x{ncurve}" if radius else ""
    print(f"outline   {x1 - x0:.2f} x {y1 - y0:.2f} mm{corners}")
    print(f"          origin at ({x0:.2f}, {y0:.2f}), far corner ({x1:.2f}, {y1:.2f})")

    holes = b.holes()
    if holes:
        print("\nholes                          x       y     drill   from outline SW")
        for h in sorted(holes, key=lambda h: (-h.drill, h.x)):
            tag = f"{h.part} {h.package}".strip()[:24]
            plated = "P" if h.plated else " "
            print(
                f"  {tag:<24} {h.x:8.3f}{h.y:8.3f}   {h.drill:5.2f}{plated}"
                f"  ({h.x - x0:6.2f},{h.y - y0:6.2f})"
            )

    print("\nparts")
    for e in b.elements:
        pkg = text(e, "package")
        if not args.all_parts and not any(k in pkg.upper() for k in INTERESTING):
            continue
        print(
            f"  {text(e, 'name'):<8} {pkg:<32} "
            f"({num(e, 'x'):7.3f},{num(e, 'y'):7.3f}) {text(e, 'rot', 'R0')}"
        )

    for name in args.part:
        e = b.part(name)
        if e is None:
            print(f"\n{name}: no such element")
            continue
        print(
            f"\n{name}  {text(e, 'package')}  at ({num(e, 'x')}, {num(e, 'y')}) "
            f"{text(e, 'rot', 'R0')}"
        )
        body = b.body(e)
        if body:
            print(
                f"  body {body[2] - body[0]:.2f} x {body[3] - body[1]:.2f} mm, "
                f"({body[0]:.2f},{body[1]:.2f}) to ({body[2]:.2f},{body[3]:.2f})"
            )
        pads = b.pads(e)
        print("  pad            x       y     drill  type      from outline SW")
        for p in pads:
            print(
                f"  {p.name:<8} {p.x:8.3f}{p.y:8.3f}   {p.drill:5.2f}  {p.kind:<8} "
                f"({p.x - x0:6.2f},{p.y - y0:6.2f})"
            )
        if len(pads) > 1:
            xs = sorted({round(p.x, 3) for p in pads})
            ys = sorted({round(p.y, 3) for p in pads})
            if len(xs) > 1:
                print(f"  x span {xs[-1] - xs[0]:.2f} over {len(xs)} columns")
            if len(ys) > 1:
                print(f"  y span {ys[-1] - ys[0]:.2f} over {len(ys)} rows")


if __name__ == "__main__":
    main()
