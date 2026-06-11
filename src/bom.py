"""
BOM-Generator (Bill of Materials) fuer JLCPCB SMT Assembly.

JLCPCB BOM-Format (CSV):
    Comment, Designator, Footprint, JLCPCB Part #

Konventionen:
    - Mehrere Bestückungsreferenzen in "Designator" kommasepariert
    - "Comment" = Herstellerteilenummer (MFR Part)
    - "Footprint" = EasyEDA-Footprint-Name aus den Komponentendaten

Verwendung:
    from bom import build_bom
    csv_text = build_bom(leds, component_info)
"""

from __future__ import annotations

import csv
import io
from typing import List

from component_data import ComponentInfo
from matrix import LedInstance


def build_bom(
    leds: List[LedInstance],
    component: ComponentInfo,
) -> str:
    """
    Erzeugt den BOM-CSV-String fuer JLCPCB SMT Assembly.

    Parameters
    ----------
    leds : list[LedInstance]
        Alle platzierten LEDs der Matrix.
    component : ComponentInfo
        Komponentendaten aus dem EasyEDA/JLCPCB-Cache.

    Returns
    -------
    str
        CSV-Inhalt mit Header-Zeile.
    """
    # Alle Referenzen alphabetisch sortieren
    designators = sorted([led.ref for led in leds], key=lambda r: int(r[1:]))
    designator_str = ",".join(designators)

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # JLCPCB-Header
    writer.writerow(["Comment", "Designator", "Footprint", "JLCPCB Part #"])

    writer.writerow([
        component.mfr_part,
        designator_str,
        component.package,
        component.jlcpcb_part,
    ])

    return buf.getvalue()
