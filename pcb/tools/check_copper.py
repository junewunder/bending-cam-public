#!/usr/bin/env python3

import json
import sys
from collections import defaultdict
from itertools import combinations

PATH = sys.argv[1] if len(sys.argv) > 1 else "dist/v3/v3/circuit.json"
TRACE_W = 0.3
CLEARANCE = 0.2
PAD_SNAP = 0.9

doc = json.load(open(PATH))
by_type = defaultdict(list)
for e in doc:
    by_type[e["type"]].append(e)
idx = {e.get("source_port_id") or e.get("pcb_port_id") or i: e for i, e in enumerate(doc)}


def seg_dist(p, q, r, s):

    def d_pt_seg(pt, a, b):
        ax, ay = a
        bx, by = b
        px, py = pt
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5

    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])

    if (ccw(p, q, r) > 0) != (ccw(p, q, s) > 0) and (ccw(r, s, p) > 0) != (
        ccw(r, s, q) > 0
    ):
        return 0.0
    return min(
        d_pt_seg(p, r, s), d_pt_seg(q, r, s), d_pt_seg(r, p, q), d_pt_seg(s, p, q)
    )


parent = {}


def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb


for st in by_type["source_trace"]:
    ports = st.get("connected_source_port_ids") or []
    nets = st.get("connected_source_net_ids") or []
    keys = [("p", p) for p in ports] + [("n", n) for n in nets]
    for a, b in zip(keys, keys[1:]):
        union(a, b)

src_port = {e["source_port_id"]: e for e in by_type["source_port"]}
src_comp = {e["source_component_id"]: e for e in by_type["source_component"]}
net_name = {e["source_net_id"]: e.get("name", "?") for e in by_type["source_net"]}


def label(key):
    kind, i = key
    if kind == "n":
        return net_name.get(i, "NET")
    p = src_port.get(i)
    if not p:
        return "?"
    c = src_comp.get(p["source_component_id"], {})
    return f"{c.get('name','?')}.{p.get('name','?')}"


def net_of_port(spid):
    root = find(("p", spid))
    members = [k for k in parent if find(k) == root]
    for k in members:
        if k[0] == "n":
            return net_name.get(k[1], "NET")
    return "NET:" + min(label(k) for k in members)


pcb_port = {e["pcb_port_id"]: e for e in by_type["pcb_port"]}
pads = []
for e in by_type["pcb_smtpad"] + by_type["pcb_plated_hole"]:
    pp = pcb_port.get(e.get("pcb_port_id"))
    if not pp:
        continue
    spid = pp.get("source_port_id")
    if not spid:
        continue
    pads.append((e["x"], e["y"], net_of_port(spid), label(("p", spid))))


def pad_at(x, y):
    best, bd = None, PAD_SNAP
    for px, py, net, name in pads:
        d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
        if d < bd:
            best, bd = (net, name), d
    return best


traces = []
for i, e in enumerate(by_type["pcb_trace"]):
    pts = [(p["x"], p["y"]) for p in e["route"] if "x" in p]
    if len(pts) < 2:
        continue
    ends = [pad_at(*pts[0]), pad_at(*pts[-1])]
    hit = [h for h in ends if h]
    net = hit[0][0] if hit else None
    layer = e["route"][0].get("layer", "top")
    traces.append({"i": i, "pts": pts, "net": net, "ends": ends, "layer": layer})

unknown = [t for t in traces if t["net"] is None]

for _ in range(6):
    for t in traces:
        if t["net"]:
            continue
        for u in traces:
            if not u["net"]:
                continue
            if any(
                abs(a[0] - b[0]) < 0.02 and abs(a[1] - b[1]) < 0.02
                for a in t["pts"]
                for b in u["pts"]
            ):
                t["net"] = u["net"]
                break


MIN_GAP = TRACE_W + CLEARANCE

