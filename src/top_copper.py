"""
Gerber-Generator fuer die Top-Copper-Lage (GTL).

Erzeugt in Reihenfolge:
  1. Alle LED-Pads (Flash)
  2. Datenkette: Traces DI/DO und CI/CO zwischen benachbarten LEDs
  3. Kurze Top-Stuecke Via -> Pad fuer VDD und GND
     (Vias selbst kommen aus power.py, hier nur die Top-Stichleitung)

Alle Masse in mm, Gerber-Format FSLAX46Y46.
"""

from __future__ import annotations
from typing import List
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, Footprint
from matrix import LedInstance


# Leiterbahnbreiten in mm
TRACE_DATA  = 0.15   # Daten-Traces (DI/DO, CI/CO)
TRACE_POWER = 0.20   # Kurze Power-Stichleitung Via -> Pad


def build_top_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    """
    Erzeugt die Top-Copper-Lage als Gerber-String.

    Ablauf:
        1. Pads aller LEDs flashen
        2. Daten-Traces zwischen benachbarten LEDs in der Kette
        3. Power-Stichleitungen Via -> VDD-Pad und Via -> GND-Pad
    """
    g = GerberWriter("Top Copper (GTL) - LED Matrix")

    # --- Aperturen definieren ---
    pad_rect = g.add_aperture(ApertureShape.RECT, fp.pads[0].width, fp.pads[0].height)
    trace_d  = g.add_aperture(ApertureShape.CIRCLE, TRACE_DATA)
    trace_p  = g.add_aperture(ApertureShape.CIRCLE, TRACE_POWER)
    via_ap   = g.add_aperture(ApertureShape.CIRCLE, 0.50)  # Via-Pad Top

    # ---------------------------------------------------------------
    # 1. LED-Pads flashen
    # ---------------------------------------------------------------
    for led in leds:
        for pad in fp.pads:
            px = led.x + pad.x
            py = led.y + pad.y
            g.flash(pad_rect, px, py)

    # ---------------------------------------------------------------
    # 2. Daten-Traces: DI/DO und CI/CO zwischen Ketten-Nachbarn
    #
    #    LED[idx].DO  --Trace-->  LED[idx+1].DI
    #    LED[idx].CO  --Trace-->  LED[idx+1].CI
    #
    #    Aber: DO und DI tragen denselben Netz-Namen -> eine direkte
    #    Trace vom DO-Pad von LED[n] zum DI-Pad von LED[n+1].
    # ---------------------------------------------------------------
    by_index = {led.index: led for led in leds}

    for led in leds:
        next_led = by_index.get(led.index + 1)
        if next_led is None:
            continue  # Letzte LED hat keinen Nachfolger

        # DO-Pad dieser LED -> DI-Pad naechste LED
        do_pad = get_pad(fp, "DO")
        di_pad = get_pad(fp, "DI")
        x1 = led.x + do_pad.x
        y1 = led.y + do_pad.y
        x2 = next_led.x + di_pad.x
        y2 = next_led.y + di_pad.y
        g.draw(trace_d, x1, y1, x2, y2)

        # CO-Pad dieser LED -> CI-Pad naechste LED
        co_pad = get_pad(fp, "CO")
        ci_pad = get_pad(fp, "CI")
        x1 = led.x + co_pad.x
        y1 = led.y + co_pad.y
        x2 = next_led.x + ci_pad.x
        y2 = next_led.y + ci_pad.y
        g.draw(trace_d, x1, y1, x2, y2)

    # ---------------------------------------------------------------
    # 3. Power-Stichleitungen Via -> Pad (Top Layer)
    #
    #    Via sitzt 0.5 mm horizontal neben dem Pad (ausserhalb, Richtung
    #    Board-Rand oder freier Flaeche).
    #    Konvention: VDD-Via links vom VDD-Pad, GND-Via links vom GND-Pad.
    # ---------------------------------------------------------------
    VIA_OFFSET_X = -0.7   # Via-Versatz in X-Richtung relativ zum Pad

    for led in leds:
        vdd_pad = get_pad(fp, "VDD")
        gnd_pad = get_pad(fp, "GND")

        # VDD
        pad_x = led.x + vdd_pad.x
        pad_y = led.y + vdd_pad.y
        via_x = pad_x + VIA_OFFSET_X
        via_y = pad_y
        g.flash(via_ap, via_x, via_y)        # Via-Pad auf Top
        g.draw(trace_p, via_x, via_y, pad_x, pad_y)

        # GND
        pad_x = led.x + gnd_pad.x
        pad_y = led.y + gnd_pad.y
        via_x = pad_x + VIA_OFFSET_X
        via_y = pad_y
        g.flash(via_ap, via_x, via_y)        # Via-Pad auf Top
        g.draw(trace_p, via_x, via_y, pad_x, pad_y)

    return g.render()
