"""
Matrixgenerator: berechnet absolute LED-Positionen und Netz-Zuordnungen.

Serpentinenmuster:
  Zeile 0: links -> rechts  (x steigt)
  Zeile 1: rechts -> links  (x faellt)
  Zeile 2: links -> rechts
  usw.

Koordinatensystem: Ursprung links-oben, Y nach unten, alle Masse in mm.
"""

from dataclasses import dataclass, field
from typing import List, Dict
from footprint import Footprint, SK9822_EC20


@dataclass
class LedInstance:
    """Eine platzierte LED in der Matrix."""
    index: int           # Laufender Index in der Datenkette (0-basiert)
    ref: str             # Bestuckungsreferenz, z.B. "D1"
    col: int             # Spalte (0-basiert)
    row: int             # Zeile (0-basiert)
    x: float             # Absolute X-Position des Bauteilmittelpunkts in mm
    y: float             # Absolute Y-Position des Bauteilmittelpunkts in mm
    nets: Dict[str, str] = field(default_factory=dict)
    # nets: {"VDD": "+5V", "GND": "GND", "DI": "DAT_1", "DO": "DAT_2", ...}


def _effective_margin(margin: float, pitch: float) -> float:
    """
    Berechnet den tatsaechlich verwendeten Rand.

    margin=0  ->  pitch / 2
      Das platziert die Board-Kante genau auf halber Pitchdistanz zur LED-Mitte,
      d.h. bei 5mm Pitch liegt die Kante 2.5mm vom LED-Zentrum entfernt.
    """
    if margin == 0.0:
        return pitch / 2.0
    return margin


def generate_matrix(
    cols: int,
    rows: int,
    pitch: float,
    footprint: Footprint = SK9822_EC20,
    margin: float = 2.0,
) -> List[LedInstance]:
    """
    Erzeugt die vollstaendige Liste aller LED-Instanzen fuer eine cols x rows Matrix.

    Args:
        cols:      Anzahl Spalten
        rows:      Anzahl Zeilen
        pitch:     Abstand Mittelpunkt zu Mittelpunkt in mm
        footprint: Footprint-Objekt
        margin:    Rand von Board-Kante zu LED-Mittelpunkt in mm.
                   0 = pitch/2 (Board-Kante auf halber Pitchdistanz zur LED-Mitte)

    Returns:
        Liste von LedInstance, sortiert nach Ketten-Index
    """
    leds: List[LedInstance] = []
    eff_margin = _effective_margin(margin, pitch)

    # Serpentinen-Reihenfolge aufbauen: Liste von (col, row) in Ketten-Reihenfolge
    chain: List[tuple] = []
    for row in range(rows):
        if row % 2 == 0:
            cols_iter = range(cols)          # links -> rechts
        else:
            cols_iter = range(cols - 1, -1, -1)  # rechts -> links
        for col in cols_iter:
            chain.append((col, row))

    # LED-Instanzen mit Koordinaten und Netzen aufbauen
    for idx, (col, row) in enumerate(chain):
        x = eff_margin + col * pitch
        y = eff_margin + row * pitch
        ref = f"D{idx + 1}"

        nets = {
            "VDD": "+5V",
            "GND": "GND",
            "DI":  f"DAT_{idx + 1}",
            "DO":  f"DAT_{idx + 2}",
            "CI":  f"CLK_{idx + 1}",
            "CO":  f"CLK_{idx + 2}",
        }

        leds.append(LedInstance(
            index=idx,
            ref=ref,
            col=col,
            row=row,
            x=x,
            y=y,
            nets=nets,
        ))

    return leds


def board_size(
    cols: int,
    rows: int,
    pitch: float,
    margin: float = 2.0,
    footprint: Footprint = SK9822_EC20,
) -> tuple:
    """Berechnet die Board-Abmessungen in mm. margin=0 -> pitch/2 als Rand."""
    eff = _effective_margin(margin, pitch)
    width  = 2 * eff + (cols - 1) * pitch
    height = 2 * eff + (rows - 1) * pitch
    return width, height


if __name__ == "__main__":
    # Schnelltest: 3x2 Prototyp-Matrix
    leds = generate_matrix(cols=3, rows=2, pitch=5.0)
    w, h = board_size(3, 2, 5.0)
    print(f"Board: {w:.1f} x {h:.1f} mm")
    print()
    for led in leds:
        print(f"  {led.ref:4s}  idx={led.index}  ({led.col},{led.row})  "
              f"pos=({led.x:.1f},{led.y:.1f})  "
              f"DI={led.nets['DI']}  DO={led.nets['DO']}  "
              f"CI={led.nets['CI']}  CO={led.nets['CO']}")
