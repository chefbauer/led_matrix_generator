"""
Layer-Writer fuer die Schema-Architektur (tools/layout_schema.py).

Verbraucht:
  matrix.generate_matrix   -> LEDs (rot 180/90, horizontale Serpentine)
  power_grid.compute_power_grid -> B.Cu-Rails, F.Cu-Schienen+Stubs,
                                   Stitch-Vias, Eckpads, Exposures
  data_chain.compute_data_chain -> F.Cu-Datenkette + DIN/DOUT-Entry-Vias

Erzeugt Gerber-Dateien:
  .GTL  F.Cu: LED-Pads (rotiert), Stromschienen+Stubs, Datenkette,
              Stitch-/Entry-Via-Pads
  .GBL  B.Cu: zwei mittige Rails, Eckpads DIN/DOUT, Via-Pads
  .GTS  Top-Mask: Oeffnungen LED-Pads
  .GBS  Bottom-Mask: Oeffnungen Eckpads + Rail-Enden (Exposures)
  .GKO  Board Outline
  .GTO  Silkscreen: DIN/DOUT/GND/VCC-Beschriftung
  .DRL  Excellon: alle Bohrungen 0.3 mm
"""
from __future__ import annotations

import math
import re
from typing import List, Tuple

import design_rules as DR
import power_grid as PG
from footprint import Footprint
from gerber_writer import GerberWriter, ApertureShape
from matrix import LedInstance

SM_EXP = 0.05   # Mask-Expansion pro Seite (JLCPCB-Standard)

Rect = Tuple[float, float, float, float]


def _rot(px: float, py: float, deg: float) -> Tuple[float, float]:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return px * c - py * s, px * s + py * c


def _flash_rect(g: GerberWriter, rect: Rect):
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    ap = g.add_aperture(ApertureShape.RECT, round(w, 6), round(h, 6))
    g.flash(ap, (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)


def _seg_rect(x0, y0, x1, y1, w) -> Rect:
    """Rechteck um ein achsenparalleles Segment (beide Richtungen)."""
    if abs(x0 - x1) < 1e-9:      # vertikal
        return (x0 - w / 2, min(y0, y1), x0 + w / 2, max(y0, y1))
    return (min(x0, x1), min(y0, y1) - w / 2,
            max(x0, x1), max(y0, y1) + w / 2)


def _led_pads(led, fp: Footprint):
    """(cx, cy, w, h) aller Pads einer LED, rotiert."""
    out = []
    for p in fp.pads:
        ox, oy = _rot(p.x, p.y, led.rotation)
        w, h = (p.height, p.width) if int(led.rotation) % 180 == 90 \
            else (p.width, p.height)
        out.append((led.x + ox, led.y + oy, w, h))
    return out


# ---------------------------------------------------------------------------
# F.Cu
# ---------------------------------------------------------------------------

def build_fcu(leds, fp: Footprint, pg: dict, dc: dict) -> str:
    g = GerberWriter("Top Copper (GTL)")

    # LED-Pads (rotiert)
    for led in leds:
        for cx, cy, w, h in _led_pads(led, fp):
            _flash_rect(g, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))

    # Stromschienen + Stubs
    for rail in pg["rails_top"]:
        y, w = rail["y"], rail["w"]
        _flash_rect(g, (rail["x0"], y - w / 2, rail["x1"], y + w / 2))
        for (sx, pe) in rail["stubs"]:
            y0, y1 = sorted((y, pe))
            _flash_rect(g, (sx - PG.STUB_W / 2, y0,
                            sx + PG.STUB_W / 2, y1))

    # Datenkette: Achsenparallel als Rechteck, Diagonalen als Zug mit
    # Kreisapertur (echte 45-Trasse, keine Treppenform)
    diag_ap = None
    for (x0, y0, x1, y1, _n) in dc["segs"]:
        if abs(x0 - x1) > 1e-9 and abs(y0 - y1) > 1e-9:
            if diag_ap is None:
                diag_ap = g.add_aperture(ApertureShape.CIRCLE,
                                        round(dc["trace_w"], 6))
            g.move(x0, y0)
            g.draw(diag_ap, x0, y0, x1, y1)
        else:
            _flash_rect(g, _seg_rect(x0, y0, x1, y1, dc["trace_w"]))

    # Via-Pads (Stitch + Entry)
    via_ap = g.add_aperture(ApertureShape.CIRCLE, DR.VIA_PAD_D)
    edge_ap = g.add_aperture(ApertureShape.CIRCLE, PG.EDGE_VIA_PAD)
    for (x, y, _net, pd) in pg["stitch_vias"]:
        g.flash(edge_ap if pd < DR.VIA_PAD_D else via_ap, x, y)
    for (x, y) in dc["vias"]:
        g.flash(via_ap, x, y)
    return g.render()