shorts = []
for a, b in combinations(traces, 2):
    if a["net"] and b["net"] and a["net"] == b["net"]:
        continue
    if not a["net"] or not b["net"]:
        continue
    if a["layer"] != b["layer"]:
        continue
    for p, q in zip(a["pts"], a["pts"][1:]):
        for r, s in zip(b["pts"], b["pts"][1:]):
            d = seg_dist(p, q, r, s)
            if d < MIN_GAP:
                shorts.append((a["net"], b["net"], round(d, 3), p, r))
                break
        else:
            continue
        break

pad_hits = []
for px, py, pnet, pname in pads:
    for t in traces:
        if not t["net"] or t["net"] == pnet:
            continue
        for p, q in zip(t["pts"], t["pts"][1:]):
            d = seg_dist((px, py), (px, py), p, q)
            if d < 0.75 + CLEARANCE:
                pad_hits.append((pname, pnet, t["net"], round(d, 3)))
                break

cparent = {}


def cfind(a):
    cparent.setdefault(a, a)
    while cparent[a] != a:
        cparent[a] = cparent[cparent[a]]
        a = cparent[a]
    return a


def cunion(a, b):
    ra, rb = cfind(a), cfind(b)
    if ra != rb:
        cparent[ra] = rb


vias = [(v["x"], v["y"]) for v in by_type.get("pcb_via", [])]


def via_at(x, y):
    return any((x - vx) ** 2 + (y - vy) ** 2 < 0.25 for vx, vy in vias)


verts = []
for t in traces:
    keys = [("t", t["i"], k) for k in range(len(t["pts"]))]
    for k in keys[1:]:
        cunion(keys[0], k)
    for k, pt in zip(keys, t["pts"]):
        verts.append((k, pt, t["layer"]))

for (ka, pa, la), (kb, pb, lb) in combinations(verts, 2):
    if abs(pa[0] - pb[0]) < 0.05 and abs(pa[1] - pb[1]) < 0.05:
        if la == lb or via_at(*pa):
            cunion(ka, kb)

for k, pt, lyr in verts:
    for t in traces:
        if k[1] == t["i"] or t["layer"] != lyr:
            continue
        for p, q in zip(t["pts"], t["pts"][1:]):
            if seg_dist(pt, pt, p, q) < TRACE_W / 2 + 0.05:
                cunion(k, ("t", t["i"], 0))
                break

for i, (px, py, net, name) in enumerate(pads):
    for k, pt, lyr in verts:
        if ((pt[0] - px) ** 2 + (pt[1] - py) ** 2) ** 0.5 < PAD_SNAP:
            cunion(("pad", i), k)
    for t in traces:
        for p, q in zip(t["pts"], t["pts"][1:]):
            if seg_dist((px, py), (px, py), p, q) < 0.4:
                cunion(("pad", i), ("t", t["i"], 0))
                break

net_pads = defaultdict(list)
for i, (px, py, net, name) in enumerate(pads):
    net_pads[net].append((i, name))

unrouted = []
for net, plist in net_pads.items():
    if len(plist) < 2:
        continue
    groups = defaultdict(list)
    for i, name in plist:
        groups[cfind(("pad", i))].append(name)
    if len(groups) > 1:
        unrouted.append((net, [sorted(g) for g in groups.values()]))

print(f"traces: {len(traces)}   net inferred: {len(traces)-len([t for t in traces if not t['net']])}")
print(f"\nSHORTS (different nets closer than {MIN_GAP}mm): {len(shorts)}")
for s in shorts[:40]:
    print(f"  {s[0]:14s} <-> {s[1]:14s} gap={s[2]}mm near {tuple(round(v,2) for v in s[3])}")

print(f"\nPAD/COPPER CLASHES: {len(pad_hits)}")
for h in pad_hits[:40]:
    print(f"  pad {h[0]:14s} ({h[1]}) vs trace on {h[2]}  gap={h[3]}mm")

print(f"\nNETS NOT FULLY JOINED BY COPPER: {len(unrouted)}")
print("(GND is expected here — it is carried by the pours, not by traces.)")
for n, groups in sorted(unrouted):
    print(f"  {n}")
    for g in groups:
        print(f"      island: {', '.join(g)}")

if shorts or pad_hits:
    sys.exit(1)
