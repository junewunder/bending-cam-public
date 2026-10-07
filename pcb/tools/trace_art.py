import json
import pathlib
import subprocess
import sys
import tempfile

PX_PER_MM = 40
GROW_MM = 0.08
INK_THRESHOLD = "70%"


def bounds(ring):
    xs, ys = [v["x"] for v in ring], [v["y"] for v in ring]
    return min(xs), min(ys), max(xs), max(ys)


def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def trace(png, box, tmp):
    x0, y0, x1, y1 = box
    ink = tmp / "ink.png"
    run("magick", png, "-background", "white", "-alpha", "remove", "-alpha", "off",
        "-colorspace", "gray", "-threshold", "90%", "-trim", "+repage", ink)
    w, h = (int(n) for n in run("magick", "identify", "-format", "%w %h", ink).split())
    mm_per_px = min((x1 - x0) / w, (y1 - y0) / h)
    grow = round(GROW_MM * PX_PER_MM)
    pbm = tmp / "art.pbm"
    run("magick", png, "-background", "white", "-alpha", "remove", "-alpha", "off",
        "-colorspace", "gray", "-trim", "+repage",
        "-resize", f"{round(w * mm_per_px * PX_PER_MM)}x{round(h * mm_per_px * PX_PER_MM)}!",
        "-threshold", INK_THRESHOLD, "-negate",
        "-morphology", "Dilate", f"Disk:{grow}", "-negate", pbm)
    rendered = tmp / "art.geojson"
    run("potrace", "-b", "geojson", "-t", "4", pbm, "-o", rendered)
    features = json.load(open(rendered))["features"]

    aw, ah = w * mm_per_px, h * mm_per_px
    ox, oy = (x0 + x1 - aw) / 2, (y0 + y1 - ah) / 2
    s = 1 / PX_PER_MM
    polygons = [
        [[[ox + px * s, oy + py * s] for px, py in ring] for ring in f["geometry"]["coordinates"]]
        for f in features
    ]
    return polygons, pbm


def main():
    circuit, out = json.load(open(sys.argv[1])), sys.argv[2]
    preview = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None
    art = {}
    for e in circuit:
        if e["type"] != "pcb_silkscreen_graphic":
            continue
        src = e["image_asset"]["project_relative_path"].removeprefix("file://")
        if e["image_asset"]["mimetype"] != "image/png" or not pathlib.Path(src).is_file():
            sys.exit(f"!! {e['pcb_silkscreen_graphic_id']}: not a local PNG: {src}")
        with tempfile.TemporaryDirectory() as tmp:
            polygons, pbm = trace(src, bounds(e["brep_shape"]["outer_ring"]["vertices"]),
                                  pathlib.Path(tmp))
            if preview:
                preview.mkdir(parents=True, exist_ok=True)
                run("magick", pbm, preview / f"{pathlib.Path(src).stem}.png")
        art[e["pcb_silkscreen_graphic_id"]] = {"layer": e["layer"], "polygons": polygons}
        print(f"{pathlib.Path(src).name}: {len(polygons)} polygons")
    json.dump(art, open(out, "w"))


main()
