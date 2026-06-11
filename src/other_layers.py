"""
Gerber-Generator fuer die verbleibenden Lagen:
  - Top Solder Mask (GTS): Oeffnungen ueber allen Top-Pads und Via-Pads
  - Bottom Solder Mask (GBS): Oeffnungen ueber Via-Pads auf Bottom
  - Board Outline (GKO): Rechteck
  - Excellon Drill File (DRL): alle Via-Bohrungen

Solder Mask: Oeffnungen sind per Konvention 0.1 mm groesser als der Pad auf
jeder Seite (d.h. +0.1mm auf Breite und Hoehe = LPI-Prozess Standard).
"""

from __future__ import annotations
from typing import List
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, Footprint
from matrix import LedInstance, board_size


# Solder-Mask-Expansion in mm (pro Seite)
SM_EXP = 0.05

# Via-Parameter
VIA_DRILL    = 0.30   # Bohrungsdurchmesser mm
VIA_PAD_D    = 0.50   # Pad-Durchmesser mm (gleich wie in top/bottom_copper.py)
VIA_OFFSET_X = -0.7   # Gleicher Versatz wie in top_copper.py


def _via_list(leds: List[LedInstance], fp: Footprint):
    """Alle Via-Positionen als Liste von (x, y) Tupeln."""
    vias = []
    for led in leds:
        for sig in ("VDD", "GND"):
            pad = get_pad(fp, sig)
            via_x = led.x + pad.x + VIA_OFFSET_X
            via_y = led.y + pad.y
            vias.append((via_x, via_y))
    return vias


def build_top_soldermask(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    """Top Solder Mask: Oeffnungen ueber allen LED-Pads und VDD/GND-Via-Pads."""
    g = GerberWriter("Top Solder Mask (GTS)")

    # Pad-Oeffnungen (groesser als Pad)
    pad_ap = g.add_aperture(
        ApertureShape.RECT,
        fp.pads[0].width  + 2 * SM_EXP,
        fp.pads[0].height + 2 * SM_EXP,
    )
    via_ap = g.add_aperture(ApertureShape.CIRCLE, VIA_PAD_D + 2 * SM_EXP)

    for led in leds:
        for pad in fp.pads:
            g.flash(pad_ap, led.x + pad.x, led.y + pad.y)

    for vx, vy in _via_list(leds, fp):
        g.flash(via_ap, vx, vy)

    return g.render()


def build_bottom_soldermask(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    """Bottom Solder Mask: Oeffnungen ueber Via-Pads auf der Unterseite."""
    g = GerberWriter("Bottom Solder Mask (GBS)")
    via_ap = g.add_aperture(ApertureShape.CIRCLE, VIA_PAD_D + 2 * SM_EXP)

    for vx, vy in _via_list(leds, fp):
        g.flash(via_ap, vx, vy)

    return g.render()


def build_board_outline(
    cols: int,
    rows: int,
    pitch: float,
    margin: float = 2.0,
) -> str:
    """Board Outline (GKO): Rechteck passend zur Matrix."""
    g = GerberWriter("Board Outline (GKO)")
    outline_ap = g.add_aperture(ApertureShape.CIRCLE, 0.05)

    w, h = board_size(cols, rows, pitch, margin)
    g.rect_outline(outline_ap, 0.0, 0.0, w, h)
    return g.render()


def build_drill(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    """
    Excellon Drill File fuer alle Via-Bohrungen.

    Format: Minimales Excellon mit METRIC-Header.
    Alle Bohrungen haben denselben Durchmesser (VIA_DRILL).
    """
    lines = [
        "M48",                          # Excellon Header
        "METRIC,TZ",                    # Metrisch, trailing zeros
        f"T1C{VIA_DRILL:.3f}",          # Tool 1: Via-Bohrung
        "%",                            # Header Ende
        "T1",                           # Tool 1 waehlen
        "G05",                          # Drill-Modus
    ]

    for vx, vy in _via_list(leds, fp):
        # Excellon-Koordinaten: mm * 1000 als Integer (3 Nachkommastellen)
        xi = round(vx * 1000)
        yi = round(vy * 1000)
        lines.append(f"X{xi:+07d}Y{yi:+07d}")

    lines.append("M30")  # Dateiende
    return "\n".join(lines) + "\n"
