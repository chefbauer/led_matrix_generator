"""
Gerber-Generator fuer die Top-Copper-Lage (GTL).

Erzeugt in Reihenfolge:
  1. Alle LED-Pads (Flash, rotiert pro Reihe)
  2. Datenkette: DO->DI und CO->CI zwischen Ketten-Nachbarn
  3. Power-Stichleitungen Via -> VDD-Pad und Via -> GND-Pad (horizontal)

Rotation:
  Gerade Reihen (->): 90 Grad CCW -> DI links, DO rechts
  Ungerade Reihen (<-): 270 Grad CCW -> DI rechts, DO links

  Das stellt sicher, dass DO und DI bei Horizontal-Nachbarn auf
  einander zugewandten Seiten liegen.
  Bei Zeilen-Uebergaengen (D3->D4) liegt DO/DI auf derselben
  X-Koordinate -> senkrechter Uebergangs-Trace.
"""

from __future__ import annotations
from typing import List
from gerber_writer import GerberWriter, ApertureShape
from footprint import SK9822_EC20, get_pad, pad_pos, via_pos, Footprint
from matrix import LedInstance
from router import route, led_obstacles


TRACE_DATA  = 0.15   # Daten-Traces (DI/DO, CI/CO)
TRACE_POWER = 0.20   # Power-Stichleitung Via -> Pad


def build_top_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
) -> str:
    g = GerberWriter("Top Copper (GTL) - LED Matrix")

    # Zwei Apertures: bei 0°/180° Original, bei 90°/270° Breite<->Hoehe getauscht
    pw, ph = fp.pads[0].width, fp.pads[0].height
    pad_ap_0   = g.add_aperture(ApertureShape.RECT, pw, ph)   # fuer 0° / 180°
    pad_ap_90  = g.add_aperture(ApertureShape.RECT, ph, pw)   # fuer 90° / 270°
    trace_d  = g.add_aperture(ApertureShape.CIRCLE, TRACE_DATA)
    trace_p  = g.add_aperture(ApertureShape.CIRCLE, TRACE_POWER)
    via_ap   = g.add_aperture(ApertureShape.CIRCLE, 0.50)

    def _pad_ap(rotation: float) -> int:
        return pad_ap_90 if rotation % 180 != 0 else pad_ap_0

    # -------------------------------------------------------------------
    # 1. LED-Pads flashen (rotierte Positionen, rotiertes Aperture)
    # -------------------------------------------------------------------
    for led in leds:
        ap = _pad_ap(led.rotation)
        for pad in fp.pads:
            px, py = pad_pos(led.x, led.y, led.rotation, pad)
            g.flash(ap, px, py)

    # -------------------------------------------------------------------
    # 2. Datenkette: DO -> DI und CO -> CI  (H/V/45-Router)
    # -------------------------------------------------------------------
    by_index = {led.index: led for led in leds}
    obstacles = led_obstacles(leds, fp.body_width, fp.body_height)

    for led in leds:
        next_led = by_index.get(led.index + 1)
        if next_led is None:
            continue

        do_pad = get_pad(fp, "DO")
        di_pad = get_pad(fp, "DI")
        x1, y1 = pad_pos(led.x,      led.y,      led.rotation,      do_pad)
        x2, y2 = pad_pos(next_led.x, next_led.y, next_led.rotation, di_pad)
        path = route(x1, y1, x2, y2, obstacles,
                     (led.x, led.y), (next_led.x, next_led.y),
                     trace_w=TRACE_DATA)
        for i in range(len(path) - 1):
            g.draw(trace_d, path[i][0], path[i][1], path[i+1][0], path[i+1][1])

        co_pad = get_pad(fp, "CO")
        ci_pad = get_pad(fp, "CI")
        x1, y1 = pad_pos(led.x,      led.y,      led.rotation,      co_pad)
        x2, y2 = pad_pos(next_led.x, next_led.y, next_led.rotation, ci_pad)
        path = route(x1, y1, x2, y2, obstacles,
                     (led.x, led.y), (next_led.x, next_led.y),
                     trace_w=TRACE_DATA)
        for i in range(len(path) - 1):
            g.draw(trace_d, path[i][0], path[i][1], path[i+1][0], path[i+1][1])

    # -------------------------------------------------------------------
    # 3. Power-Stichleitungen Via -> Pad (Top Layer)
    #
    #    Da Via und Pad nach der Rotation dieselbe rotierte Y-Koordinate
    #    haben, sind diese Traces horizontal.
    # -------------------------------------------------------------------
    for led in leds:
        for sig in ("VDD", "GND"):
            vx, vy = via_pos(led.x, led.y, led.rotation, sig)
            px, py = pad_pos(led.x, led.y, led.rotation, get_pad(fp, sig))
            g.flash(via_ap, vx, vy)
            g.draw(trace_p, vx, vy, px, py)

    return g.render()
