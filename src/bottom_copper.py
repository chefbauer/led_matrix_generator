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
    # Bus-Y = nominale Schienenmitte (unabhaengig von der Via-Position)
    # Via-Y kann durch Sicherheitsabstand weiter verschoben sein
    # -------------------------------------------------------------------
    w = DR.bus_width(pitch)

    for row_idx in sorted(rows.keys()):
        row_leds = rows[row_idx]
        first = row_leds[0]

        for sig in ("VDD", "GND"):
            # Via-Positionen (ggf. sicherheitsbedingt verschoben)
            via_xs = []
            via_ys = []
            for led in row_leds:
                vx, vy = fp_via_pos(led.x, led.y, led.rotation, sig, pitch)
                via_xs.append(vx)
                via_ys.append(vy)

            # Vorzeichen aus Via-Richtung (gleich fuer alle LEDs einer Reihe)
            sign = +1 if via_ys[0] > first.y else -1

            # Bus bei nominalem Y (CLEARANCE + w/2 von LED-Mitte)
            bus_y_val = first.y + sign * (DR.CLEARANCE + w / 2)

            x_min = min(via_xs) - w / 2
            x_max = max(via_xs) + w / 2
            ap = trace_vdd if sig == "VDD" else trace_gnd
            g.draw(ap, x_min, bus_y_val, x_max, bus_y_val)

            for vx, vy in zip(via_xs, via_ys):
                g.flash(via_ap, vx, vy)

    return g.render()
