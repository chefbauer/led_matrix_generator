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
from footprint import SK9822_EC20, pad_pos, via_pos, get_pad, has_pad, Footprint
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
    busbar: int = 0,
    x_offset: float = 0.0,
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

    # Busbar VDD-Vias + VDD-Kupferflaeche + Connector-Pads (Top)
    if busbar > 0:
        from bottom_copper import (busbar_vdd_via_positions, BUSBAR_VDD_VIA_PAD,
                                   PAD_DIA_SIG, PAD_DIA_PWR)
        bb_vias   = busbar_vdd_via_positions(leds, pitch, x_offset)
        bb_via_ap = g.add_aperture(ApertureShape.CIRCLE, BUSBAR_VDD_VIA_PAD + 2 * SM_EXP)
        for vx, vy in bb_vias:
            g.flash(bb_via_ap, vx, vy)

        # VDD-Kupferflaeche Freilegung (gleiche Abmessungen wie copper_top)
        busbar_w    = x_offset - 2 * DR.CLEARANCE - DR.BUS_GAP
        y_gnd_pad   = DR.CLEARANCE + PAD_DIA_PWR / 2
        y_5v_pad    = y_gnd_pad + PAD_DIA_PWR + DR.CLEARANCE
        via_ys      = [vy for _, vy in bb_vias]
        pour_bottom = min(min(via_ys) - DR.VIA_PAD_D / 2, y_5v_pad) - DR.CLEARANCE
        pour_top    = max(via_ys) + DR.VIA_PAD_D / 2 + DR.CLEARANCE
        pour_h_sm   = pour_top - pour_bottom + 2 * SM_EXP
        pour_cx_sm  = DR.CLEARANCE + busbar_w / 2
        pour_cy_sm  = (pour_top + pour_bottom) / 2
        pour_ap_sm  = g.add_aperture(ApertureShape.RECT,
                                     busbar_w + 2 * SM_EXP, pour_h_sm)
        g.flash(pour_ap_sm, pour_cx_sm, pour_cy_sm)

        # DAT/CLK Connector-Pad Freilegungen
        first_led  = min(leds, key=lambda l: l.index)
        di_x, di_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                              get_pad(fp, "DI"))
        sig_x1    = DR.CLEARANCE + PAD_DIA_SIG / 2
        sig_x2    = sig_x1 + PAD_DIA_SIG
        y_dat     = di_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
        sig_ap_sm = g.add_aperture(ApertureShape.CIRCLE, PAD_DIA_SIG + 2 * SM_EXP)
        g.draw(sig_ap_sm, sig_x1, y_dat, sig_x2, y_dat)
        if has_pad(fp, "CI"):
            ci_x, ci_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                                  get_pad(fp, "CI"))
            y_clk = ci_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
            g.draw(sig_ap_sm, sig_x1, y_clk, sig_x2, y_clk)

        # +5V / GND Anschluss-Pad Freilegungen (Top)
        pwr_x1    = DR.CLEARANCE + PAD_DIA_PWR / 2
        pwr_x2    = DR.CLEARANCE + busbar_w - PAD_DIA_PWR / 2
        pwr_ap_sm = g.add_aperture(ApertureShape.CIRCLE, PAD_DIA_PWR + 2 * SM_EXP)
        g.draw(pwr_ap_sm, pwr_x1, y_gnd_pad, pwr_x2, y_gnd_pad)
        g.draw(pwr_ap_sm, pwr_x1, y_5v_pad,  pwr_x2, y_5v_pad)

    return g.render()


def build_bottom_soldermask(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
    busbar: int = 0,
    led_current_ma: float = 15.0,
    copper_oz: float = 1.0,
    board_height: float = 0.0,
    x_offset: float = 0.0,
) -> str:
    """Bottom Solder Mask: Oeffnungen ueber Via-Pads und GND-Busbar-Bereich."""
    g = GerberWriter("Bottom Solder Mask (GBS)")
    via_ap = g.add_aperture(ApertureShape.CIRCLE, VIA_PAD_D + 2 * SM_EXP)

    for vx, vy in _via_list(leds, pitch):
        g.flash(via_ap, vx, vy)

    # GND-Busbar Freilegung (nur GND-Bereich auf Bottom; VDD-Busbar ist auf Top)
    if busbar > 0 and board_height > 0 and x_offset > 0:
        from bottom_copper import (busbar_vdd_via_positions, BUSBAR_VDD_VIA_PAD,
                                   PAD_DIA_PWR)
        bb_vias    = busbar_vdd_via_positions(leds, pitch, x_offset)
        via_x      = bb_vias[0][0]
        pour_left  = DR.CLEARANCE
        pour_right = via_x - DR.VIA_PAD_D / 2 - DR.CLEARANCE
        pour_w     = pour_right - pour_left
        gnd_cx     = (pour_left + pour_right) / 2
        pour_h     = board_height - 2 * DR.CLEARANCE
        # Freilegung gleich gross wie Kupferflaeche (keine Expansion noetig)
        pour_ap    = g.add_aperture(ApertureShape.RECT, pour_w, pour_h)
        g.flash(pour_ap, gnd_cx, board_height / 2)

        # Busbar VDD-Vias auf Bottom (separate Freilegungen)
        bb_via_ap_bsm = g.add_aperture(ApertureShape.CIRCLE,
                                       BUSBAR_VDD_VIA_PAD + 2 * SM_EXP)
        for vx, vy in bb_vias:
            g.flash(bb_via_ap_bsm, vx, vy)

    return g.render()


