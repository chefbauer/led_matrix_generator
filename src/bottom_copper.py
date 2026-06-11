"""
Gerber-Generator fuer die Bottom-Copper-Lage (GBL).

Inhalt:
  - Horizontale VDD-Stromschiene pro Zeile
  - Horizontale GND-Stromschiene pro Zeile
  - Via-Pads auf Bottom fuer alle VDD- und GND-Vias

Die Via-Positionen werden ueber via_pos() aus footprint.py berechnet
und respektieren die LED-Rotation.
"""

from __future__ import annotations
from typing import List, Dict
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, via_pos as fp_via_pos, Footprint
from matrix import LedInstance


TRACE_POWER = 0.40   # Breite der Stromschiene in mm


def build_bottom_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    g = GerberWriter("Bottom Copper (GBL) - Power Planes")

    trace_ap = g.add_aperture(ApertureShape.CIRCLE, TRACE_POWER)
    via_ap   = g.add_aperture(ApertureShape.CIRCLE, 0.50)

    # Zeilen-Gruppen aufbauen
    rows: Dict[int, List[LedInstance]] = {}
    for led in leds:
        rows.setdefault(led.row, []).append(led)

    # -------------------------------------------------------------------
    # Stromschienen und Via-Pads pro Zeile
    # -------------------------------------------------------------------
    for row_idx in sorted(rows.keys()):
        row_leds = rows[row_idx]

        for sig in ("VDD", "GND"):
            xs = []
            y_val = None
            for led in row_leds:
                vx, vy = fp_via_pos(led.x, led.y, led.rotation, sig)
                xs.append(vx)
                y_val = vy  # alle LEDs einer Zeile haben denselben via_y

            x_min = min(xs) - TRACE_POWER / 2
            x_max = max(xs) + TRACE_POWER / 2
            g.draw(trace_ap, x_min, y_val, x_max, y_val)

            for vx in xs:
                g.flash(via_ap, vx, y_val)

    return g.render()
