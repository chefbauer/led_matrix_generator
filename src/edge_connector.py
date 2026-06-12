"""
Edge-Connector (Halb-Loecher / castellations) an den Board-Kanten.

Aktiv wenn busbar=0 + 4-Pin LED.  Vias an x=0 (links) und x=w (rechts).
Links:  GND, DI, VCC
Rechts: GND, DO, VCC
"""

from __future__ import annotations
from typing import List
from dataclasses import dataclass

from footprint import Footprint, get_pad, has_pad, pad_pos
from matrix import LedInstance


@dataclass
class EdgeVia:
    signal: str
    x: float
    y: float


VIA_PAD_DIA = 0.9
VIA_DRILL   = 0.6


# ---------------------------------------------------------------------------
def _fmt(x: float) -> str:
    return str(int(round(x * 1_000_000)))


def _draw_cmd(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"X{_fmt(x1)}Y{_fmt(y1)}D02*\nX{_fmt(x2)}Y{_fmt(y2)}D01*\n"


def _flash_cmd(x: float, y: float) -> str:
    return f"X{_fmt(x)}Y{_fmt(y)}D03*\n"


# ---------------------------------------------------------------------------
# placement
# ---------------------------------------------------------------------------

def place_left(leds: List[LedInstance], fp: Footprint,
               board_h: float) -> List[EdgeVia]:
    return [
        EdgeVia("GND", 0.0, board_h - 1.0),
        EdgeVia("DI",  0.0, board_h / 2.0),
        EdgeVia("VCC", 0.0, 1.0),
    ]


def place_right(leds: List[LedInstance], fp: Footprint,
                board_w: float, board_h: float) -> List[EdgeVia]:
    return [
        EdgeVia("GND", board_w, board_h - 1.0),
        EdgeVia("DO",  board_w, board_h / 2.0),
        EdgeVia("VCC", board_w, 1.0),
    ]


def _pad(led, fp, sig):
    return pad_pos(led.x, led.y, led.rotation, get_pad(fp, sig))


# ---------------------------------------------------------------------------
# layer generators (raw RS-274X injected before M02)
# ---------------------------------------------------------------------------

def edge_gtl(left: List[EdgeVia], right: List[EdgeVia],
             leds: List[LedInstance], fp: Footprint) -> str:
    L = []
    L.append(f"%ADD22C,{VIA_PAD_DIA:.6f}*%")
    L.append(f"%ADD23C,0.200000*%")
    L.append("G01*\nG54D22*")
    all_vias = left + right
    for ev in all_vias:
        L.append(_flash_cmd(ev.x, ev.y))
    L.append("G54D23*")

    # DI trace (left, from D1)
    d1 = min(leds, key=lambda l: l.index)
    di_sx, di_sy = _pad(d1, fp, "DI")
    for ev in left:
        if ev.signal == "DI":
            L.append(_draw_cmd(ev.x, ev.y, di_sx, di_sy))

    # DO trace (right, from last LED)
    last = max(leds, key=lambda l: l.index)
    do_sx, do_sy = _pad(last, fp, "DO")
    for ev in right:
        if ev.signal == "DO":
            L.append(_draw_cmd(ev.x, ev.y, do_sx, do_sy))

    return "".join(L)


def edge_gbl(left: List[EdgeVia], right: List[EdgeVia]) -> str:
    L = [f"%ADD22C,{VIA_PAD_DIA:.6f}*%", "G01*\nG54D22*"]
    for ev in left + right:
        L.append(_flash_cmd(ev.x, ev.y))
        if ev.signal in ("GND", "VCC"):
            if ev.x < 10:
                L.append(_draw_cmd(ev.x, ev.y, ev.x + 1.6, ev.y))
            else:
                L.append(_draw_cmd(ev.x, ev.y, ev.x - 1.6, ev.y))
    return "".join(L)


def edge_mask(vias: List[EdgeVia]) -> str:
    dia = VIA_PAD_DIA + 0.30
    L = [f"%ADD22C,{dia:.6f}*%", "G01*\nG54D22*"]
    for ev in vias:
        L.append(_flash_cmd(ev.x, ev.y))
    return "".join(L)


def edge_silk(vias: List[EdgeVia]) -> str:
    L = ["%ADD22C,0.150000*%", "G01*\nG54D22*"]
    for ev in vias:
        sx = ev.x + 1.5
        L.append(_draw_cmd(sx, ev.y, sx + 1.0, ev.y))
    return "".join(L)


def edge_drill(vias: List[EdgeVia]) -> str:
    L = ["T2"]
    for ev in vias:
        L.append(f"X{round(ev.x*1000):+07d}Y{round(ev.y*1000):+07d}")
    return "\n".join(L)
