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

from footprint import footprint_from_data
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
from silkscreen import build_top_silkscreen
from render_preview import render_zip


# JLCPCB-Dateinamen-Konvention
FILE_NAMES = {
    "gto": "matrix-F_SilkS.gto",       # Top Silkscreen
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
# Nicht mehr benoetigt – Footprints werden direkt aus data/{lcsc_id}/ geladen.


def generate(
    cols: int = 3,
    rows: int = 2,
    pitch: float = 5.0,
    margin: float = 2.0,
    output: str = "output/matrix.zip",
    lcsc_id: str = "C2909059",
    busbar: int = 0,
    led_current_ma: float = 15.0,
    copper_oz: float = 1.0,
    preview: bool = True,
    preview_dpmm: int = 60,
):
    import design_rules as DR
    fp = footprint_from_data(lcsc_id)

    # Busbar: extra Breite links, margin bleibt separat rundherum
    n_leds = cols * rows
    if busbar > 0:
        busbar_w = DR.busbar_width_mm(n_leds, led_current_ma, copper_oz)
        x_offset = busbar_w + 2 * DR.CLEARANCE + DR.BUS_GAP  # Gesamtbreite busbar-Zone
    else:
        busbar_w = 0.0
        x_offset = 0.0

    leds = generate_matrix(cols, rows, pitch, fp, margin, x_offset=x_offset)
    w, h = board_size(cols, rows, pitch, margin, fp, extra_left=x_offset)

    # Komponentendaten laden (BOM/CPL)
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
    if busbar > 0:
        print(f"Busbar:  {busbar} (links)  Breite={busbar_w:.2f}mm  x_offset={x_offset:.2f}mm")
    print(f"Output:  {output}")
    print()

    files = {
        FILE_NAMES["gto"]: build_top_silkscreen(leds, fp, pitch=pitch, board_width=w,
                                                busbar=busbar, x_offset=x_offset),
        FILE_NAMES["gtl"]: build_top_copper(leds, fp, pitch=pitch,
                                            busbar=busbar, x_offset=x_offset),
        FILE_NAMES["gbl"]: build_bottom_copper(leds, fp, pitch=pitch,
                                               busbar=busbar, led_current_ma=led_current_ma,
                                               copper_oz=copper_oz, board_height=h,
                                               x_offset=x_offset),
        FILE_NAMES["gts"]: build_top_soldermask(leds, fp, pitch=pitch,
                                                busbar=busbar, x_offset=x_offset),
        FILE_NAMES["gbs"]: build_bottom_soldermask(leds, fp, pitch=pitch,
                                                   busbar=busbar, led_current_ma=led_current_ma,
                                                   copper_oz=copper_oz, board_height=h,
                                                   x_offset=x_offset),
        FILE_NAMES["gko"]: build_board_outline(cols, rows, pitch, margin, extra_left=x_offset),
        FILE_NAMES["drl"]: build_drill(leds, fp, pitch=pitch, busbar=busbar, x_offset=x_offset),
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

    # Automatische PNG-Vorschau
    if preview:
        print()
        try:
            render_zip(str(out_path), dpmm=preview_dpmm)
        except Exception as e:
            print(f"[WARNUNG] Preview fehlgeschlagen: {e}")

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
    parser.add_argument("--lcsc",   type=str,   default=None,
                        help="JLCPCB-Teilenummer, z.B. C2909059")
    parser.add_argument("--no-preview", action="store_true",
                        help="Keine PNG-Vorschau rendern")
    parser.add_argument("--dpmm",   type=int,   default=60,
                        help="Pixel pro mm fuer Vorschau (Standard: 60)")
    args = parser.parse_args()

    # Defaults
    cfg_cols   = 3
    cfg_rows   = 2
    cfg_pitch  = 5.0
    cfg_margin = 2.0
    cfg_output = "output/matrix.zip"
    cfg_lcsc         = "C2909059"
    cfg_busbar       = 0
    cfg_led_current  = 15.0
    cfg_copper_oz    = 1.0

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

        # Busbar
        cfg_busbar        = ini.getint("matrix",   "busbar",         fallback=0)
        cfg_led_current   = ini.getfloat("matrix", "led_current_ma", fallback=15.0)
        cfg_copper_oz     = ini.getfloat("matrix", "copper_oz",      fallback=1.0)

        # LCSC-ID direkt aus Config lesen
        cfg_lcsc = ini.get("led", "jlcpcb_part", fallback=cfg_lcsc)

        # Output-Name = Config-Dateiname ohne Extension
        cfg_output = f"output/{cfg_path.stem}.zip"

    # CLI-Argumente ueberschreiben Config
    cols   = args.cols   if args.cols   is not None else cfg_cols
    rows   = args.rows   if args.rows   is not None else cfg_rows
    pitch  = args.pitch  if args.pitch  is not None else cfg_pitch
    margin = args.margin if args.margin is not None else cfg_margin
    output = args.output if args.output is not None else cfg_output
    lcsc   = args.lcsc   if args.lcsc   is not None else cfg_lcsc

    generate(
        cols=cols,
        rows=rows,
        pitch=pitch,
        margin=margin,
        output=output,
        lcsc_id=lcsc,
        busbar=cfg_busbar,
        led_current_ma=cfg_led_current,
        copper_oz=cfg_copper_oz,
        preview=not args.no_preview,
        preview_dpmm=args.dpmm,
    )