# ---------------------------------------------------------------------------
# B.Cu
# ---------------------------------------------------------------------------

def build_bcu(leds, fp: Footprint, pg: dict, dc: dict) -> str:
    g = GerberWriter("Bottom Copper (GBL)")

    # Zwei mittige Rails (Eckpads liegen aussenhalb, keine Ausschnitte noetig)
    for _net, rect in pg["rails_bottom"]:
        _flash_rect(g, rect)

    # Eckpads DIN/DOUT
    for cp in pg["corner_pads"].values():
        _flash_rect(g, cp)

    # Via-Pads: Stitch (gleiche Rails, kein Clearance noetig) + Entry
    via_ap = g.add_aperture(ApertureShape.CIRCLE, DR.VIA_PAD_D)
    edge_ap = g.add_aperture(ApertureShape.CIRCLE, PG.EDGE_VIA_PAD)
    for (x, y, _net, pd) in pg["stitch_vias"]:
        g.flash(edge_ap if pd < DR.VIA_PAD_D else via_ap, x, y)
    for (x, y) in dc["vias"]:
        g.flash(via_ap, x, y)
    return g.render()


# ---------------------------------------------------------------------------
# Masken
# ---------------------------------------------------------------------------

def _mask_via_openings(g: GerberWriter, pg: dict, dc: dict):
    """Masken-Oeffnungen fuer ALLE Bohrungen (Stitch-, Rand-, Entry-Vias),
    damit keine Via tented ist (Locher in 2D- und 3D-Ansicht sichtbar)."""
    seen = set()
    for (x, y, _net, pd) in pg["stitch_vias"]:
        seen.add((round(x, 3), round(y, 3), pd))
    for (x, y) in dc["vias"]:
        seen.add((round(x, 3), round(y, 3), DR.VIA_PAD_D))
    for (x, y, pd) in seen:
        ap = g.add_aperture(ApertureShape.CIRCLE, pd + 2 * SM_EXP)
        g.flash(ap, x, y)


def build_mask_top(leds, fp: Footprint, pg: dict, dc: dict) -> str:
    g = GerberWriter("Top Solder Mask (GTS)")
    for led in leds:
        for cx, cy, w, h in _led_pads(led, fp):
            _flash_rect(g, (cx - w / 2 - SM_EXP, cy - h / 2 - SM_EXP,
                            cx + w / 2 + SM_EXP, cy + h / 2 + SM_EXP))
    _mask_via_openings(g, pg, dc)
    return g.render()


def build_mask_bottom(pg: dict, dc: dict) -> str:
    g = GerberWriter("Bottom Solder Mask (GBS)")
    for rect, _net in pg["exposures"]:
        _flash_rect(g, (rect[0] - SM_EXP, rect[1] - SM_EXP,
                        rect[2] + SM_EXP, rect[3] + SM_EXP))
    for cp in pg["corner_pads"].values():
        _flash_rect(g, (cp[0] - SM_EXP, cp[1] - SM_EXP,
                        cp[2] + SM_EXP, cp[3] + SM_EXP))
    _mask_via_openings(g, pg, dc)
    return g.render()


# ---------------------------------------------------------------------------
# Outline + Drill
# ---------------------------------------------------------------------------

def build_outline(W: float, H: float) -> str:
    g = GerberWriter("Board Outline (GKO)")
    ap = g.add_aperture(ApertureShape.CIRCLE, 0.05)
    g.rect_outline(ap, 0.0, 0.0, W, H)
    return g.render()


def build_drill(dc: dict, pg: dict) -> str:
    lines = ["M48", "METRIC,TZ", f"T1C{DR.VIA_DRILL:.3f}", "%", "T1", "G05"]
    holes = [(x, y) for (x, y, _n, _pd) in pg["stitch_vias"]]
    holes += [(x, y) for (x, y) in dc["vias"]]
    for vx, vy in holes:
        lines.append(f"X{round(vx*1000):+07d}Y{round(vy*1000):+07d}")
    lines.append("M30")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Silkscreen (Top)
# ---------------------------------------------------------------------------

SILK_W = 0.15
SILK_H = 1.0


