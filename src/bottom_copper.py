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
import design_rules as DR


TRACE_POWER = 0.40   # Breite der Stromschiene in mm


def build_bottom_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
) -> str:
    g = GerberWriter("Bottom Copper (GBL) - Power Planes")

    w_bus = DR.bus_width(pitch)
    trace_vdd = g.add_aperture(ApertureShape.CIRCLE, w_bus)
    trace_gnd = g.add_aperture(ApertureShape.CIRCLE, w_bus)
    via_ap    = g.add_aperture(ApertureShape.CIRCLE, DR.VIA_PAD_D)

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
                vx, vy = fp_via_pos(led.x, led.y, led.rotation, sig, pitch)
                xs.append(vx)
                y_val = vy  # alle LEDs einer Zeile haben denselben via_y

            x_min = min(xs) - w_bus / 2
            x_max = max(xs) + w_bus / 2
            ap = trace_vdd if sig == "VDD" else trace_gnd
            g.draw(ap, x_min, y_val, x_max, y_val)

            for vx in xs:
                g.flash(via_ap, vx, y_val)

    return g.render()
