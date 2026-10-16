"""
DRC ueber der Generator-Geometrie (Schema-Architektur).

Sammlt alle Kupfer-Rechtecke pro Lage+Netz (LED-Pads rotiert,
F.Cu-Schienen+Stubs, Datenkette, Via-Pads, B.Cu-Rails, Eckpads) und
prueft:
  1. Clearance: gleiches Layer, fremdes Netz  >= DR.CLEARANCE (0.15)
     (Beruehrung nur bei gleichem Netz erlaubt = gewollte Verbindung)
  2. Randabstand aller Kupferecke >= DR.EDGE_CLEAR (0.20)
  3. Bohrung (0.3) -> fremdes Kupfer gleiches Layer >= 0.15 + 0.15
  4. Netzgraph: alle Kupferobjekte eines Netzes zusammenhaengend
     (Layerwechsel nur ueber Vias)

Aufruf: python drc_geometry.py [pitch] [cols] [rows]
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional, Tuple

import design_rules as DR
import power_grid as PG
from footprint import footprint_from_data
from matrix import generate_matrix
from data_chain import compute_data_chain
from power_grid import compute_power_grid

Rect = Tuple[float, float, float, float]
Seg = Tuple[float, float, float, float, float]   # x0,y0,x1,y1,w (Centerline)
Item = Tuple[str, str, Rect, str, Optional[Seg]] # layer, net, rect, tag, seg|None


def _rot(px, py, deg):
    import math
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return px * c - py * s, px * s + py * c


def _pt_seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return ((px - x0 - t * dx) ** 2 + (py - y0 - t * dy) ** 2) ** 0.5


def _seg_seg_dist(a, b):
    """Mindestabstand zweier Liniensegment-Mittellinien (0 bei Schnitt)."""
    ax0, ay0, ax1, ay1 = a[:4]
    bx0, by0, bx1, by1 = b[:4]
    def cross(ux, uy, vx, vy): return ux * vy - uy * vx
    r = (ax1 - ax0, ay1 - ay0)
    s = (bx1 - bx0, by1 - by0)
    den = cross(r[0], r[1], s[0], s[1])
    qp = (bx0 - ax0, by0 - ay0)
    if abs(den) > 1e-12:
        t = cross(qp[0], qp[1], s[0], s[1]) / den
        u = cross(qp[0], qp[1], r[0], r[1]) / den
        if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
            return 0.0
    cands = [
        _pt_seg_dist(ax0, ay0, bx0, by0, bx1, by1),
        _pt_seg_dist(ax1, ay1, bx0, by0, bx1, by1),
        _pt_seg_dist(bx0, by0, ax0, ay0, ax1, ay1),
        _pt_seg_dist(bx1, by1, ax0, ay0, ax1, ay1),
    ]
    return min(cands)


def _seg_rect_dist(seg, r):
    """Abstand Segment-Mittellinie zu Rechteck (0 bei Schnitt)."""
    x0, y0, x1, y1 = r
    if (seg[0] >= x0 - 1e-9 and seg[0] <= x1 + 1e-9
            and seg[1] >= y0 - 1e-9 and seg[1] <= y1 + 1e-9) or \
       (seg[2] >= x0 - 1e-9 and seg[2] <= x1 + 1e-9
            and seg[3] >= y0 - 1e-9 and seg[3] <= y1 + 1e-9):
        return 0.0
    edges = [((x0, y0, x1, y0),), ((x1, y0, x1, y1),),
             ((x0, y1, x1, y1),), ((x0, y0, x0, y1),)]
    return min(_seg_seg_dist(seg[:4], e[0]) for e in edges)


def shape_gap(a, b):
    """Mindestabstand zweier Kupferformen (0 bei Beruehrung/Ueberlappung)."""
    ra, rb = a[2], b[2]
    sa, sb = a[4] if len(a) > 4 else None, b[4] if len(b) > 4 else None
    if sa is None and sb is None:
        dx = max(rb[0] - ra[2], ra[0] - rb[2], 0.0)
        dy = max(rb[1] - ra[3], ra[1] - rb[3], 0.0)
        return (dx * dx + dy * dy) ** 0.5
    if sa is not None and sb is not None:
        return max(0.0, _seg_seg_dist(sa, sb) - sa[4] / 2 - sb[4] / 2)
    seg, rect = (sa, rb) if sa is not None else (sb, ra)
    return max(0.0, _seg_rect_dist(seg, rect) - seg[4] / 2)


def collect_copper(cols, rows, pitch, lcsc="C41413180", edge_pads=False):
    fp = footprint_from_data(lcsc)
    W, H = cols * pitch, rows * pitch
    leds = generate_matrix(cols, rows, pitch, fp)
    pg = compute_power_grid(leds, fp, W, H, pitch, edge_pads=edge_pads)
    dc = compute_data_chain(leds, fp, W, H, pitch)

    copper: List[tuple] = []   # 4- oder 5-Tupel, wird unten normalisiert

    # F.Cu LED-Pads
    for led in leds:
        for p in fp.pads:
            ox, oy = _rot(p.x, p.y, led.rotation)
            w, h = (p.height, p.width) if int(led.rotation) % 180 == 90 \
                else (p.width, p.height)
            cx, cy = led.x + ox, led.y + oy
            net = {"GND": "GND", "VDD": "VCC"}.get(p.signal,
                  led.nets[p.signal])
            copper.append(("F.Cu", net,
                           (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                           f"pad {p.signal} {led.ref}"))

    # F.Cu Schienen + Stubs
    for rail in pg["rails_top"]:
        y, w = rail["y"], rail["w"]
        copper.append(("F.Cu", rail["net"],
                       (rail["x0"], y - w / 2, rail["x1"], y + w / 2),
                       f"rail {rail['net']} y={y:.2f}"))
        for (sx, pe) in rail["stubs"]:
            y0, y1 = sorted((y, pe))
            copper.append(("F.Cu", rail["net"],
                           (sx - PG.STUB_W / 2, y0,
                            sx + PG.STUB_W / 2, y1),
                           f"stub {rail['net']} x={sx:.2f}"))

    # F.Cu Datenkette (echte Segmente, keine Baeume)
    for i, (x0, y0, x1, y1, net) in enumerate(dc["segs"]):
        w = dc["trace_w"]
        if abs(x0 - x1) < 1e-9:      # vertikal: BBox in X aufweiten
            bbox = (x0 - w / 2, min(y0, y1), x0 + w / 2, max(y0, y1))
        else:
            bbox = (min(x0, x1), min(y0, y1) - w / 2,
                    max(x0, x1), max(y0, y1) + w / 2)
        copper.append(("F.Cu", net, bbox,
                       f"data seg {i}", (x0, y0, x1, y1, w)))

    # Via-Pads auf beiden Lagen
    for (x, y, net, pd) in pg["stitch_vias"]:
        r = (x - pd / 2, y - pd / 2, x + pd / 2, y + pd / 2)
        copper.append(("F.Cu", net, r, "stitch via"))
        copper.append(("B.Cu", net, r, "stitch via"))
    first, last = leds[0], leds[-1]
    entry_nets = [first.nets["DI"], last.nets["DO"]]
    for (x, y), net in zip(dc["vias"], entry_nets):
        r = (x - DR.VIA_PAD_D / 2, y - DR.VIA_PAD_D / 2,
             x + DR.VIA_PAD_D / 2, y + DR.VIA_PAD_D / 2)
        copper.append(("F.Cu", net, r, "entry via"))
        copper.append(("B.Cu", net, r, "entry via"))

    # B.Cu Rails + Eckpads
    for net, rect in pg["rails_bottom"]:
        copper.append(("B.Cu", net, rect, f"rail_bottom {net}"))
    cp_net = {"DIN": first.nets["DI"], "DOUT": last.nets["DO"]}
    for name, rect in pg["corner_pads"].items():
        copper.append(("B.Cu", cp_net[name], rect, f"corner {name}"))

    # alle Objekte einheitlich auf 5-Tupel (seg=None fuer Rechtecke)
    copper = [it if len(it) == 5 else it + (None,) for it in copper]

    return copper, (leds, pg, dc, W, H)


def _gap(a: Rect, b: Rect) -> Tuple[float, float]:
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return dx, dy


def run(pitch: float, cols: int = 8, rows: int = 8, lcsc: str = "C41413180",
        edge_pads: bool = False):
    copper, (leds, pg, dc, W, H) = collect_copper(cols, rows, pitch, lcsc,
                                                  edge_pads)
    problems: List[str] = []

    # --- 1+2: Clearance + Randabstand ----------------------------------
    n = len(copper)
    for i in range(n):
        l1, n1, r1, t1, _s1 = copper[i]
        # Randabstand (Anschlusspads DIN/DOUT sind bewusst randbuendig)
        if not t1.startswith("corner") and (
                r1[0] < DR.EDGE_CLEAR - 1e-6 or r1[1] < DR.EDGE_CLEAR - 1e-6
                or r1[2] > W - DR.EDGE_CLEAR + 1e-6
                or r1[3] > H - DR.EDGE_CLEAR + 1e-6):
            problems.append(f"{l1}: {t1} [{n1}] Randabstand < "
                            f"{DR.EDGE_CLEAR}: {r1}")
        for j in range(i + 1, n):
            l2, n2, r2, t2, _s2 = copper[j]
            if l1 != l2 or n1 == n2:
                continue
            if shape_gap(copper[i], copper[j]) < DR.CLEARANCE - 1e-9:
                problems.append(
                    f"{l1}: {t1} [{n1}] vs {t2} [{n2}] "
                    f"Abstand < {DR.CLEARANCE}")

    # --- 3: Bohrung -> fremdes Kupfer ----------------------------------
    drill_r = DR.VIA_DRILL / 2
    holes = [(x, y, n) for (x, y, n, _pd) in pg["stitch_vias"]]
    first, last = leds[0], leds[-1]
    holes += [(x, y, n) for (x, y), n in
              zip(dc["vias"], [first.nets["DI"], last.nets["DO"]])]
    for (hx, hy, hnet) in holes:
        for item in copper:
            l2, n2, r2, t2, s2 = item
            if n2 == hnet:
                continue          # Via haengt an eigenem Netz: ok
            if s2 is None:
                dx = max(r2[0] - hx, hx - r2[2], 0.0)
                dy = max(r2[1] - hy, hy - r2[3], 0.0)
                d = (dx * dx + dy * dy) ** 0.5
            else:
                d = max(0.0, _pt_seg_dist(hx, hy, *s2[:4]) - s2[4] / 2)
            if d < drill_r + DR.CLEARANCE - 1e-9:
                problems.append(f"Bohrung ({hx:.2f},{hy:.2f}) [{hnet}] -> "
                                f"{l2} {t2} [{n2}] Abstand < "
                                f"{drill_r + DR.CLEARANCE}")

    # --- 4: Netzgraph-Konnektivitaet ------------------------------------
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        l1, n1, r1, _, _ = copper[i]
        for j in range(i + 1, n):
            l2, n2, r2, _, _ = copper[j]
            if n1 != n2:
                continue
            if shape_gap(copper[i], copper[j]) <= 1e-9:   # Beruehrung
                union(i, j)
    groups: Dict[str, Dict[int, List[str]]] = {}
    for i, (l1, n1, r1, t1, _s) in enumerate(copper):
        groups.setdefault(n1, {}).setdefault(find(i), []).append(t1)
    for net, comps in groups.items():
        if len(comps) > 1:
            sizes = sorted((len(v) for v in comps.values()), reverse=True)
            problems.append(f"Netz {net}: {len(comps)} getrennte Kupfer-"
                            f"Inseln (Groessen {sizes[:6]})")

    print(f"pitch={pitch} {cols}x{rows}: {len(copper)} Kupferobjekte, "
          f"{len(holes)} Bohrungen, {len(groups)} Netze")
    if problems:
        print(f"\n{len(problems)} PROBLEME:")
        for p in problems[:50]:
            print("  -", p)
    else:
        print("DRC OK")
    return len(problems)


if __name__ == "__main__":
    pitch = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    ep = "--edge-pads" in sys.argv[4:]
    sys.exit(1 if run(pitch, cols, rows, edge_pads=ep) else 0)
