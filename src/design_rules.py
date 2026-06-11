"""
Design Rules fuer den LED-Matrix-Generator.

Grundregel:
    Mindestabstand zwischen zwei Leitungen (Pad-Kante zu Pad-Kante) = 0.30 mm.
    Das entspricht CLEARANCE = 0.15 mm pro Seite einer Leitung.
    Ueberall wo Clearance eingehalten wird gilt: 2 * 0.15 = 0.30 mm Abstand.

Stromschienen-Geometrie (zwischen zwei LED-Reihen):
    Freier Raum von LED-Mitte bis Mittelpunkt zwischen zwei Reihen = pitch / 2.
    Dort liegen VDD und GND je als horizontale Schiene auf der Bottom-Lage.

    Aufteilung (von LED-Mitte aus, Richtung Mittelpunkt):
       [CLEARANCE][GND-Bus][BUS_GAP][VDD-Bus][CLEARANCE] = pitch/2
    => Bus-Breite = (pitch/2 - 2*CLEARANCE - BUS_GAP) / 2

    Beispiel pitch=5mm:
       Bus-Breite = (2.5 - 0.15 - 0.15 - 0.30) / 2 = 0.95 mm

    VDD nahe am Rand (weiter von LED-Mitte entfernt), GND innen (naeher an LED-Mitte).
    (Konvention: VDD = Schiene mit hoeherem Y-Abstand bei positiver Richtung)

Via-Geometrie:
    Via-Pad-Ø = 0.50 mm, Drill = 0.30 mm.
    Via sitzt direkt unter/ueber dem Pad (gleiche X wie Pad).
    Via-Y liegt auf der Schienen-Mittellinie der jeweiligen Schiene.
    Top-Layer-Stichleitung: senkrechte Linie vom Pad bis zur Via-Mitte.

Daten-Traces:
    Breite = 0.15 mm, Clearance = 0.15 mm (=> 0.30 mm Abstand zu anderen Traces)

Top-Layer Power-Stichleitung:
    Breite = 0.20 mm, Clearance = 0.15 mm
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Grund-Designregel
# ---------------------------------------------------------------------------

CLEARANCE   = 0.15   # mm: Randabstand je Seite einer Leitung
MIN_SPACING = 0.30   # mm: = 2 * CLEARANCE, Mindestabstand Leitungskante zu Leitungskante


# ---------------------------------------------------------------------------
# Leiterbahnbreiten
# ---------------------------------------------------------------------------

TRACE_DATA  = 0.15   # mm: Datensignale (DI/DO, CI/CO)
TRACE_POWER = 0.20   # mm: Power-Stichleitung Top-Layer (Via -> Pad)


# ---------------------------------------------------------------------------
# Via
# ---------------------------------------------------------------------------

VIA_PAD_D   = 0.50   # mm: Via-Pad-Durchmesser
VIA_DRILL   = 0.30   # mm: Via-Bohrungs-Durchmesser


# ---------------------------------------------------------------------------
# Stromschienen (Bottom-Layer)
# ---------------------------------------------------------------------------

BUS_GAP     = 0.30   # mm: Luecke zwischen VDD- und GND-Schiene (= MIN_SPACING)


def bus_width(pitch: float, body_height: float = 2.0) -> float:
    """
    Breite einer einzelnen Stromschiene.

    Jede LED-Reihe hat einen VDD-Bus AUF EINER SEITE und einen GND-Bus
    AUF DER ANDEREN SEITE. Jeder Bus bekommt eine halbe Pitch-Zone:

        [CLEARANCE][Bus][CLEARANCE] = pitch/2
        Bus-Breite = pitch/2 - 2*CLEARANCE

    Beispiel pitch=5mm:
        Bus-Breite = 2.5 - 2*0.15 = 2.20 mm

    Gap zwischen VDD- und GND-Bus einer Reihe:
        Gap = 2*(CLEARANCE + w/2) = 2*1.25 = 2.5mm (= Mitte-Mitte-Abstand)
        Freier Spalt: 2.5 - 2.2 = 0.30 mm = MIN_SPACING ✓
    """
    return pitch / 2 - 2 * CLEARANCE


def bus_centers(pitch: float, body_height: float = 2.0) -> tuple[float, float]:
    """
    Y-Offsets der Schienen-Mitten relativ zur Mittellinie zwischen zwei Reihen.

    GND innen (naeher an Mittellinie), VDD aussen.

    Returns
    -------
    (vdd_offset, gnd_offset) ab Mittellinie.
    """
    w = bus_width(pitch)
    gnd_center = w / 2 + BUS_GAP / 2
    vdd_center = w + BUS_GAP + w / 2
    # symmetrisch zur Mittellinie: GND innen, VDD aussen - aber Schienen
    # liegen BEIDE auf derselben Seite (zwischen zwei Reihen)
    # GND naeher an Mittellinie, VDD weiter weg
    gnd_off = BUS_GAP / 2 + w / 2
    vdd_off = BUS_GAP / 2 + w + BUS_GAP / 2 + w / 2
    # Vereinfacht: beide symmetrisch um Mittellinie
    # [CLEARANCE][GND][BUS_GAP][VDD][CLEARANCE] = pitch
    # Mitte GND: CLEARANCE + w/2
    # Mitte VDD: CLEARANCE + w + BUS_GAP + w/2
    # relativ zur Mittellinie (pitch/2):
    half = pitch / 2
    gnd_abs = CLEARANCE + w / 2          # ab Linker Kante
    vdd_abs = CLEARANCE + w + BUS_GAP + w / 2
    return (vdd_abs - half, gnd_abs - half)   # relativ zur Mittellinie


def bus_y(led_y: float, pitch: float, side: str, body_height: float = 2.0) -> tuple[float, float]:
    """
    Absolute Y-Koordinaten der VDD- und GND-Schienen-Mittelpunkte.

    Schienen liegen zwischen zwei Reihen, zentriert auf der Mittellinie
    zwischen den LED-Mittelpunkten (pitch/2). Bottom hat keine Bauteile,
    daher volle Pitch-Breite nutzbar.

    Parameters
    ----------
    led_y       : float  LED-Mittelpunkt Y
    pitch       : float
    side        : 'below' | 'above'
    body_height : float  (ungenutzt, nur fuer API-Kompatibilitaet)

    Returns
    -------
    (vdd_y, gnd_y)
    """
    midline = led_y + (pitch / 2 if side == "below" else -pitch / 2)
    sign = 1 if side == "below" else -1
    vdd_off, gnd_off = bus_centers(pitch)
    return (midline + sign * vdd_off, midline + sign * gnd_off)
