"""
Footprint-Definitionen fuer LED-Matrix-Generator.

Koordinatensystem: Ursprung (0,0) = Mittelpunkt des Gehaeuses.
Alle Masse in mm. Positiv-Y = nach unten (Gerber-Standard).

Pad-Layout SK9822-EC20 – geprueft gegen EasyEDA raw.json (C2909059):
  2 Spalten x 3 Reihen (NICHT 3x2 wie frueher angenommen!)

  EasyEDA-Einheit: 1 unit = 0.254 mm (= 10 mil)
  c_origin = (400, 300.118) = Gehaeusemittelpunkt

       links (-0.707)   rechts (+0.707)
  oben  (-0.800):  Pad1=DO    Pad6=CO
  mitte (+0.000):  Pad2=GND   Pad5=VDD
  unten (+0.800):  Pad3=DI    Pad4=CI

  Pin-1-Marker (Seidendruckkreis) oben-links -> Ecke bei (-1.680, -0.840)
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Pad:
    number: str        # Pad-Nummer als String (z.B. "1")
    signal: str        # Signalname im Footprint (VDD, GND, DI, DO, CI, CO)
    x: float           # X-Offset vom Bauteilmittelpunkt in mm
    y: float           # Y-Offset vom Bauteilmittelpunkt in mm
    width: float       # Pad-Breite in mm (in Bauteil-Eigenkoordinaten)
    height: float      # Pad-Hoehe in mm (in Bauteil-Eigenkoordinaten)


@dataclass
class Footprint:
    name: str
    description: str
    body_width: float   # Gehaeuse-Breite in mm
    body_height: float  # Gehaeuse-Hoehe in mm
    # Ecke des Pin-1-Markers relativ zum Gehaeusemittelpunkt (fuer CPL)
    pin1_corner_x: float = 0.0
    pin1_corner_y: float = 0.0
    pads: List[Pad] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SK9822-EC20 – Werte direkt aus EasyEDA raw.json (C2909059) berechnet
#
# Umrechnung: EasyEDA-Unit * 0.254 = mm
#
# Pad-Groesse:
#   width  = 3.4449 * 0.254 = 0.8750 mm
#   height = 1.5748 * 0.254 = 0.4000 mm
#
# Pad-Positionen (relativ c_origin = Gehaeusemitte):
#   X links  = (397.2165 - 400.0) * 0.254 = -0.7070 mm
#   X rechts = (402.7835 - 400.0) * 0.254 = +0.7070 mm
#   Y oben   = (296.968  - 300.118) * 0.254 = -0.8001 mm
#   Y mitte  = (300.118  - 300.118) * 0.254 =  0.0000 mm
#   Y unten  = (303.268  - 300.118) * 0.254 = +0.8001 mm
#
# Pin-1-Marker (Seidendruckkreis auf Layer 3):
#   (393.386 - 400.0) * 0.254 = -1.680 mm
#   (296.811 - 300.118) * 0.254 = -0.840 mm
# ---------------------------------------------------------------------------

PAD_W  = 0.8750   # Pad-Breite  (aus raw.json)
PAD_H  = 0.4000   # Pad-Hoehe   (aus raw.json)
PAD_XL = -0.7070  # X linke Spalte
PAD_XR = +0.7070  # X rechte Spalte
PAD_YT = -0.8001  # Y obere Reihe
PAD_YM =  0.0000  # Y mittlere Reihe
PAD_YB = +0.8001  # Y untere Reihe

SK9822_EC20 = Footprint(
    name="SK9822-EC20",
    description="Worldsemi SK9822-EC20, SPI RGB LED, 2x2mm, SMD2121-6P",
    body_width=2.0,
    body_height=2.0,
    pin1_corner_x=-1.680,
    pin1_corner_y=-0.840,
    pads=[
        # Linke Spalte (X = -0.707)
        Pad("1", "DO",  PAD_XL, PAD_YT, PAD_W, PAD_H),  # oben-links
        Pad("2", "GND", PAD_XL, PAD_YM, PAD_W, PAD_H),  # mitte-links
        Pad("3", "DI",  PAD_XL, PAD_YB, PAD_W, PAD_H),  # unten-links
        # Rechte Spalte (X = +0.707)
        Pad("4", "CI",  PAD_XR, PAD_YB, PAD_W, PAD_H),  # unten-rechts
        Pad("5", "VDD", PAD_XR, PAD_YM, PAD_W, PAD_H),  # mitte-rechts
        Pad("6", "CO",  PAD_XR, PAD_YT, PAD_W, PAD_H),  # oben-rechts
    ],
)


def get_pad(fp: Footprint, signal: str) -> Pad:
    """Pad eines Footprints anhand des Signalnamens zurueckgeben."""
    for pad in fp.pads:
        if pad.signal == signal:
            return pad
    raise KeyError(f"Signal '{signal}' nicht im Footprint '{fp.name}' gefunden")


FOOTPRINTS = {
    "SK9822-EC20": SK9822_EC20,
}


# ---------------------------------------------------------------------------
# Rotations- und Positionshilfen
# ---------------------------------------------------------------------------

def rotate_xy(x: float, y: float, degrees: float) -> Tuple[float, float]:
    """Punkt (x, y) um `degrees` Grad CCW um den Ursprung rotieren."""
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    return (x * c - y * s, x * s + y * c)


def pad_pos(
    led_x: float, led_y: float, rotation: float, pad: "Pad"
) -> Tuple[float, float]:
    """Absolute Position eines Pads nach Rotation des Bauteils."""
    rx, ry = rotate_xy(pad.x, pad.y, rotation)
    return (led_x + rx, led_y + ry)


# ---------------------------------------------------------------------------
# Via-Positionen im lokalen LED-Koordinatensystem (vor Rotation)
#
# VDD lokal: (+0.7070, 0.0000)  -> Via 0.5 mm weiter in +Y: (+0.7070, +0.5000)
# GND lokal: (-0.7070, 0.0000)  -> Via 0.5 mm weiter in -Y: (-0.7070, -0.5000)
#
# Nach 90° CCW-Rotation:
#   VDD-Via  -> (-0.5000, +0.7070)  -> gleiche rotierte Y wie VDD-Pad (+0.7070)
#   GND-Via  -> (+0.5000, -0.7070)  -> gleiche rotierte Y wie GND-Pad (-0.7070)
#   => Top-Stichleitung Via->Pad ist horizontal ✓
#   => VDD-Bus bei Y=led_y+0.707, GND-Bus bei Y=led_y-0.707 pro Zeile ✓
#
# Nach 270° CCW-Rotation:
#   VDD-Via  -> (+0.5000, -0.7070)  -> gleiche rotierte Y wie VDD-Pad (-0.7070)
#   GND-Via  -> (-0.5000, +0.7070)  -> gleiche rotierte Y wie GND-Pad (+0.7070)
#   => horizontal ✓, andere Seite als bei 90° ✓
# ---------------------------------------------------------------------------
_VIA_LOCAL: Dict[str, Tuple[float, float]] = {
    "VDD": (PAD_XR, +0.5000),
    "GND": (PAD_XL, -0.5000),
}


def via_pos(
    led_x: float, led_y: float, rotation: float, signal: str
) -> Tuple[float, float]:
    """Absolute Position der Power-Via fuer VDD oder GND nach Rotation."""
    lx, ly = _VIA_LOCAL[signal]
    rx, ry = rotate_xy(lx, ly, rotation)
    return (led_x + rx, led_y + ry)
