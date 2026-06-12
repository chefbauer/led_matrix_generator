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
from footprint import SK9822_EC20, get_pad, has_pad, pad_pos, via_pos, Footprint
from matrix import LedInstance
from router import route, led_obstacles
import design_rules as DR

TRACE_DATA  = DR.TRACE_DATA    # 0.15 mm
TRACE_POWER = DR.TRACE_POWER   # 0.20 mm


def build_top_copper(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
    busbar: int = 0,
    x_offset: float = 0.0,
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

        if led.row != next_led.row and abs(x1 - x2) < 0.01:
            # Reihen-Uebergang: beide Pads auf gleicher X, Trace laeuft durch Koerper.
            # Beide Traces als U-Route nach aussen. Damit sie sich nicht kreuzen:
            #   CLK innen (x_inner): kuerzer, horizontale Segmente enden vor DAT-Vertikale
            #   DAT aussen (x_outer): weiter, horizontale Segmente ausserhalb CLK-Vertikale
            # Reihe gerade (270°) -> aussen = rechts (+), ungerade (90°) -> links (-)
            offset_sign = +1.0 if led.rotation == 270.0 else -1.0
            x_inner = led.x + offset_sign * (fp.body_width / 2 + DR.TRACE_DATA / 2 + DR.MIN_SPACING)
            x_outer = x_inner + offset_sign * (DR.TRACE_DATA + DR.MIN_SPACING)
            dat_path = [(x1, y1), (x_outer, y1), (x_outer, y2), (x2, y2)]
        else:
            dat_path = route(x1, y1, x2, y2, obstacles,
                             (led.x, led.y), (next_led.x, next_led.y),
                             trace_w=TRACE_DATA)
        for i in range(len(dat_path) - 1):
            g.draw(trace_d, dat_path[i][0], dat_path[i][1], dat_path[i+1][0], dat_path[i+1][1])

        co_pad = get_pad(fp, "CO") if has_pad(fp, "CO") else None
        ci_pad = get_pad(fp, "CI") if has_pad(fp, "CI") else None
        if co_pad is None or ci_pad is None:
            continue   # LED ohne CLK (z.B. 4-Pad WS2812-kompatibel), CLK-Trace weglassen
        x1, y1 = pad_pos(led.x,      led.y,      led.rotation,      co_pad)
        x2, y2 = pad_pos(next_led.x, next_led.y, next_led.rotation, ci_pad)

        if led.row != next_led.row and abs(x1 - x2) < 0.01:
            # CLK-Trace: innen (x_inner), damit keine Kreuzung mit DAT (x_outer)
            offset_sign = +1.0 if led.rotation == 270.0 else -1.0
            x_inner = led.x + offset_sign * (fp.body_width / 2 + DR.TRACE_DATA / 2 + DR.MIN_SPACING)
            clk_path = [(x1, y1), (x_inner, y1), (x_inner, y2), (x2, y2)]
        else:
            clk_path = route(x1, y1, x2, y2, obstacles,
                             (led.x, led.y), (next_led.x, next_led.y),
                             trace_w=TRACE_DATA)
        for i in range(len(clk_path) - 1):
            g.draw(trace_d, clk_path[i][0], clk_path[i][1], clk_path[i+1][0], clk_path[i+1][1])

    # -------------------------------------------------------------------
    # 3. Power-Stichleitungen Via -> Pad (senkrecht, Top Layer)
    #
    #    Via liegt auf gleicher X wie Pad, Y auf Schienen-Mittellinie.
    #    Stichleitung: senkrechte Linie von pad_y bis via_y.
    # -------------------------------------------------------------------
    pitch = pitch  # aus Parameter
    for led in leds:
        for sig in ("VDD", "GND"):
            vx, vy = via_pos(led.x, led.y, led.rotation, sig, pitch)
            px, py = pad_pos(led.x, led.y, led.rotation, get_pad(fp, sig))
            g.flash(via_ap, vx, vy)
            # Stichleitung: senkrecht vom Pad bis zur Via (gleiche X)
            g.draw(trace_p, px, py, vx, vy)

    # -------------------------------------------------------------------
    # 4. Busbar VDD-Sammelleitung + Connector-Bereich (Top Layer)
    # -------------------------------------------------------------------
    if busbar > 0:
        from bottom_copper import (busbar_vdd_via_positions, BUSBAR_VDD_VIA_PAD,
                                   PAD_DIA_SIG, PAD_DIA_PWR)
        bb_vias   = busbar_vdd_via_positions(leds, pitch, x_offset)
        bb_via_ap = g.add_aperture(ApertureShape.CIRCLE, BUSBAR_VDD_VIA_PAD)
        bb_trace  = g.add_aperture(ApertureShape.CIRCLE, DR.TRACE_POWER)

        # Via-Pads auf Top flashen
        for vx, vy in bb_vias:
            g.flash(bb_via_ap, vx, vy)

        # Vertikale Sammelleitung von unterster bis oberster VDD-Via
        if len(bb_vias) > 1:
            ys = [vy for _, vy in bb_vias]
            bx = bb_vias[0][0]  # alle gleiche X
            g.draw(bb_trace, bx, min(ys), bx, max(ys))

        # -------------------------------------------------------------------
        # 5. VDD-Kupferflaeche (Top), horizontale Verteilleitungen,
        #    DAT/CLK Connector-Pads, +5V/GND Anschluss-Loetpads
        # -------------------------------------------------------------------
        busbar_w  = x_offset - 2 * DR.CLEARANCE - DR.BUS_GAP
        pour_cx   = DR.CLEARANCE + busbar_w / 2

        # +5V/GND Anschlusspad-Positionen (benoetigt fuer pour_bottom)
        y_gnd_pad = DR.CLEARANCE + PAD_DIA_PWR / 2
        y_5v_pad  = y_gnd_pad + PAD_DIA_PWR + DR.CLEARANCE

        # VDD-Kupferflaeche: deckt alle Busbar-VDD-Vias ab + 5V-Pad
        via_ys      = [vy for _, vy in bb_vias]
        pour_bottom = min(min(via_ys) - DR.VIA_PAD_D / 2, y_5v_pad) - DR.CLEARANCE
        pour_top    = max(via_ys) + DR.VIA_PAD_D / 2 + DR.CLEARANCE
        pour_h      = pour_top - pour_bottom
        pour_cy     = (pour_top + pour_bottom) / 2
        pour_ap     = g.add_aperture(ApertureShape.RECT, busbar_w, pour_h)
        g.flash(pour_ap, pour_cx, pour_cy)

        # Horizontale VDD-Verteilleitungen (0.6 mm, eine pro Reihe)
        rows_vdd: dict = {}
        for led in leds:
            rows_vdd.setdefault(led.row, []).append(led)
        vdd_h_ap = g.add_aperture(ApertureShape.CIRCLE, 0.6)
        bb_x = bb_vias[0][0]
        for row_idx in sorted(rows_vdd.keys()):
            row_leds_v = rows_vdd[row_idx]
            first_v    = min(row_leds_v, key=lambda l: l.index)
            _, via_y_v = via_pos(first_v.x, first_v.y, first_v.rotation, "VDD", pitch)
            x_right_v  = max(via_pos(l.x, l.y, l.rotation, "VDD", pitch)[0]
                             for l in row_leds_v)
            g.draw(vdd_h_ap, bb_x, via_y_v, x_right_v, via_y_v)

        # DAT/CLK Connector-Pads + L-foermiges Routing zu LED D1
        first_led  = min(leds, key=lambda l: l.index)
        di_x, di_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                              get_pad(fp, "DI"))
        has_clk    = has_pad(fp, "CI")
        if has_clk:
            ci_x, ci_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                                  get_pad(fp, "CI"))
        sig_x1  = DR.CLEARANCE + PAD_DIA_SIG / 2
        sig_x2  = sig_x1 + PAD_DIA_SIG
        sig_cx  = (sig_x1 + sig_x2) / 2
        y_dat   = di_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
        sig_ap   = g.add_aperture(ApertureShape.CIRCLE, PAD_DIA_SIG)
        trace_ct = g.add_aperture(ApertureShape.CIRCLE, TRACE_DATA)
        g.draw(sig_ap,   sig_x1, y_dat, sig_x2, y_dat)   # DAT-Pad
        g.draw(trace_ct, sig_cx, y_dat, di_x,   y_dat)   # DAT horizontal
        g.draw(trace_ct, di_x,   y_dat, di_x,   di_y)    # DAT vertikal
        if has_clk:
            y_clk = ci_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
            g.draw(sig_ap,   sig_x1, y_clk, sig_x2, y_clk)   # CLK-Pad
            g.draw(trace_ct, sig_cx, y_clk, ci_x,   y_clk)   # CLK horizontal
            g.draw(trace_ct, ci_x,   y_clk, ci_x,   ci_y)    # CLK vertikal

        # +5V / GND Anschluss-Loetpads (Top Layer, gleiche Position wie Bottom)
        pwr_x1   = DR.CLEARANCE + PAD_DIA_PWR / 2
        pwr_x2   = DR.CLEARANCE + busbar_w - PAD_DIA_PWR / 2
        pwr_ap_t = g.add_aperture(ApertureShape.CIRCLE, PAD_DIA_PWR)
        g.draw(pwr_ap_t, pwr_x1, y_gnd_pad, pwr_x2, y_gnd_pad)  # GND-Pad
        g.draw(pwr_ap_t, pwr_x1, y_5v_pad,  pwr_x2, y_5v_pad)   # +5V-Pad

    return g.render()
