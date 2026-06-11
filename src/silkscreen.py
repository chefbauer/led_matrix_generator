"""
Gerber Top Silkscreen (GTO).

Inhalt:
  - Richtungspfeile (> oder <) zwischen benachbarten LEDs einer Reihe
  - Reihen-Beschriftung am Eingang jeder Reihe:
      D = Data In   (am DI-Pad)
      C = Clock In  (am CI-Pad)
      + = VDD       (am Boardrand, Hoehe der VDD-Via)
      - = GND       (am Boardrand, Hoehe der GND-Via)

Positionierung:
  Gerade Reihen (->): Beschriftung LINKS  (D, C nahe DI/CI-Pad; +/- am linken Rand)
  Ungerade Reihen (<-): Beschriftung RECHTS (gespiegelt)
"""

from __future__ import annotations
from typing import List, Dict
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, pad_pos, via_pos, Footprint
from matrix import LedInstance
import design_rules as DR


SILK_W = 0.12   # mm: Linienbreite Silkscreen-Striche


# ---------------------------------------------------------------------------
# Vektor-Zeichensatz (normierte Koordinaten 0..1 x 0..1, Ursprung unten-links)
# Jedes Zeichen besteht aus einer Liste von Polylinien.
# ---------------------------------------------------------------------------
GLYPHS: dict[str, list[list[tuple[float, float]]]] = {
    '+': [
        [(0.5, 0.15), (0.5, 0.85)],        # vertikal
        [(0.15, 0.5), (0.85, 0.5)],        # horizontal
    ],
    '-': [
        [(0.2, 0.5), (0.8, 0.5)],
    ],
    'D': [
        [(0.2, 0.1), (0.2, 0.9)],          # linke Senkrechte
        [(0.2, 0.9), (0.55, 0.95), (0.85, 0.72),   # Rundbogen oben
         (0.85, 0.28), (0.55, 0.05), (0.2, 0.1)],  # Rundbogen unten
    ],
    'C': [
        [(0.88, 0.8), (0.62, 0.95), (0.28, 0.88),
         (0.12, 0.68), (0.12, 0.32), (0.28, 0.12),
         (0.62, 0.05), (0.88, 0.2)],
    ],
    '>': [
        [(0.15, 0.15), (0.85, 0.5), (0.15, 0.85)],
    ],
    '<': [
        [(0.85, 0.15), (0.15, 0.5), (0.85, 0.85)],
    ],
}


def _draw_glyph(
    g: GerberWriter,
    ap: int,
    char: str,
    cx: float,
    cy: float,
    size: float = 1.0,
) -> None:
    """Zeichen zentriert um (cx, cy) mit gegebener Hoehe zeichnen."""
    char_h = size
    char_w = size * 0.85
    x0 = cx - char_w / 2
    y0 = cy - char_h / 2
    for stroke in GLYPHS.get(char, []):
        for i in range(len(stroke) - 1):
            sx = x0 + stroke[i][0]   * char_w
            sy = y0 + stroke[i][1]   * char_h
            ex = x0 + stroke[i+1][0] * char_w
            ey = y0 + stroke[i+1][1] * char_h
            g.draw(ap, sx, sy, ex, ey)


def build_top_silkscreen(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
    board_width: float = 25.0,
) -> str:
    g = GerberWriter("Top Silkscreen (GTO)")
    ap = g.add_aperture(ApertureShape.CIRCLE, SILK_W)

    by_index = {led.index: led for led in leds}
    rows: Dict[int, List[LedInstance]] = {}
    for led in leds:
        rows.setdefault(led.row, []).append(led)

    # -------------------------------------------------------------------
    # 1. Richtungspfeile zwischen benachbarten LEDs (gleiche Reihe)
    # -------------------------------------------------------------------
    for led in leds:
        nxt = by_index.get(led.index + 1)
        if nxt is None or led.row != nxt.row:
            continue
        mid_x = (led.x + nxt.x) / 2
        mid_y = (led.y + nxt.y) / 2
        arrow = '>' if led.rotation == 90.0 else '<'
        _draw_glyph(g, ap, arrow, mid_x, mid_y, size=1.1)

    # -------------------------------------------------------------------
    # 2. Reihen-Beschriftung am Eingang: D, C, +, -
    # -------------------------------------------------------------------
    for row_idx in sorted(rows.keys()):
        row_leds  = rows[row_idx]
        first     = min(row_leds, key=lambda l: l.index)

        di_abs  = pad_pos(first.x, first.y, first.rotation, get_pad(fp, "DI"))
        ci_abs  = pad_pos(first.x, first.y, first.rotation, get_pad(fp, "CI"))
        vdd_abs = via_pos(first.x, first.y, first.rotation, "VDD", pitch)
        gnd_abs = via_pos(first.x, first.y, first.rotation, "GND", pitch)

        going_right = (first.rotation == 90.0)

        if going_right:
            # Gerade Reihe (->): D und C links der Pads, +/- ganz am linken Rand
            label_x_dc = di_abs[0] - 0.55   # kurz links der DI/CI-Pads
            label_x_pm = 0.45               # am linken Boardrand
        else:
            # Ungerade Reihe (<-): alles rechts
            label_x_dc = di_abs[0] + 0.55
            label_x_pm = board_width - 0.45

        _draw_glyph(g, ap, 'D', label_x_dc, di_abs[1],  size=0.9)
        _draw_glyph(g, ap, 'C', label_x_dc, ci_abs[1],  size=0.9)
        _draw_glyph(g, ap, '+', label_x_pm, vdd_abs[1], size=0.8)
        _draw_glyph(g, ap, '-', label_x_pm, gnd_abs[1], size=0.8)

    return g.render()
