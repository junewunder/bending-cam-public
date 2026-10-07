import json
import math
import sys

import pcbnew  # pyright: ignore[reportMissingImports] -- KiCad's own Python only

STROKE_MIN_MM = 0.15
STROKE_RATIO = 0.15
SILK = {pcbnew.F_SilkS, pcbnew.B_SilkS}


def exported_for_back(fp):
    items = list(fp.GetFields()) + list(fp.GraphicalItems())
    return not fp.IsFlipped() and any(i.GetLayer() == pcbnew.B_SilkS for i in items)


def flip_to_back(fp):
    ref = fp.GetReference()
    pads = {p.GetNumber(): (p.GetPosition(), p.GetNetCode()) for p in fp.Pads()}
    items = list(fp.GetFields()) + list(fp.GraphicalItems())
    layers = [i.GetLayer() for i in items]
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for p in fp.Pads():
        pos, net = pads[p.GetNumber()]
        p.SetPosition(pos)
        assert p.GetNetCode() == net
    for item, layer in zip(items, layers):
        item.SetLayer(layer)
    print(f"{ref}: flipped to B.Cu, {len(pads)} pads held in place")


def crosses_pad(seg, pad):
    (ax, ay), (bx, by) = (
        (seg.GetStart().x, seg.GetStart().y),
        (seg.GetEnd().x, seg.GetEnd().y),
    )
    px, py = pad.GetPosition().x, pad.GetPosition().y
    dx, dy = bx - ax, by - ay
    t = (
        0.0
        if dx == dy == 0
        else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    )
    return (
        math.hypot(ax + t * dx - px, ay + t * dy - py)
        <= max(pad.GetSizeX(), pad.GetSizeY()) / 2
    )


def strip_footprint_silk(board):
    fields, texts, shapes = [], [], []
    for fp in board.GetFootprints():
        fields += [f for f in fp.GetFields() if f.GetLayer() in SILK and f.IsVisible()]
        pads = list(fp.Pads())
        for item in fp.GraphicalItems():
            if item.GetLayer() not in SILK:
                continue
            if isinstance(item, pcbnew.PCB_TEXT):
                texts.append((fp, item))
            elif item.GetShape() == pcbnew.SHAPE_T_SEGMENT and any(
                crosses_pad(item, p) for p in pads
            ):
                shapes.append((fp, item))
    for field in fields:
        field.SetVisible(False)
    for fp, item in texts + shapes:
        fp.Remove(item)
    print(
        f"footprint silk: {len(fields) + len(texts)} texts and {len(shapes)} pad-crossing segments removed"
    )


def board_centre(board):
    edge = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    xs = [p.x for d in edge for p in (d.GetStart(), d.GetEnd())]
    ys = [p.y for d in edge for p in (d.GetStart(), d.GetEnd())]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def art_shapes(board, polygons, at, layer):
    shapes = []
    for rings in polygons:
        ps = pcbnew.SHAPE_POLY_SET()
        outline = ps.NewOutline()
        for x, y in rings[0]:
            p = at({"x": x, "y": y})
            ps.Append(p.x, p.y, outline)
        for hole in rings[1:]:
            h = ps.NewHole(outline)
            for x, y in hole:
                p = at({"x": x, "y": y})
                ps.Append(p.x, p.y, outline, h)
        ps.Fracture()
        for i in range(ps.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(ps.Outline(i))
            shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
            shape.SetPolyShape(one)
            shape.SetFilled(True)
            shape.SetWidth(0)
            shape.SetLayer(layer)
            shapes.append(shape)
    return shapes


def restore_board_shapes(board, circuit, art):
    (bc,) = [e["center"] for e in circuit if e["type"] == "pcb_board"]
    kx, ky = board_centre(board)

    def at(pt):
        return pcbnew.VECTOR2I(
            int(kx + pcbnew.FromMM(pt["x"] - bc["x"])),
            int(ky - pcbnew.FromMM(pt["y"] - bc["y"])),
        )

    added = graphics = 0
    for e in circuit:
        if not e["type"].startswith("pcb_silkscreen_") or e.get("pcb_component_id"):
            continue
        if e["type"] == "pcb_silkscreen_text":
            continue
        layer = pcbnew.B_SilkS if e["layer"] == "bottom" else pcbnew.F_SilkS
        if e["type"] == "pcb_silkscreen_graphic":
            traced = art.get(e["pcb_silkscreen_graphic_id"])
            if traced is None:
                sys.exit(f"!! {e['pcb_silkscreen_graphic_id']} was never traced")
            for shape in art_shapes(board, traced["polygons"], at, layer):
                board.Add(shape)
            graphics += 1
            continue
        c = e["center"]
        if e["type"] == "pcb_silkscreen_rect":
            shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECTANGLE)
            w, h = e["width"] / 2, e["height"] / 2
            shape.SetStart(at({"x": c["x"] - w, "y": c["y"] + h}))
            shape.SetEnd(at({"x": c["x"] + w, "y": c["y"] - h}))
            shape.SetFilled(bool(e.get("is_filled")))
        elif e["type"] == "pcb_silkscreen_circle":
            shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
            shape.SetCenter(at(c))
            shape.SetEnd(at({"x": c["x"] + e["radius"], "y": c["y"]}))
        else:
            sys.exit(
                f"!! board-level {e['type']} would be dropped by the export; not handled here"
            )
        shape.SetLayer(layer)
        shape.SetWidth(pcbnew.FromMM(max(STROKE_MIN_MM, e.get("stroke_width", 0))))
        board.Add(shape)
        added += 1
    print(f"board silk: {added} rects/circles restored from circuit.json, {graphics} graphics drawn")


def finish_board_text(board):
    mirrored = 0
    for item in board.GetDrawings():
        if not isinstance(item, pcbnew.PCB_TEXT) or item.GetLayer() not in SILK:
            continue
        h = pcbnew.ToMM(item.GetTextHeight())
        item.SetTextThickness(pcbnew.FromMM(max(STROKE_MIN_MM, STROKE_RATIO * h)))
        if item.GetLayer() == pcbnew.B_SilkS and not item.IsMirrored():
            item.SetMirrored(True)
            mirrored += 1
    print(f"board text: stroke set, {mirrored} back-side texts mirrored")


def main():
    path, circuit, art = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
    board = pcbnew.LoadBoard(path)
    for fp in [fp for fp in board.GetFootprints() if exported_for_back(fp)]:
        flip_to_back(fp)
    finish_board_text(board)
    restore_board_shapes(board, circuit, art)
    strip_footprint_silk(board)
    board.Save(path)


main()
