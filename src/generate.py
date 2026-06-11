"""
Haupt-Generator: erzeugt alle Fertigungsdateien und packt sie als ZIP.

Aufruf:
    python3 generate.py [--cols N] [--rows M] [--pitch P] [--output FILE.zip]

Standardwerte: 3x2 Matrix, 5mm Pitch, Ausgabe in output/matrix.zip

Komponentendaten (BOM/CPL):
    Werden aus data/{JLCPCB_PART}/component.json geladen.
    Falls noch nicht vorhanden:
        python3 fetch_component.py C2909059
"""

import argparse
import io
import zipfile
import os
import configparser
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
from component_data import load_component
from bom import build_bom
from cpl import build_cpl


# JLCPCB-Dateinamen-Konvention
FILE_NAMES = {
    "gtl": "matrix-F_Cu.gtl",       # Top Copper
    "gbl": "matrix-B_Cu.gbl",       # Bottom Copper
    "gts": "matrix-F_Mask.gts",     # Top Solder Mask
    "gbs": "matrix-B_Mask.gbs",     # Bottom Solder Mask
    "gko": "matrix-Edge_Cuts.gko",  # Board Outline
    "drl": "matrix.drl",            # Drill
    "bom": "BOM.csv",               # Bill of Materials
    "cpl": "CPL.csv",               # Component Placement List
}

# JLCPCB-Teilenummern der verwendeten Bauteile
JLCPCB_PARTS = {
    "SK9822-EC20": "C2909059",
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

    # Komponentendaten laden (BOM/CPL)
    lcsc_id = JLCPCB_PARTS[fp_name]
    try:
        component = load_component(lcsc_id)
        has_component_data = True
    except FileNotFoundError as exc:
        print(f"[WARNUNG] {exc}")
        print(f"[WARNUNG] BOM und CPL werden NICHT erzeugt.")
        has_component_data = False

    print(f"Matrix:  {cols} x {rows}  ({cols * rows} LEDs)")
    print(f"Pitch:   {pitch} mm")
    print(f"Board:   {w:.1f} x {h:.1f} mm")
    if has_component_data:
        print(f"Bauteil: {component.mfr_part}  [{component.jlcpcb_part}]  {component.package}")
    print(f"Output:  {output}")
    print()

    files = {
        FILE_NAMES["gtl"]: build_top_copper(leds, fp, pitch=pitch),
        FILE_NAMES["gbl"]: build_bottom_copper(leds, fp, pitch=pitch),
        FILE_NAMES["gts"]: build_top_soldermask(leds, fp, pitch=pitch),
        FILE_NAMES["gbs"]: build_bottom_soldermask(leds, fp, pitch=pitch),
        FILE_NAMES["gko"]: build_board_outline(cols, rows, pitch, margin),
        FILE_NAMES["drl"]: build_drill(leds, fp, pitch=pitch),
    }

    if has_component_data:
        files[FILE_NAMES["bom"]] = build_bom(leds, component)
        files[FILE_NAMES["cpl"]] = build_cpl(leds)

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
    parser.add_argument("--config", type=str, default=None,
                        help="Pfad zu einer .cfg-Datei (z.B. cfg/SK9822_5x4.cfg)")
    parser.add_argument("--cols",   type=int,   default=None)
    parser.add_argument("--rows",   type=int,   default=None)
    parser.add_argument("--pitch",  type=float, default=None)
    parser.add_argument("--margin", type=float, default=None)
    parser.add_argument("--output", type=str,   default=None)
    parser.add_argument("--led",    type=str,   default=None)
    args = parser.parse_args()

    # Defaults
    cfg_cols   = 3
    cfg_rows   = 2
    cfg_pitch  = 5.0
    cfg_margin = 2.0
    cfg_output = "output/matrix.zip"
    cfg_led    = "SK9822-EC20"

    # Config-Datei laden
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            # relativ zum Workspace-Root (parent von src/)
            cfg_path = Path(__file__).parent.parent / args.config
        ini = configparser.ConfigParser()
        ini.read(cfg_path)

        cfg_cols   = ini.getint("matrix", "cols",   fallback=cfg_cols)
        cfg_rows   = ini.getint("matrix", "rows",   fallback=cfg_rows)
        cfg_pitch  = ini.getfloat("matrix", "pitch", fallback=cfg_pitch)
        cfg_margin = ini.getfloat("matrix", "margin", fallback=cfg_margin)

        # LED-Typ aus JLCPCB-Teilenummer ableiten
        lcsc = ini.get("led", "jlcpcb_part", fallback=None)
        if lcsc:
            rev = {v: k for k, v in JLCPCB_PARTS.items()}
            if lcsc in rev:
                cfg_led = rev[lcsc]
            else:
                print(f"[FEHLER] JLCPCB-Teil '{lcsc}' nicht in JLCPCB_PARTS bekannt.")
                raise SystemExit(1)

        # Output-Name = Config-Dateiname ohne Extension
        cfg_output = f"output/{cfg_path.stem}.zip"

    # CLI-Argumente ueberschreiben Config
    cols   = args.cols   if args.cols   is not None else cfg_cols
    rows   = args.rows   if args.rows   is not None else cfg_rows
    pitch  = args.pitch  if args.pitch  is not None else cfg_pitch
    margin = args.margin if args.margin is not None else cfg_margin
    output = args.output if args.output is not None else cfg_output
    led    = args.led    if args.led    is not None else cfg_led

    generate(
        cols=cols,
        rows=rows,
        pitch=pitch,
        margin=margin,
        output=output,
        fp_name=led,
    )
