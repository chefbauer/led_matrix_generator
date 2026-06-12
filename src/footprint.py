"""
Footprint-Definitionen fuer LED-Matrix-Generator.

Koordinatensystem
-----------------
Ursprung (0,0) = Mittelpunkt des Gehaeuses. Alle Masse in mm.
Gerber RS-274X: Y waechst nach OBEN (Math-Koordinaten).

WICHTIG: Y-Flip bei EasyEDA-Import (verifiziert 2026-06-11)
------------------------------------------------------------
EasyEDA speichert Pad-Koordinaten mit Screen-Koordinaten (Y waechst nach UNTEN).
Gerber RS-274X nutzt Math-Koordinaten (Y waechst nach OBEN).
=> Beim Import aus raw.json das Y-Vorzeichen NEGIEREN!

Ohne Y-Flip waeren DO und DI gespiegelt (DO schiene unten, ist aber oben).
Verifiziert anhand EasyEDA Library Screenshot SK9822-EC20:
  Schaltzeichen: SDO=Pin1 links-oben, GND=Pin2 links-mitte, SDI=Pin3 links-unten
  Package (Foto): Pin1-Punkt oben-links -> Pad1=DO oben-links, Pad3=DI unten-links

SK9822-EC20 Pad-Layout (KORREKT, nach Y-Flip, Gerber-Koordinaten)
------------------------------------------------------------------
  Oben  (+0.800):  Pad1=DO  (links)   Pad6=CO  (rechts)
  Mitte (+0.000):  Pad2=GND (links)   Pad5=VDD (rechts)
  Unten (-0.800):  Pad3=DI  (links)   Pad4=CI  (rechts)

Rotationskonvention
-------------------
Gerade Reihen (Richtung rechts): 270 Grad CCW (= 90 Grad CW)
  Ergebnis:
    Links:  DI oben->links,  CI unten->links   = EINGAENGE
    Rechts: DO oben->rechts, CO unten->rechts  = AUSGAENGE
    Oben:   GND                                 = MINUS (-)
    Unten:  VDD                                 = PLUS  (+)

Ungerade Reihen (Richtung links): 90 Grad CCW
  Ergebnis: gespiegelt, Eingaenge rechts, Ausgaenge links.

Die Ausgaenge zeigen immer zur naechsten LED.
Strom kommt oben an (-) und geht unten raus (+).
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
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
# SK9822-EC20 – Werte direkt aus EasyEDA raw.json (C2909059), Y-Flip korrigiert.
#
# EasyEDA nutzt Screen-Koordinaten (Y nach unten).
# Gerber nutzt Math-Koordinaten (Y nach oben).
# => Y-Werte aus raw.json NEGIEREN fuer korrekte Gerber-Darstellung.
#
# Korrekte Lage im Gerber-Viewer (Y oben):
#   Oben  (+0.800): DO (links), CO (rechts)
#   Mitte (+0.000): GND (links), VDD (rechts)
#   Unten (-0.800): DI (links), CI (rechts)
#
# Mit 270° CCW (= 90° CW) Rotation fuer Reihe nach rechts:
#   Links:  DI (unten), CI (oben)  = EINGAENGE
#   Rechts: DO (unten), CO (oben)  = AUSGAENGE
#   Oben:   GND                    = MINUS
#   Unten:  VDD                    = PLUS
# ---------------------------------------------------------------------------

PAD_W  = 0.8750   # Pad-Breite  (aus raw.json)
PAD_H  = 0.4000   # Pad-Hoehe   (aus raw.json)
PAD_XL = -0.7070  # X linke Spalte
PAD_XR = +0.7070  # X rechte Spalte
PAD_YT = +0.8001  # Y oben  (negiert: EasyEDA -0.8001 -> Gerber +0.8001)
PAD_YM =  0.0000  # Y mitte
PAD_YB = -0.8001  # Y unten (negiert: EasyEDA +0.8001 -> Gerber -0.8001)

SK9822_EC20 = Footprint(
    name="SK9822-EC20",
    description="Worldsemi SK9822-EC20, SPI RGB LED, 2x2mm, SMD2121-6P",
    body_width=2.0,
    body_height=2.0,
    pin1_corner_x=-1.680,
    pin1_corner_y=+0.840,   # Y-negiert
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


def has_pad(fp: Footprint, signal: str) -> bool:
    """True wenn der Footprint ein Pad mit diesem Signalnamen hat."""
    return any(p.signal == signal for p in fp.pads)


FOOTPRINTS = {
    "SK9822-EC20": SK9822_EC20,
}


def footprint_from_data(lcsc_id: str) -> Footprint:
    """
    Footprint dynamisch aus data/{lcsc_id}/footprint.json laden.

    Funktioniert fuer jedes Bauteil, dessen Daten per fetch_component.py
    geladen wurden. Kein Hardcoding erforderlich.

    Signal-Konventionen (normalisiert):
      DI / DO / CI / CO / VDD / GND
    Falls CI/CO fehlen (4-Pad LED ohne CLK) bleiben sie einfach weg.

    Y-Flip: footprint.json speichert bereits korrekte Gerber-Koordinaten
    (Y-Flip wurde in fetch_component.py angewendet).
    """
    import json as _json

    workspace = Path(__file__).parent.parent
    fp_path   = workspace / "data" / lcsc_id / "footprint.json"
    cmp_path  = workspace / "data" / lcsc_id / "component.json"

    if not fp_path.exists():
        raise FileNotFoundError(
            f"Footprint-Daten fehlen: {fp_path}\n"
            f"Bitte zuerst ausführen: python3 src/fetch_component.py {lcsc_id}"
        )

    fp_data  = _json.loads(fp_path.read_text(encoding="utf-8"))
    cmp_data = _json.loads(cmp_path.read_text(encoding="utf-8")) if cmp_path.exists() else {}

    pads_raw = fp_data.get("pads", [])

    # Gehaeuse-Abmessungen aus Pad-Ausdehnung schaetzen
    xs = [abs(p["x"]) + p["width"]  / 2 for p in pads_raw]
    ys = [abs(p["y"]) + p["height"] / 2 for p in pads_raw]
    bw = round(max(xs) * 2, 3) if xs else 2.0
    bh = round(max(ys) * 2, 3) if ys else 2.0

    pads = [
        Pad(
            number=str(p["number"]),
            signal=p.get("signal", ""),
            x=p["x"],
            y=-p["y"],        # Y-Flip: EasyEDA-Screen -> Gerber-Math
            width=p["width"],
            height=p["height"],
        )
        for p in pads_raw
    ]

    name = cmp_data.get("mfr_part", lcsc_id)
    return Footprint(
        name=name,
        description=cmp_data.get("package", ""),
        body_width=bw,
        body_height=bh,
        pads=pads,
    )


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
# Via-Positionen: Midpoint-Schema (Vias zwischen den LED-Reihen)
#
# Neue Strategie: Via liegt AUSSERHALB des Pad-Bereichs, direkt senkrecht
# unter/ueber dem Pad, auf der Y-Hoehe der Stromschiene zwischen zwei Reihen.
#
# via_pos() gibt nur die X-Koordinate (= Pad-X rotiert) zurueck.
# Die Y-Koordinate (Schienen-Y) kommt aus design_rules.bus_y() und wird
# in top_copper.py und bottom_copper.py berechnet.
#
# Hilfsfunktion via_pad_x(): gibt den absoluten X-Wert der Via (= Pad-X nach Rotation).
# ---------------------------------------------------------------------------

def via_pad_x(
    led_x: float, led_y: float, rotation: float, signal: str,
    fp: "Footprint | None" = None,
) -> float:
    """
    Absolute X-Koordinate der Via fuer VDD oder GND.

    Die Via liegt auf derselben X-Koordinate wie das jeweilige Pad
    (direkt senkrecht darueber/darunter).
    """
    lx, ly = _pad_xy(fp, signal)
    rx, _ = rotate_xy(lx, ly, rotation)
    return led_x + rx


def _pad_x(fp: "Footprint | None", signal: str) -> float:
    """X-Offset des Pads im Footprint (oder SK9822-Default)."""
    return _pad_xy(fp, signal)[0]


def _pad_xy(fp: "Footprint | None", signal: str) -> Tuple[float, float]:
    """(x,y)-Offset des Pads im Footprint (oder SK9822-Default)."""
    if fp is not None:
        try:
            pad = get_pad(fp, signal)
            return (pad.x, pad.y)
        except KeyError:
            pass
    default = {"VDD": (PAD_XR, 0.0), "GND": (PAD_XL, 0.0)}
    return default[signal]


def via_pos(
    led_x: float, led_y: float, rotation: float, signal: str,
    pitch: float = 5.0,
    fp: "Footprint | None" = None,
) -> Tuple[float, float]:
    """
    Absolute Position der Power-Via fuer VDD oder GND.

    Via liegt auf gleicher X wie das Pad, Y auf der Stromschiene.
    Position = max(Bus-Mitte, sichere Drill-Distanz vom Pad).
    """
    from design_rules import CLEARANCE, bus_width, VIA_DRILL, VIA_DRILL_CLEAR

    vx = via_pad_x(led_x, led_y, rotation, signal, fp=fp)

    lx, ly = _pad_xy(fp, signal)
    _, pad_ry = rotate_xy(lx, ly, rotation)
    sign = +1 if pad_ry > 0 else -1

    pw = PAD_W
    if fp is not None:
        try:
            pw = get_pad(fp, signal).width
        except KeyError:
            pass

    # Nominale Bus-Mitte
    w = bus_width(pitch)
    nominal = CLEARANCE + w / 2

    # Sichere Mindestdistanz: Drill darf Pad-Kupfer nicht beruehren
    # + 0.15mm extra Abstand (Fertigungstoleranz)
    # + 0.01mm Puffer gegen Floating-Point-Grenzfaelle
    pad_outer = abs(pad_ry) + pw / 2
    safe_min  = pad_outer + VIA_DRILL_CLEAR + VIA_DRILL / 2 + 0.15 + 0.01

    vy = led_y + sign * max(nominal, safe_min)
    return (vx, vy)
