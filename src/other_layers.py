"""
Gerber-Generator fuer die verbleibenden Lagen:
  - Top Solder Mask (GTS): Oeffnungen ueber allen Top-Pads und Via-Pads
  - Bottom Solder Mask (GBS): Oeffnungen ueber Via-Pads auf Bottom
  - Board Outline (GKO): Rechteck
  - Excellon Drill File (DRL): alle Via-Bohrungen

Solder Mask: Oeffnungen sind 0.05 mm groesser als der Pad auf jeder Seite.
"""

from __future__ import annotations
from typing import List
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, pad_pos, via_pos, Footprint
from matrix import LedInstance, board_size
import design_rules as DR


# Solder-Mask-Expansion in mm (pro Seite)
SM_EXP = DR.CLEARANCE   # 0.05 wäre Standard; wir nehmen CLEARANCE = 0.15 als Expansion

# Via-Parameter
VIA_DRILL = DR.VIA_DRILL
VIA_PAD_D = DR.VIA_PAD_D


def _via_list(leds: List[LedInstance], pitch: float = 5.0):
    """Alle Via-Positionen als Liste von (x, y) Tupeln."""
    result = []
    for led in leds:
        for sig in ("VDD", "GND"):
            result.append(via_pos(led.x, led.y, led.rotation, sig, pitch))
    return result


def build_top_soldermask(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
) -> str:
    """Top Solder Mask: Oeffnungen ueber allen LED-Pads und VDD/GND-Via-Pads."""
    g = GerberWriter("Top Solder Mask (GTS)")

    pw, ph = fp.pads[0].width + 2 * SM_EXP, fp.pads[0].height + 2 * SM_EXP
    pad_ap_0  = g.add_aperture(ApertureShape.RECT, pw, ph)
    pad_ap_90 = g.add_aperture(ApertureShape.RECT, ph, pw)
    via_ap = g.add_aperture(ApertureShape.CIRCLE, VIA_PAD_D + 2 * SM_EXP)

    for led in leds:
        ap = pad_ap_90 if led.rotation % 180 != 0 else pad_ap_0
        for p in fp.pads:
            px, py = pad_pos(led.x, led.y, led.rotation, p)
            g.flash(ap, px, py)

    for vx, vy in _via_list(leds, pitch):
        g.flash(via_ap, vx, vy)

    return g.render()


def build_bottom_soldermask(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
) -> str:
    """Bottom Solder Mask: Oeffnungen ueber Via-Pads auf der Unterseite."""
    g = GerberWriter("Bottom Solder Mask (GBS)")
    via_ap = g.add_aperture(ApertureShape.CIRCLE, VIA_PAD_D + 2 * SM_EXP)

    for vx, vy in _via_list(leds, pitch):
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
    pitch: float = 5.0,
) -> str:
    """
    Excellon Drill File fuer alle Via-Bohrungen.

    Format: Minimales Excellon mit METRIC-Header.
    Alle Bohrungen haben denselben Durchmesser (VIA_DRILL).
    """
    lines = [
        "M48",
        "METRIC,TZ",
        f"T1C{VIA_DRILL:.3f}",
        "%",
        "T1",
        "G05",
    ]

    for vx, vy in _via_list(leds, pitch):
        xi = round(vx * 1000)
        yi = round(vy * 1000)
        lines.append(f"X{xi:+07d}Y{yi:+07d}")

    lines.append("M30")
    return "\n".join(lines) + "\n"
