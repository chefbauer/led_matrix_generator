"""
Haupt-Generator: erzeugt alle Fertigungsdateien und packt sie als ZIP.

Aufruf:
    python3 generate.py [--cols N] [--rows M] [--pitch P] [--output FILE.zip]

Standardwerte: 3x2 Matrix, 5mm Pitch, Ausgabe in output/matrix.zip
"""

import argparse
import io
import zipfile
import os
from pathlib import Path

from footprint import SK9822_EC20, FOOTPRINTS
from matrix import generate_matrix, board_size
from top_copper import build_top_copper
from bottom_copper import build_bottom_copper
from other_layers import (
    build_top_soldermask,
    build_bottom_soldermask,
    build_board_outline,
    build_drill,
)


# JLCPCB-Dateinamen-Konvention
FILE_NAMES = {
    "gtl": "matrix-F_Cu.gtl",       # Top Copper
    "gbl": "matrix-B_Cu.gbl",       # Bottom Copper
    "gts": "matrix-F_Mask.gts",     # Top Solder Mask
    "gbs": "matrix-B_Mask.gbs",     # Bottom Solder Mask
    "gko": "matrix-Edge_Cuts.gko",  # Board Outline
    "drl": "matrix.drl",            # Drill
}


def generate(
    cols: int = 3,
    rows: int = 2,
    pitch: float = 5.0,
    margin: float = 2.0,
    output: str = "output/matrix.zip",
    fp_name: str = "SK9822-EC20",
):
    fp = FOOTPRINTS[fp_name]
    leds = generate_matrix(cols, rows, pitch, fp, margin)
    w, h = board_size(cols, rows, pitch, margin, fp)

    print(f"Matrix:  {cols} x {rows}  ({cols * rows} LEDs)")
    print(f"Pitch:   {pitch} mm")
    print(f"Board:   {w:.1f} x {h:.1f} mm")
    print(f"Output:  {output}")
    print()

    files = {
        FILE_NAMES["gtl"]: build_top_copper(leds, fp),
        FILE_NAMES["gbl"]: build_bottom_copper(leds, fp),
        FILE_NAMES["gts"]: build_top_soldermask(leds, fp),
        FILE_NAMES["gbs"]: build_bottom_soldermask(leds, fp),
        FILE_NAMES["gko"]: build_board_outline(cols, rows, pitch, margin),
        FILE_NAMES["drl"]: build_drill(leds, fp),
    }

    # ZIP erzeugen
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
            print(f"  + {filename:40s}  {len(content):6d} Bytes")

    print()
    print(f"ZIP geschrieben: {out_path}  ({out_path.stat().st_size} Bytes)")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LED-Matrix Gerber Generator")
    parser.add_argument("--cols",   type=int,   default=3,              help="Anzahl Spalten")
    parser.add_argument("--rows",   type=int,   default=2,              help="Anzahl Zeilen")
    parser.add_argument("--pitch",  type=float, default=5.0,            help="Pitch in mm")
    parser.add_argument("--margin", type=float, default=2.0,            help="Rand in mm")
    parser.add_argument("--output", type=str,   default="output/matrix.zip", help="Ausgabedatei")
    parser.add_argument("--led",    type=str,   default="SK9822-EC20",  help="LED-Typ")
    args = parser.parse_args()

    generate(
        cols=args.cols,
        rows=args.rows,
        pitch=args.pitch,
        margin=args.margin,
        output=args.output,
        fp_name=args.led,
    )
