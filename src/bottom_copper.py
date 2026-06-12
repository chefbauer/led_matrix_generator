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

# Via-Parameter fuer Busbar-VDD-Verbindung (kleiner als normale Vias)
BUSBAR_VDD_VIA_DRILL = 0.30
BUSBAR_VDD_VIA_PAD   = 0.50

# Anschluss-Lötpad-Durchmesser (Kreisbahn-Aperture erzeugt Oval)
PAD_DIA_SIG = 1.2   # DAT/CLK Signalpads in mm
PAD_DIA_PWR = 2.4   # +5V/GND Leistungspads in mm


def busbar_vdd_via_positions(
    leds: List[LedInstance],
    pitch: float,
    x_offset: float,
) -> list:
    """
    Eine VDD-Via pro Reihe an der rechten Kante der Busbar-Zone.

    Diese Vias verbinden die VDD-Schiene (Bottom) mit der
    VDD-Sammelleitung im Busbar-Bereich (Top).

    X = rechter Rand der Busbar-Zone (x_offset - CLEARANCE - VIA_PAD/2)
    Y = VDD-Bus-Y der jeweiligen Reihe
    """
    rows: dict = {}
    for led in leds:
        rows.setdefault(led.row, []).append(led)

    via_x = x_offset - DR.CLEARANCE - BUSBAR_VDD_VIA_PAD / 2
    result = []
    for row_idx in sorted(rows.keys()):
        first = rows[row_idx][0]
        _, vy = fp_via_pos(first.x, first.y, first.rotation, "VDD", pitch)
        result.append((via_x, vy))
    return result


def build_bottom_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
    busbar: int = 0,
    led_current_ma: float = 15.0,
    copper_oz: float = 1.0,
    board_height: float = 0.0,
    x_offset: float = 0.0,
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

    w = DR.bus_width(pitch)

    # Busbar VDD-Via-Positionen (eine pro Reihe, an Busbar-rechter Kante)
    if busbar > 0:
        bb_vias = busbar_vdd_via_positions(leds, pitch, x_offset)
        bb_via_ap = g.add_aperture(ApertureShape.CIRCLE, BUSBAR_VDD_VIA_PAD)

    for row_idx in sorted(rows.keys()):
        row_leds = rows[row_idx]
        first = row_leds[0]

        for sig in ("VDD", "GND"):
            via_xs = []
            via_ys = []
            for led in row_leds:
                vx, vy = fp_via_pos(led.x, led.y, led.rotation, sig, pitch)
                via_xs.append(vx)
                via_ys.append(vy)

            sign = +1 if via_ys[0] > first.y else -1
            bus_y_val = first.y + sign * (DR.CLEARANCE + w / 2)
            x_max = max(via_xs) + w / 2

            if busbar > 0 and sig == "GND":
                # GND: Schiene laeuft bis ganz links (Boardrand + Clearance)
                x_min = DR.CLEARANCE
            elif busbar > 0 and sig == "VDD":
                # VDD: Schiene endet am Busbar-VDD-Via
                bb_via_x = x_offset - DR.CLEARANCE - BUSBAR_VDD_VIA_PAD / 2
                x_min = bb_via_x
            else:
                x_min = min(via_xs) - w / 2

            ap = trace_vdd if sig == "VDD" else trace_gnd
            g.draw(ap, x_min, bus_y_val, x_max, bus_y_val)

            for vx, vy in zip(via_xs, via_ys):
                g.flash(via_ap, vx, vy)

    # Busbar VDD-Vias auf Bottom flashen
    if busbar > 0:
        for vx, vy in bb_vias:
            g.flash(bb_via_ap, vx, vy)

    # -------------------------------------------------------------------
    # GND-Busbar: Volle Kupferflaeche + Anschluss-Loetpads (Bottom Layer)
    # Kupferflaeche muss Abstand zu Busbar-VDD-Vias einhalten!
    # -------------------------------------------------------------------
    if busbar > 0 and board_height > 0:
        via_x      = bb_vias[0][0]            # Busbar-VDD-Via X (alle gleich)
        pour_left  = DR.CLEARANCE
        pour_right = via_x - DR.VIA_PAD_D / 2 - DR.CLEARANCE
        pour_w     = pour_right - pour_left
        gnd_cx     = (pour_left + pour_right) / 2
        pour_h     = board_height - 2 * DR.CLEARANCE
        pour_ap    = g.add_aperture(ApertureShape.RECT, pour_w, pour_h)
        g.flash(pour_ap, gnd_cx, board_height / 2)

        # +5V / GND Anschluss-Loetpads (Bottom Layer, gleiche Positionen wie Top)
        pwr_x1 = DR.CLEARANCE + PAD_DIA_PWR / 2
        pwr_x2 = pour_right - PAD_DIA_PWR / 2
        pwr_ap = g.add_aperture(ApertureShape.CIRCLE, PAD_DIA_PWR)
        y_gnd  = DR.CLEARANCE + PAD_DIA_PWR / 2
        y_5v   = y_gnd + PAD_DIA_PWR + DR.CLEARANCE
        g.draw(pwr_ap, pwr_x1, y_gnd, pwr_x2, y_gnd)
        g.draw(pwr_ap, pwr_x1, y_5v,  pwr_x2, y_5v)

    return g.render()
