"""
Datenkette auf F.Cu (Schema-Vorlage: tools/layout_schema.py).

Kette: horizontale Serpentine ab oben-links (matrix.py).
Routing-Regeln (vom User vorgegeben):
  - innerhalb einer Reihe: 45°-Diagonale, wenn noetig mit horizontalen
    Anschlussstuecken an die Padkanten
  - zwischen den Reihen: DIREKTE vertikale Verbindung. Durch die relative
    90°-Drehung der geraden Reihen ueberlappen sich DO-/DI-Pad in X
    (~0.4 mm); die Vertikale steht in der Ueberlappungszone.
  - DIN (oben-links) / DOUT (unten-links): je 1 Via vom B.Cu-Eckpad
    zur F.Cu-Kette; Zulauf horizontal bzw. 45° + horizontal.
Die Rand-/Zwischenreihen-Schienen enden an der aeussersten Power-Pad-
Kante; die Vertikalen der Reihenuebergaenge liegen ausserhalb dieser
Enden -> keine Kreuzung Daten/Power.

Alle Pad-Kanten werden aus den Footprint-Daten berechnet (kein
Hardcoding). Masse mm, Ursprung links-unten.
"""
from __future__ import annotations
import math
from typing import List, Tuple

TRACE_DATA = 0.15
VIA_D = 0.3          # Bohr-Durchmesser DIN/DOUT-Via
VIA_P = 0.6          # Pad-Durchmesser

Seg = Tuple[float, float, float, float, str]


def _pad_edges(led, signal: str, fp):
    """Gedrehte Pad-Kanten: (cx, cy, x0, x1, y0, y1)."""
    for p in fp.pads:
        if p.signal == signal:
            a = math.radians(led.rotation)
            ox = p.x * math.cos(a) - p.y * math.sin(a)
            oy = p.x * math.sin(a) + p.y * math.cos(a)
            w, h = (p.height, p.width) if int(led.rotation) % 180 == 90 \
                else (p.width, p.height)
            cx, cy = led.x + ox, led.y + oy
            return cx, cy, cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    raise KeyError(signal)


def compute_data_chain(leds, fp, W: float, H: float, pitch: float) -> dict:
    """Berechnet F.Cu-Datenkette: Segmente + DIN/DOUT-Entry-Vias."""
    cols = max(l.col for l in leds) + 1
    by_index = {l.index: l for l in leds}

    segs: List[Seg] = []

    def poly(pts, net):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            segs.append((x0, y0, x1, y1, net))

    for i in range(len(leds) - 1):
        a, b = by_index[i], by_index[i + 1]
        net = a.nets["DO"]
        acx, acy, ax0, ax1, ay0, ay1 = _pad_edges(a, "DO", fp)
        bcx, bcy, bx0, bx1, by0, by1 = _pad_edges(b, "DI", fp)
        if a.row == b.row:
            # innerhalb einer Reihe: 45°-Diagonale + horizontales
            # Anschlussstueck an die DI-Padkante (DI liegt immer hoeher)
            dy = bcy - acy
            if a.col < b.col:                  # L->R: DO rechts, DI links
                sx = ax1
                assert sx + dy <= bx0 + 1e-9, (
                    f"{a.ref}->{b.ref}: kein Platz fuer 45°+Horizontal "
                    f"({sx + dy:.3f} > {bx0:.3f})")
                poly([(sx, acy), (sx + dy, bcy), (bx0, bcy)], net)
            else:                              # R->L: DO links, DI rechts
                sx = ax0
                assert sx - dy >= bx1 - 1e-9, (
                    f"{a.ref}->{b.ref}: kein Platz fuer 45°+Horizontal "
                    f"({sx - dy:.3f} < {bx1:.3f})")
                poly([(sx, acy), (sx - dy, bcy), (bx1, bcy)], net)
        else:
            # Reihenuebergang: direkte Vertikale in der X-Ueberlappung
            # der Pad-Kanten. Sie liegt ausserhalb der Schienen-Enden.
            lo, hi = max(ax0, bx0), min(ax1, bx1)
            assert hi - lo >= TRACE_DATA + 0.2, (
                f"Reihenuebergang {a.ref}->{b.ref}: Pad-X-Ueberlappung "
                f"zu klein ({hi - lo:.3f})")
            xv = (lo + hi) / 2.0
            if a.row > b.row:                  # a oben, b unten
                poly([(xv, ay0), (xv, by1)], net)
            else:                              # a unten, b oben
                poly([(xv, ay1), (xv, by0)], net)

    # --- DIN-Entry: B.Cu-Eckpad -> Via -> DI von L1 ---------------------
    first = by_index[0]
    fcx, fcy, fdx0, _fdx1, _fdy0, _fdy1 = _pad_edges(first, "DI", fp)
    din_via = (0.5, fcy)             # links der Rand-Schiene, im Eckpad
    poly([din_via, (fdx0, fcy)], first.nets["DI"])

    # --- DOUT-Entry: DO von L-N -> Via -> B.Cu-Eckpad -------------------
    last = by_index[len(leds) - 1]
    lcx, _lcy, _ldx0, _ldx1, ldy0, _ldy1 = _pad_edges(last, "DO", fp)
    vx, vy = 0.5, 0.5                # Via-Pad: Randabstand = 0.2
    # 45-Diagonale vom DO-Pad auf den Via zu, dann gerade zum Via-Mittelpunkt
    poly([(lcx, ldy0), (lcx - (ldy0 - vy), vy), (vx, vy)], last.nets["DO"])

    return {
        "segs": segs,
        "vias": [din_via, (vx, vy)],
        "trace_w": TRACE_DATA,
    }


if __name__ == "__main__":
    from footprint import footprint_from_data
    from matrix import generate_matrix
    fp = footprint_from_data("C41413180")
    leds = generate_matrix(8, 8, 3.0, fp)
    dc = compute_data_chain(leds, fp, 24.0, 24.0, 3.0)
    print("Segmente:", len(dc["segs"]), " Vias:", dc["vias"])
    # 56x2 (intra: 45°+Horizontal) + 7x1 (Vertikale) + 1 (DIN) + 2 (DOUT)
    assert len(dc["segs"]) == 56 * 2 + 7 + 3, "Segmentzahl unerwartet"
    # keine Daten-Segmente in den Rand-Schienen-Baendern (y<0.5 / y>23.45)
    for (x0, y0, x1, y1, n) in dc["segs"]:
        for y in (y0, y1):
            assert not (0.2 <= y <= 0.5 and min(x0, x1) >= 1.65), \
                f"Daten-Segment in unterer Rand-Schiene: {(x0,y0,x1,y1)}"
    # jedes Segment ist horizontal, vertikal oder exakt 45°
    for (x0, y0, x1, y1, n) in dc["segs"]:
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        assert dx < 1e-9 or dy < 1e-9 or abs(dx - dy) < 1e-9, \
            f"Nicht-45°-Segment: {(x0,y0,x1,y1)}"
    print("OK: Routing-Regeln eingehalten (45°+Horizontal / Vertikale)")
