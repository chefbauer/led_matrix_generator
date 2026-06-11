"""
Gerber-Generator fuer die Bottom-Copper-Lage (GBL).

Inhalt:
  - Horizontale VDD-Stromschiene pro Zeile (von erster bis letzter LED der Zeile)
  - Horizontale GND-Stromschiene pro Zeile
  - Via-Pads auf Bottom fuer alle VDD- und GND-Vias

Die Vias verbinden diese Bottom-Schienen mit den VDD/GND-Pads auf der Oberseite.
Die Via-Positionen muessen mit denen in top_copper.py uebereinstimmen.
"""

from __future__ import annotations
from typing import List, Dict
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, Footprint
from matrix import LedInstance


TRACE_POWER = 0.40   # Breite der Stromschiene in mm
VIA_OFFSET_X = -0.7  # Gleicher Versatz wie in top_copper.py


def _via_positions(leds: List[LedInstance], fp: Footprint):
    """
    Gibt alle Via-Positionen fuer VDD und GND zurueck.
    Struktur: {"VDD": [(x, y), ...], "GND": [(x, y), ...]}
    """
    positions: Dict[str, list] = {"VDD": [], "GND": []}
    for led in leds:
        for sig in ("VDD", "GND"):
            pad = get_pad(fp, sig)
            pad_x = led.x + pad.x
            pad_y = led.y + pad.y
            via_x = pad_x + VIA_OFFSET_X
            via_y = pad_y
            positions[sig].append((via_x, via_y))
    return positions


def build_bottom_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    """
    Erzeugt die Bottom-Copper-Lage als Gerber-String.

    Ablauf:
        1. Pro Zeile: VDD-Schiene von links-aussen bis rechts-aussen
        2. Pro Zeile: GND-Schiene
        3. Via-Pads auf Bottom fuer alle Power-Vias
    """
    g = GerberWriter("Bottom Copper (GBL) - Power Planes")

    trace_ap = g.add_aperture(ApertureShape.CIRCLE, TRACE_POWER)
    via_ap   = g.add_aperture(ApertureShape.CIRCLE, 0.50)

    # Zeilen-Gruppen aufbauen: row -> [LedInstance, ...]
    rows: Dict[int, List[LedInstance]] = {}
    for led in leds:
        rows.setdefault(led.row, []).append(led)

    # ---------------------------------------------------------------
    # 1+2. Stromschienen pro Zeile
    #
    #   Via-Positionen auf Bottom:
    #     VDD-Via: links vom VDD-Pad der LED (VIA_OFFSET_X)
    #     GND-Via: links vom GND-Pad der LED
    #
    #   Schiene verlaeuft von der am weitesten links liegenden Via-X
    #   bis zur am weitesten rechts liegenden Via-X dieser Zeile.
    # ---------------------------------------------------------------
    for row_idx in sorted(rows.keys()):
        row_leds = rows[row_idx]

        vdd_xs = []
        gnd_xs = []
        vdd_y  = None
        gnd_y  = None

        for led in row_leds:
            vdd_pad = get_pad(fp, "VDD")
            gnd_pad = get_pad(fp, "GND")

            vdd_via_x = led.x + vdd_pad.x + VIA_OFFSET_X
            gnd_via_x = led.x + gnd_pad.x + VIA_OFFSET_X
            vdd_via_y = led.y + vdd_pad.y
            gnd_via_y = led.y + gnd_pad.y

            vdd_xs.append(vdd_via_x)
            gnd_xs.append(gnd_via_x)

            # Y ist in einer Zeile konstant
            vdd_y = vdd_via_y
            gnd_y = gnd_via_y

        # Schiene von linksaussen bis rechtsaussen
        x_min_vdd = min(vdd_xs) - TRACE_POWER / 2
        x_max_vdd = max(vdd_xs) + TRACE_POWER / 2
        x_min_gnd = min(gnd_xs) - TRACE_POWER / 2
        x_max_gnd = max(gnd_xs) + TRACE_POWER / 2

        g.draw(trace_ap, x_min_vdd, vdd_y, x_max_vdd, vdd_y)
        g.draw(trace_ap, x_min_gnd, gnd_y, x_max_gnd, gnd_y)

    # ---------------------------------------------------------------
    # 3. Via-Pads auf Bottom
    # ---------------------------------------------------------------
    via_pos = _via_positions(leds, fp)
    for sig in ("VDD", "GND"):
        for vx, vy in via_pos[sig]:
            g.flash(via_ap, vx, vy)

    return g.render()