def _text(g: GerberWriter, ap: int, s: str, x: float, y: float,
          mirror: bool = False, h: float | None = None,
          vertical: bool = False):
    """Text (links-buendig bei x, mittlere Y). mirror=True fuer GBO:
    Zeichen in umgekehrter Reihenfolge, gespiegelte Glyphen -> von unten
    gelesen korrekt. h = Glyphenhoehe (Default SILK_H).
    vertical=True: Glyphen untereinander (Textblock 90°-gestapelt,
    Glyphen selbst bleiben aufrecht), y = Mitte des Blocks."""
    from silkscreen import _draw_glyph
    hh = SILK_H if h is None else h
    n = len(s)
    for i, ch in enumerate(s):
        pos = (n - 1 - i) if (mirror and not vertical) else i
        if vertical:
            # Vorschub = Glyphenhoehe + 10% Abstand (nicht 0.85* wie
            # horizontal, das wuerde die Buchstaben ueberlappen lassen)
            _draw_glyph(g, ap, ch, x, y + (n - 1) * hh * 1.1 / 2
                        - pos * hh * 1.1, hh, mirror=mirror)
        else:
            _draw_glyph(g, ap, ch, x + pos * hh * 0.85, y, hh,
                        mirror=mirror)


def _text_ink_dx(s: str, mirror: bool, h: float) -> float:
    """Ink-Mitte eines _text-Blocks relativ zu dessen x-Start (gemessen)."""
    return sum(_text_ink_edges(s, mirror, h)) / 2


def _text_ink_edges(s: str, mirror: bool, h: float) -> tuple:
    """(links, rechts) der Tinte relativ zum x-Start (gemessen)."""
    g = GerberWriter("scratch")
    ap = g.add_aperture(ApertureShape.CIRCLE, SILK_W)
    _text(g, ap, s, 0.0, 0.0, mirror=mirror, h=h)
    xs = [int(m.group(1)) / 1e6 for m in
          re.finditer(r"X(-?\d+)Y(-?\d+)D\d+", g.render())]
    return (min(xs), max(xs))


def build_silkscreen_bottom(pg: dict, W: float, H: float) -> str:
    """Beschriftung NUR auf der Rueckseite (GBO): DIN/DOUT neben den
    Eckpads, GND/VCC an den Rail-Enden. Gespiegelt gezeichnet, damit von
    der Bestueckungsseite Rueckseite lesbar."""
    g = GerberWriter("Bottom Silkscreen (GBO)")
    ap = g.add_aperture(ApertureShape.CIRCLE, SILK_W)
    cp = pg["corner_pads"]

    # DIN/DOUT: 90° als Textstapel (Glyphen aufrecht) ausserhalb der
    # Eckpads (v9-Position), aber mit 1.0 mm Tintenabstand zum Boardrand.
    # Glyph-Halbbreite ~0.3 mm -> Achse bei x = 1.3.
    din_x = 1.3
    din_y = cp["DIN"][1] - 2.2
    dout_x = 1.3
    dout_y = cp["DOUT"][3] + 2.2
    for s, xc, yc in (("DIN", din_x, din_y), ("DOUT", dout_x, dout_y)):
        # Achse so legen, dass Tinten-Linkskante bei 1.0 mm liegt
        # (Einzelglyph-Ink relativ zur Glyphenmitte bestimmen)
        lo = min(_text_ink_edges(ch, True, SILK_H)[0] for ch in set(s))
        _text(g, ap, s, max(1.0 - lo, xc), yc, mirror=True, vertical=True)

    # GND/VCC: 2x mittig AUF den Stromschienen (B.Cu-Rails), auf den
    # aeusseren Stitch-Via-Reihen (y = 6.0 mm ab jeweils anderem Rand).
    # Ueberdeckung mit Vias ist ausdruecklich erlaubt.
    rails = {net: (r[0], r[2]) for net, r in
             ((n, rect) for n, rect in pg["rails_bottom"])}
    for net in ("GND", "VCC"):
        cx = (rails[net][0] + rails[net][1]) / 2
        dx = _text_ink_dx(net, True, SILK_H)
        for y in (6.0, H - 6.0):
            _text(g, ap, net, cx - dx, y, mirror=True)
    return g.render()


# ---------------------------------------------------------------------------
# Silkscreen Top: kleine Netz-Kennzeichnungen auf den F.Cu-Reihenschienen
# ---------------------------------------------------------------------------

SILK_H_F = 0.6       # Mini-Orientierungschrift (+V / G) auf Schienen
                     # (teilverdeckt Pads/Rail-Rand ist ausdruecklich ok)


def build_silkscreen_top(pg: dict) -> str:
    """Kleine Netzlabels (+V, G) mittig auf jeder F.Cu-Stromschiene.
    Skaliert von der Schienenmitte aus (Ink-Mitte bleibt auf Rail-Mitte)."""
    g = GerberWriter("Top Silkscreen (GTO)")
    ap = g.add_aperture(ApertureShape.CIRCLE, SILK_W)
    for rail in pg["rails_top"]:
        s = "+V" if rail["net"] == "VCC" else "G"
        h = SILK_H_F if rail["w"] >= 0.4 else SILK_H_F * 0.83
        cx = (rail["x0"] + rail["x1"]) / 2
        _text(g, ap, s, cx - _text_ink_dx(s, False, h), rail["y"], h=h)
    return g.render()