def build_board_outline(
    cols: int,
    rows: int,
    pitch: float,
    margin: float = 2.0,
    extra_left: float = 0.0,
) -> str:
    """Board Outline (GKO): Rechteck passend zur Matrix."""
    g = GerberWriter("Board Outline (GKO)")
    outline_ap = g.add_aperture(ApertureShape.CIRCLE, 0.05)

    w, h = board_size(cols, rows, pitch, margin, extra_left=extra_left)
    g.rect_outline(outline_ap, 0.0, 0.0, w, h)
    return g.render()


def build_drill(
    leds: List[LedInstance],
    fp: Footprint = SK9822_EC20,
    pitch: float = 5.0,
    busbar: int = 0,
    x_offset: float = 0.0,
) -> str:
    """
    Excellon Drill File fuer alle Bohrungen.

    T1 = Via-Bohrungen (VIA_DRILL, 0.30 mm)
    T2 = DAT/CLK Connector-Pads (0.80 mm), nur wenn busbar > 0
    T3 = +5V/GND Connector-Pads (1.00 mm), nur wenn busbar > 0
    """
    SIG_DRILL = 0.80   # mm, DAT/CLK Connector-Pads
    PWR_DRILL = 1.00   # mm, +5V/GND Connector-Pads

    lines = [
        "M48",
        "METRIC,TZ",
    ]

    # Werkzeug-Definitionen
    lines.append(f"T1C{VIA_DRILL:.3f}")
    if busbar > 0:
        lines.append(f"T2C{SIG_DRILL:.3f}")
        lines.append(f"T3C{PWR_DRILL:.3f}")

    lines.append("%")

    # -- T1: Via-Bohrungen --------------------------------------------------
    lines.append("T1")
    lines.append("G05")

    for vx, vy in _via_list(leds, pitch):
        xi = round(vx * 1000)
        yi = round(vy * 1000)
        lines.append(f"X{xi:+07d}Y{yi:+07d}")

    # Busbar VDD-Vias (gleicher Durchmesser wie normale Vias -> T1)
    if busbar > 0:
        from bottom_copper import busbar_vdd_via_positions
        for vx, vy in busbar_vdd_via_positions(leds, pitch, x_offset):
            xi = round(vx * 1000)
            yi = round(vy * 1000)
            lines.append(f"X{xi:+07d}Y{yi:+07d}")

    # -- T2: DAT/CLK Connector-Pads ------------------------------------------
    if busbar > 0:
        from bottom_copper import PAD_DIA_SIG
        from footprint import get_pad, has_pad, pad_pos

        first_led = min(leds, key=lambda l: l.index)
        di_x, di_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                             get_pad(fp, "DI"))
        sig_x1 = DR.CLEARANCE + PAD_DIA_SIG / 2
        sig_x2 = sig_x1 + PAD_DIA_SIG
        sig_cx = (sig_x1 + sig_x2) / 2
        y_dat = di_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE

        lines.append("T2")
        xi = round(sig_cx * 1000)
        yi = round(y_dat * 1000)
        lines.append(f"X{xi:+07d}Y{yi:+07d}")

        if has_pad(fp, "CI"):
            ci_x, ci_y = pad_pos(first_led.x, first_led.y, first_led.rotation,
                                 get_pad(fp, "CI"))
            y_clk = ci_y + PAD_DIA_SIG / 2 + 2 * DR.CLEARANCE
            yi = round(y_clk * 1000)
            lines.append(f"X{xi:+07d}Y{yi:+07d}")

    # -- T3: +5V/GND Connector-Pads ------------------------------------------
    if busbar > 0:
        from bottom_copper import busbar_vdd_via_positions, PAD_DIA_PWR

        lines.append("T3")

        bb_vias   = busbar_vdd_via_positions(leds, pitch, x_offset)
        via_x     = bb_vias[0][0]
        pour_right = via_x - DR.VIA_PAD_D / 2 - DR.CLEARANCE
        pwr_x1 = DR.CLEARANCE + PAD_DIA_PWR / 2
        pwr_x2 = pour_right - PAD_DIA_PWR / 2
        pwr_cx = (pwr_x1 + pwr_x2) / 2
        y_gnd  = DR.CLEARANCE + PAD_DIA_PWR / 2
        y_5v   = y_gnd + PAD_DIA_PWR + DR.CLEARANCE

        xi = round(pwr_cx * 1000)
        for y in (y_gnd, y_5v):
            yi = round(y * 1000)
            lines.append(f"X{xi:+07d}Y{yi:+07d}")

    lines.append("M30")
    return "\n".join(lines) + "\n"
