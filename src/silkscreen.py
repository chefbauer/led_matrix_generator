"""
Gerber Top Silkscreen (GTO).

Inhalt:
  - Richtungspfeile (> oder <) zwischen benachbarten LEDs einer Reihe
  - Reihen-Beschriftung am Eingang jeder Reihe:
      D = Data In   (am DI-Pad)
      C = Clock In  (am CI-Pad)
      + = VDD       (am Boardrand, Hoehe der VDD-Via)
      - = GND       (am Boardrand, Hoehe der GND-Via)
  - Busbar-Beschriftung: DAT / CLK / +5V / GND am Connector-Bereich

Positionierung:
  Gerade Reihen (->): Beschriftung LINKS  (D, C nahe DI/CI-Pad; +/- am linken Rand)
  Ungerade Reihen (<-): Beschriftung RECHTS (gespiegelt)
"""

from __future__ import annotations
from typing import List, Dict
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, has_pad, pad_pos, via_pos, Footprint
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
    'A': [
        [(0.1, 0.05), (0.5, 0.95), (0.9, 0.05)],   # Dreieck
        [(0.28, 0.42), (0.72, 0.42)],               # Querbalken
    ],
    'T': [
        [(0.1, 0.9), (0.9, 0.9)],                   # oben
        [(0.5, 0.9), (0.5, 0.05)],                  # Senkrechte
    ],
    'K': [
        [(0.2, 0.05), (0.2, 0.95)],                 # Senkrechte
        [(0.2, 0.5), (0.85, 0.95)],                 # obere Diagonale
        [(0.2, 0.5), (0.85, 0.05)],                 # untere Diagonale
    ],
    'L': [
        [(0.2, 0.95), (0.2, 0.05)],
        [(0.2, 0.05), (0.85, 0.05)],
    ],
    'G': [
        [(0.88, 0.8), (0.62, 0.95), (0.28, 0.88),
         (0.12, 0.68), (0.12, 0.32), (0.28, 0.12),
         (0.62, 0.05), (0.88, 0.2), (0.88, 0.5), (0.5, 0.5)],
    ],
    'N': [
        [(0.15, 0.05), (0.15, 0.95)],
        [(0.15, 0.95), (0.85, 0.05)],
        [(0.85, 0.05), (0.85, 0.95)],
    ],
    'V': [
        [(0.1, 0.95), (0.5, 0.05), (0.9, 0.95)],
    ],
    '5': [
        [(0.85, 0.95), (0.15, 0.95), (0.15, 0.55),
         (0.7, 0.55), (0.85, 0.4), (0.85, 0.15),
         (0.6, 0.05), (0.2, 0.05)],
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
    busbar: int = 0,
    x_offset: float = 0.0,
) -> str:
    g = GerberWriter("Top Silkscreen (GTO)")
    ap = g.add_aperture(ApertureShape.CIRCLE, SILK_W)

    by_index = {led.index: led for led in leds}
    rows: Dict[int, List[LedInstance]] = {}
    for led in leds:
        rows.setdefault(led.row, []).append(led)

    # -------------------------------------------------------------------
    # 1. Richtungspfeile zwischen benachbarten LEDs (gleiche Reihe)
    # 270 Grad CCW = gerade Reihe, geht nach rechts -> Pfeil >
    # 90  Grad CCW = ungerade Reihe, geht nach links  -> Pfeil <
    # -------------------------------------------------------------------
    for led in leds:
        nxt = by_index.get(led.index + 1)
        if nxt is None or led.row != nxt.row:
            continue
        mid_x = (led.x + nxt.x) / 2
        mid_y = (led.y + nxt.y) / 2
        arrow = '>' if led.rotation == 270.0 else '<'
        _draw_glyph(g, ap, arrow, mid_x, mid_y, size=1.1)

    # -------------------------------------------------------------------
    # 2. Reihen-Beschriftung am Eingang: D, C, +, -
    # -------------------------------------------------------------------
    for row_idx in sorted(rows.keys()):
        row_leds  = rows[row_idx]
        first     = min(row_leds, key=lambda l: l.index)

        di_abs  = pad_pos(first.x, first.y, first.rotation, get_pad(fp, "DI"))
        vdd_abs = via_pos(first.x, first.y, first.rotation, "VDD", pitch, fp=fp)
        gnd_abs = via_pos(first.x, first.y, first.rotation, "GND", pitch, fp=fp)

        going_right = (first.rotation == 270.0)

        if going_right:
            lx = first.x - fp.body_width / 2 - 0.8
        else:
            lx = first.x + fp.body_width / 2 + 0.8

        _draw_glyph(g, ap, 'D', lx, di_abs[1],  size=0.9)
        if has_pad(fp, "CI"):
            ci_abs = pad_pos(first.x, first.y, first.rotation, get_pad(fp, "CI"))
            _draw_glyph(g, ap, 'C', lx, ci_abs[1],  size=0.9)
        _draw_glyph(g, ap, '+', lx, vdd_abs[1], size=0.8)
        _draw_glyph(g, ap, '-', lx, gnd_abs[1], size=0.8)

    # -------------------------------------------------------------------
    # 3. Busbar Connector-Beschriftung: DAT / CLK / +5V / GND
    # -------------------------------------------------------------------
    if busbar > 0 and x_offset > 0:
        from bottom_copper import PAD_DIA_SIG, PAD_DIA_PWR

        first_led  = min(leds, key=lambda l: l.index)
        di_x, di_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                              get_pad(fp, "DI"))

        sig_x2    = DR.CLEARANCE + PAD_DIA_SIG / 2 + PAD_DIA_SIG
        y_dat     = di_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
        y_gnd_pad = DR.CLEARANCE + PAD_DIA_PWR / 2
        y_5v_pad  = y_gnd_pad + PAD_DIA_PWR + DR.CLEARANCE
        lbl_x     = sig_x2 + 0.5
        lbl_s     = 1.0

        # DAT/CLK Connector-Labels
        for i, ch in enumerate("DAT"):
            _draw_glyph(g, ap, ch, lbl_x + i * lbl_s * 0.9, y_dat, size=lbl_s)
        if has_pad(fp, "CI"):
            ci_x, ci_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                                  get_pad(fp, "CI"))
            y_clk = ci_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
            for i, ch in enumerate("CLK"):
                _draw_glyph(g, ap, ch, lbl_x + i * lbl_s * 0.9, y_clk, size=lbl_s)

        # "+5V" und "GND" bei den Leistungspads
        for i, ch in enumerate("+5V"):
            _draw_glyph(g, ap, ch, lbl_x + i * lbl_s * 0.9, y_5v_pad, size=lbl_s)
        for i, ch in enumerate("GND"):
            _draw_glyph(g, ap, ch, lbl_x + i * lbl_s * 0.9, y_gnd_pad, size=lbl_s)

    return g.render()
