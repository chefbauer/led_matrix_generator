"""
CPL-Generator (Component Placement List) fuer JLCPCB SMT Assembly.

JLCPCB CPL-Format (CSV):
    Designator, Mid X, Mid Y, Layer, Rotation

Konventionen:
    - "Mid X" / "Mid Y" in mm mit Einheitssuffix, z.B. "2.000mm"
    - "Layer": "Top" oder "Bottom" (SK9822-EC20 immer "Top")
    - "Rotation": Drehwinkel in Grad, GEGEN den Uhrzeigersinn (CCW)
      gemaess JLCPCB/EasyEDA-Standard

Rotation-Mapping:
    Unsere interne Rotation (CCW) entspricht direkt dem JLCPCB-Wert.
    Gerade Reihen:    90 Grad CCW
    Ungerade Reihen: 270 Grad CCW

Verwendung:
    from cpl import build_cpl
    csv_text = build_cpl(leds)
"""

from __future__ import annotations

import csv
import io
from typing import List

from matrix import LedInstance


LAYER = "Top"   # SK9822-EC20 ist immer Top


def build_cpl(leds: List[LedInstance]) -> str:
    """
    Erzeugt den CPL-CSV-String fuer JLCPCB SMT Assembly.

    Parameters
    ----------
    leds : list[LedInstance]
        Alle platzierten LEDs mit Rotation.

    Returns
    -------
    str
        CSV-Inhalt mit Header-Zeile.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # JLCPCB-Header
    writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])

    for led in sorted(leds, key=lambda l: l.index):
        writer.writerow([
            led.ref,
            f"{led.x:.3f}mm",
            f"{led.y:.3f}mm",
            LAYER,
            int(led.rotation),
        ])

    return buf.getvalue()
