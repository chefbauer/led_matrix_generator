"""
Haupt-Generator: erzeugt alle Fertigungsdateien und packt sie als ZIP.

Architektur v2 (PLAN.md): nahtlose Matrix (Board = cols*pitch x rows*pitch),
Stromschienen vertikal auf B.Cu, Reihen-Schienen horizontal auf F.Cu,
Datenkette auf B.Cu, DIN/DOUT als SMD-Kantenpads unten.

Aufruf:
    python generate.py --cols 8 --rows 8 [--pitch 3.0] [--lcsc C41413180]
    python generate.py --config cfg/XL-1615_8x8.cfg

Ohne --pitch wird der kleinste machbare Pitch gewaehlt (feasibility).
"""

import argparse
import zipfile
import configparser
from pathlib import Path

from footprint import footprint_from_data
from matrix import generate_matrix, board_size
from data_chain import compute_data_chain
from power_grid import compute_power_grid
import layers_v2
from component_data import load_component
from bom import build_bom
from cpl import build_cpl
from render_preview import render_zip

# JLCPCB-Dateinamen-Konvention
FILE_NAMES = {
    "gto": "matrix-F_SilkS.gto",
    "gtl": "matrix-F_Cu.gtl",
    "gbl": "matrix-B_Cu.gbl",
    "gts": "matrix-F_Mask.gts",
    "gbs": "matrix-B_Mask.gbs",
    "gbo": "matrix-B_SilkS.gbo",
    "gko": "matrix-Edge_Cuts.gko",
    "drl": "matrix.drl",
    "bom": "BOM.csv",
    "cpl": "CPL.csv",
}


def generate(
    cols: int = 8,
    rows: int = 8,
    pitch: float | None = None,
    output: str = "output/matrix.zip",
    lcsc_id: str = "C41413180",
    preview: bool = True,
    preview_dpmm: int = 60,
):
    from feasibility import check_matrix, min_feasible_pitch
    fp = footprint_from_data(lcsc_id)

    # --- Machbarkeitspruefung VOR allem anderen -------------------------
    if pitch is None:
        pitch = min_feasible_pitch(cols, rows, fp)
        if pitch is None:
            raise SystemExit("Kein machbarer Pitch bis 10mm gefunden.")
        print(f"Pitch nicht gesetzt -> kleinster machbarer: {pitch} mm")
    ok, reasons = check_matrix(cols, rows, pitch, fp)
    if not ok:
        print("MACHBARKEITSPRUEFE: NICHT MACHBAR")
        for r in reasons:
            print(f"  - {r}")
        mp = min_feasible_pitch(cols, rows, fp)
        raise SystemExit(
            f"Abbruch: pitch {pitch}mm erfuellt die Design-Regeln nicht. "
            f"Kleinster machbarer pitch: {mp}mm")
    print("Machbarkeitspruefung: OK (alle Randbedingungen erfuellt)")

    W, H = board_size(cols, rows, pitch)
    leds = generate_matrix(cols, rows, pitch, fp)
    pg = compute_power_grid(leds, fp, W, H, pitch)
    dc = compute_data_chain(leds, fp, W, H, pitch)

    # Komponentendaten (BOM/CPL)
    component = None
    try:
        component = load_component(lcsc_id)
        has_component_data = True
    except FileNotFoundError as exc:
        print(f"[WARNUNG] {exc}")
        print("[WARNUNG] BOM und CPL werden NICHT erzeugt.")
        has_component_data = False

    print(f"Matrix:  {cols} x {rows}  ({cols * rows} LEDs)")
    print(f"Pitch:   {pitch} mm")
    print(f"Board:   {W:.1f} x {H:.1f} mm (nahtlos anreihbar)")
    if has_component_data:
        print(f"Bauteil: {component.mfr_part}  [{component.jlcpcb_part}]  "
              f"{component.package}")
    print(f"Output:  {output}")
    print()

    files = {
        FILE_NAMES["gto"]: layers_v2.build_silkscreen_top(pg),
        FILE_NAMES["gtl"]: layers_v2.build_fcu(leds, fp, pg, dc),
        FILE_NAMES["gbl"]: layers_v2.build_bcu(leds, fp, pg, dc),
        FILE_NAMES["gts"]: layers_v2.build_mask_top(leds, fp, pg, dc),
        FILE_NAMES["gbs"]: layers_v2.build_mask_bottom(pg, dc),
        FILE_NAMES["gko"]: layers_v2.build_outline(W, H),
        FILE_NAMES["gbo"]: layers_v2.build_silkscreen_bottom(pg, W, H),
        FILE_NAMES["drl"]: layers_v2.build_drill(dc, pg),
    }
    if has_component_data:
        files[FILE_NAMES["bom"]] = build_bom(leds, component)
        files[FILE_NAMES["cpl"]] = build_cpl(leds)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
            print(f"  + {filename:40s}  {len(content):6d} Bytes")

    print()
    print(f"ZIP geschrieben: {out_path}  ({out_path.stat().st_size} Bytes)")

    if preview:
        print()
        try:
            render_zip(str(out_path), dpmm=preview_dpmm)
        except Exception as e:
            print(f"[WARNUNG] Preview fehlgeschlagen: {e}")

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LED-Matrix Gerber Generator v2")
    parser.add_argument("--config", type=str, default=None,
                        help="Pfad zu einer .cfg-Datei (z.B. cfg/XL-1615_8x8.cfg)")
    parser.add_argument("--cols",   type=int,   default=None)
    parser.add_argument("--rows",   type=int,   default=None)
    parser.add_argument("--pitch",  type=float, default=None)
    parser.add_argument("--output", type=str,   default=None)
    parser.add_argument("--lcsc",   type=str,   default=None,
                        help="JLCPCB-Teilenummer, z.B. C41413180")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--dpmm", type=int, default=60)
    args = parser.parse_args()

    cfg_cols, cfg_rows = 8, 8
    cfg_pitch = None
    cfg_output = "output/matrix.zip"
    cfg_lcsc = "C41413180"

    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            cfg_path = Path(__file__).parent.parent / args.config
        ini = configparser.ConfigParser()
        with open(cfg_path, encoding="utf-8-sig") as f:
            ini.read_file(f)
        cfg_cols = ini.getint("matrix", "cols", fallback=cfg_cols)
        cfg_rows = ini.getint("matrix", "rows", fallback=cfg_rows)
        if ini.has_option("matrix", "pitch"):
            cfg_pitch = ini.getfloat("matrix", "pitch")
        cfg_lcsc = ini.get("led", "jlcpcb_part", fallback=cfg_lcsc)
        cfg_output = f"output/{cfg_path.stem}.zip"

    cols = args.cols if args.cols is not None else cfg_cols
    rows = args.rows if args.rows is not None else cfg_rows
    pitch = args.pitch if args.pitch is not None else cfg_pitch
    output = args.output if args.output is not None else cfg_output
    lcsc = args.lcsc if args.lcsc is not None else cfg_lcsc

    generate(
        cols=cols, rows=rows, pitch=pitch,
        output=output, lcsc_id=lcsc,
        preview=not args.no_preview, preview_dpmm=args.dpmm,
    )
