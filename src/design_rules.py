"""
Design Rules fuer den LED-Matrix-Generator.

Ziel: JLCPCB ECONOMY-Standard (ohne Aufpreis!), NICHT die Extremwerte
der Capability-Tabelle (feinere Features = Kostenfaktor).
  Quelle: https://jlcpcb.com/capabilities/Capabilities (abgerufen 2026-10-16)
  + JLCPCB-Blog (DFM): "trace width/spacing >= 5/5 mil and via drills
    >= 0.3mm to prevent fine-feature fees"
  - Bohrung: min 0.3 mm (Standard ohne Aufpreis; kleiner = Aufpreis)
  - Via Standard: 0.3 mm Bohrung / 0.6 mm Pad  (JLCPCB-Blog: "healthy
    annular ring and reliable plating") -> Ring 0.15 mm
  - Trace/Spacing: 5/5 mil = 0.127 mm (wir arbeiten konservativ mit 0.15)
  - SMD-Pad zu Pad (versch. Netze): 0.15 mm; Min-SMD-Pad 0.25x0.25
  - Via-Loch zu Trace: 0.20 mm; Via-Loch zu Loch: 0.20 mm
  - Kupfer zu gefraester Boardkante: >= 0.20 mm
  - Castellations: Bohrung >=0.5, Loch-zu-Loch >=0.5, Abstand zu anderer
    Kante >=1.0 mm, Board >=10x10, Dicke >=0.6.
    ABER: Economic-PCBA unterstuetzt KEINE Castellations/Goldfingers/
    Edge-Plating (https://jlcpcb.com/de/capabilities/pcb-assembly-
    capabilities, abgerufen 2026-10-16) -> alle Anschlüsse als bohrungs-
    lose SMD-Kantenpads: DIN/DOUT-Eckenpads + GND/VCC-Kantenpads.
  - Economic-PCBA: einseitige Bestueckung ok, Board 10x10..470x500,
    Panel <=250x250, Dicke 0.8-1.6mm, Min-Gehaeuse 0402, Menge 2-50.
  - Silkscreen: Linie >=0.15 mm, Texthoehe >=1.0 mm, Pad-Abstand 0.15 mm
  - Soldermask-Bruecke (gruen, 1oz): >=0.10 mm

Grundregel im Generator (bewusst ueber Economy-Minima):
    Mindestabstand zwischen zwei Leitungen (Pad-Kante zu Pad-Kante) = 0.30 mm.
    Das entspricht CLEARANCE = 0.15 mm pro Seite einer Leitung.
    Ueberall wo Clearance eingehalten wird gilt: 2 * 0.15 = 0.30 mm Abstand.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Grund-Designregel
# ---------------------------------------------------------------------------

CLEARANCE   = 0.15   # mm: Randabstand je Seite einer Leitung
MIN_SPACING = 0.30   # mm: = 2 * CLEARANCE, Mindestabstand Leitungskante zu Leitungskante

# Kupfer -> gefraeste Boardkante: JLCPCB verlangt >= 0.20 mm (nicht 0.15!).
# Gilt fuer alle Cu-Flaechen, die nicht selbst Teil eines Halblochs sind.
EDGE_CLEAR  = 0.20   # mm


# ---------------------------------------------------------------------------
# Leiterbahnbreiten
# ---------------------------------------------------------------------------

TRACE_DATA  = 0.15   # mm: Datensignale (DI/DO)
TRACE_POWER = 0.30   # mm: Stromschienen-Hauptlinien (Vorderseite)
TRACE_DET   = 0.15   # mm: Detour-Umfahrungen der Schienen (duenn, wie Daten)


# ---------------------------------------------------------------------------
# Via
# ---------------------------------------------------------------------------

VIA_PAD_D        = 0.60   # mm: Via-Pad-Durchmesser
VIA_DRILL        = 0.30   # mm: Via-Bohrungs-Durchmesser
VIA_DRILL_CLEAR  = 0.25   # mm: JLCPCB Mindestabstand Drill-Kante zu fremdem Pad-Kupfer


# ---------------------------------------------------------------------------
# Stromschienen (Bottom-Layer)
# ---------------------------------------------------------------------------

BUS_GAP     = 0.30   # mm: Luecke zwischen VDD- und GND-Schiene (= MIN_SPACING)


# ---------------------------------------------------------------------------
# Busbar (vertikale Sammelschiene, Bottom-Layer, links/rechts vom Board)
#
# IPC-2221A externe Lage: I = 0.048 * dT^0.44 * A^0.725
#   A in mil², t = 1oz = 1.378 mil, dT = 10°C Standard
#
# Layout Busbar-Zone (von links nach rechts):
#   [CLEARANCE][GND w][BUS_GAP][VDD w][CLEARANCE][MIN_SPACING zur Matrix]
#
# GND aussen (Rand), VDD innen (naeher an Matrix).
# ---------------------------------------------------------------------------

BUSBAR_MIN_WIDTH = 5.0   # mm: minimale Breite einer einzelnen Sammelschiene


def busbar_width_mm(
    n_leds: int,
    ma_per_led: float = 15.0,
    copper_oz: float = 1.0,
    delta_t: float = 10.0,
) -> float:
    """
    Dynamische Busbar-Breite nach IPC-2221A (externe Lage), Minimum 5 mm.

    Beispiele (1oz, 10 Grad Anstieg):
      176 LEDs @  15mA =  2.64A -> 1.15mm -> 5.0mm (Minimum)
      352 LEDs @  15mA =  5.28A -> 2.98mm -> 5.0mm
      704 LEDs @  15mA = 10.56A -> 7.76mm -> 7.8mm (automatisch breiter)
    """
    k = 0.048
    t_mil = copper_oz * 1.378
    total = n_leds * ma_per_led / 1000.0
    if total < 1e-6:
        return BUSBAR_MIN_WIDTH
    area_mil2 = (total / (k * delta_t ** 0.44)) ** (1.0 / 0.725)
    w_mm = (area_mil2 / t_mil) * 0.0254
    return max(BUSBAR_MIN_WIDTH, w_mm)


def busbar_min_left_margin(
    n_leds: int,
    ma_per_led: float = 15.0,
    copper_oz: float = 1.0,
) -> float:
    """
    Minimales effektives linkes Margin fuer die Busbar-Zone.

    Gesamtbreite: CLEARANCE + GND_w + BUS_GAP + VDD_w + CLEARANCE + MIN_SPACING
    """
    w = busbar_width_mm(n_leds, ma_per_led, copper_oz)
    return 2 * CLEARANCE + w + BUS_GAP + w + MIN_SPACING


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
