"""
Footprint-Definitionen fuer LED-Matrix-Generator.

Koordinatensystem: Ursprung (0,0) = Mittelpunkt des Gehaeuses.
Alle Masse in mm. Positiv-Y = nach unten (Gerber-Standard).

Pad-Layout SK9822-EC20 (SMD2121-6P, 2.0x2.0mm Gehaeuse):
  Drei Pads oben (Y negativ), drei Pads unten (Y positiv).
  Pin-Nummerierung laut Datenblatt:

    Pin 4 (VDD) | Pin 5 (DO)  | Pin 6 (CO)
    ------------|-------------|------------
    Pin 3 (DI)  | Pin 2 (CI)  | Pin 1 (GND)

  Geprueft gegen Weltsuemi SK9822-EC20 Datenblatt, Packagezeichnung.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Pad:
    number: str        # Pad-Nummer als String (z.B. "1")
    signal: str        # Signalname im Footprint (VDD, GND, DI, DO, CI, CO)
    x: float           # X-Offset vom Bauteilmittelpunkt in mm
    y: float           # Y-Offset vom Bauteilmittelpunkt in mm
    width: float       # Pad-Breite in mm
    height: float      # Pad-Hoehe in mm


@dataclass
class Footprint:
    name: str
    description: str
    body_width: float   # Gehaeuse-Breite in mm
    body_height: float  # Gehaeuse-Hoehe in mm
    pads: List[Pad] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SK9822-EC20
# Gehaeuse: 2.0 x 2.0 mm
# Pad-Groesse: 0.60 x 0.35 mm (laut Packagezeichnung)
# Pad-Abstand zur Mitte: Y = +/- 0.675 mm (Padmitte)
# X-Positionen: -0.60, 0.00, +0.60 mm
#
# Pad-Reihe oben (Y = -0.675):  Pin 6 (CO), Pin 5 (DO), Pin 4 (VDD)
#   - Pin 6 links, Pin 5 Mitte, Pin 4 rechts
# Pad-Reihe unten (Y = +0.675): Pin 1 (GND), Pin 2 (CI), Pin 3 (DI)
#   - Pin 1 links, Pin 2 Mitte, Pin 3 rechts
#
# Bestueckungsrotation 0 Grad: Pin 1 unten-links
# ---------------------------------------------------------------------------

PAD_W = 0.60   # Pad-Breite
PAD_H = 0.35   # Pad-Hoehe
PAD_Y = 0.675  # Y-Abstand Padmitte zur Bauteilmitte
PAD_X = [      # X-Positionen links / mitte / rechts
    -0.60,
     0.00,
    +0.60,
]

SK9822_EC20 = Footprint(
    name="SK9822-EC20",
    description="Worldsemi SK9822-EC20, SPI RGB LED, 2x2mm, SMD2121-6P",
    body_width=2.0,
    body_height=2.0,
    pads=[
        # Untere Reihe (Y positiv = unten)
        Pad("1", "GND", PAD_X[0], +PAD_Y, PAD_W, PAD_H),
        Pad("2", "CI",  PAD_X[1], +PAD_Y, PAD_W, PAD_H),
        Pad("3", "DI",  PAD_X[2], +PAD_Y, PAD_W, PAD_H),
        # Obere Reihe (Y negativ = oben)
        Pad("4", "VDD", PAD_X[2], -PAD_Y, PAD_W, PAD_H),
        Pad("5", "DO",  PAD_X[1], -PAD_Y, PAD_W, PAD_H),
        Pad("6", "CO",  PAD_X[0], -PAD_Y, PAD_W, PAD_H),
    ],
)


def get_pad(fp: Footprint, signal: str) -> Pad:
    """Pad eines Footprints anhand des Signalnamens zurueckgeben."""
    for pad in fp.pads:
        if pad.signal == signal:
            return pad
    raise KeyError(f"Signal '{signal}' nicht im Footprint '{fp.name}' gefunden")


# Verfuegbare Footprints per Name abrufbar
FOOTPRINTS = {
    "SK9822-EC20": SK9822_EC20,
}
