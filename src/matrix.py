"""
Matrixgenerator: berechnet absolute LED-Positionen und Netz-Zuordnungen.

Schema (Anreih-Modul, PLAN.md / tools/layout_schema.py):
  Board exakt cols*pitch x rows*pitch, LED-Mitten im Raster pitch/2.
  Datenkette = HORIZONTALE Serpentine, Start oben-links (L1):
    visuelle Reihe 0 (oben):  Spalte 0 -> cols-1
    visuelle Reihe 1:         Spalte cols-1 -> 0   usw.
  Ende bei gerader Zeilenzahl unten-links (DOUT-Ecke).

  Grunddrehung 180 deg (DI oben-links), visuelle Reihen 1,3,5... relativ
  -90 deg (= absolut 90 deg): dadurch liegen in jeder Luecke die
  Power-Pads gleicher Netze (VDD<->VDD bzw. GND<->GND) einander gegenueber,
  und je Luecke reicht EINE horizontale Front-Schiene.

Koordinatensystem: Ursprung links-UNTEN, Y nach oben (Gerber-Math),
row 0 = unterste Reihe. Alle Masse in mm.
"""

from dataclasses import dataclass, field
from typing import List, Dict
from footprint import Footprint, SK9822_EC20

BASE_ROT = 180.0   # Grunddrehung: DI oben-links


@dataclass
class LedInstance:
    """Eine platzierte LED in der Datenkette."""
    index: int           # Laufender Index in der Datenkette (0-basiert)
    ref: str             # Bestuckungsreferenz, z.B. "D1"
    col: int             # Spalte (0-basiert, 0 = links)
    row: int             # Zeile (0-basiert, 0 = UNTEN)
    vrow: int            # visuelle Reihe (0 = OBEN)
    x: float             # Absolute X-Position des Bauteilmittelpunkts in mm
    y: float             # Absolute Y-Position des Bauteilmittelpunkts in mm
    rotation: float = 0.0
    nets: Dict[str, str] = field(default_factory=dict)


def row_rotation(vrow: int) -> float:
    """Absolute Bestueckungsrotation einer visuellen Reihe.
    gerade Reihen: 180 (DI oben-links), ungerade: relativ -90 -> 90."""
    return BASE_ROT if vrow % 2 == 0 else BASE_ROT - 90.0


def generate_matrix(
    cols: int,
    rows: int,
    pitch: float,
    footprint: Footprint = SK9822_EC20,
    margin: float = 0.0,     # deprecated, ignoriert
    x_offset: float = 0.0,   # deprecated, ignoriert
) -> List[LedInstance]:
    """
    Erzeugt die vollstaendige Liste aller LED-Instanzen (Ketten-Reihenfolge).
    Rand = pitch/2, Board = cols*pitch x rows*pitch (nahtloses Anreihen).
    Kettenreihenfolge: horizontale Serpentine ab oben-links.
    """
    leds: List[LedInstance] = []

    # Kettenreihenfolge: visuelle Reihe 0 (oben) von links nach rechts
    chain: List[tuple] = []
    for vrow in range(rows):
        if vrow % 2 == 0:
            cols_iter = range(cols)                  # links -> rechts
        else:
            cols_iter = range(cols - 1, -1, -1)      # rechts -> links
        for col in cols_iter:
            chain.append((col, vrow))

    for idx, (col, vrow) in enumerate(chain):
        row = rows - 1 - vrow                        # physische Reihe (0=unten)
        x = pitch / 2.0 + col * pitch
        y = pitch / 2.0 + row * pitch
        ref = f"D{idx + 1}"

        nets = {
            "VDD": "+5V",
            "GND": "GND",
            "DI":  f"DAT_{idx + 1}",
            "DO":  f"DAT_{idx + 2}",
        }

        leds.append(LedInstance(
            index=idx,
            ref=ref,
            col=col,
            row=row,
            vrow=vrow,
            x=x,
            y=y,
            rotation=row_rotation(vrow),
            nets=nets,
        ))

    return leds


def board_size(
    cols: int,
    rows: int,
    pitch: float,
    margin: float = 0.0,
    footprint: Footprint = SK9822_EC20,
    extra_left: float = 0.0,
) -> tuple:
    """Board-Abmessungen: exakt cols*pitch x rows*pitch (Anreih-Raster)."""
    return cols * pitch, rows * pitch


def chain_end_is_bottom_left(rows: int) -> bool:
    """True wenn die Kette bei rows Zeilen unten-links endet (DOUT-Ecke)."""
    return rows % 2 == 0


if __name__ == "__main__":
    leds = generate_matrix(cols=8, rows=8, pitch=3.0)
    w, h = board_size(8, 8, 3.0)
    print(f"Board: {w:.1f} x {h:.1f} mm")
    first, last = leds[0], leds[-1]
    print(f"Kette: Start {first.ref} ({first.col},{first.vrow}) @({first.x},{first.y}) rot={first.rotation}"
          f"  Ende {last.ref} ({last.col},{last.vrow}) @({last.x},{last.y}) rot={last.rotation}")
    assert first.x == 1.5 and first.y == h - 1.5, "Start muss oben-links sein"
    assert first.rotation == 180.0, "Grunddrehung 180"
    assert leds[8].rotation == 90.0, "visuelle Reihe 1: relativ -90"
    assert chain_end_is_bottom_left(8) and last.x == 1.5 and last.y == 1.5, \
        "8x8 muss unten-links enden"
    print("OK: Start oben-links (rot180), Reihe1 rot90, Ende unten-links")
