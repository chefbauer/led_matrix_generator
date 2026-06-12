"""
Gerber-Preview-Renderer.

Erzeugt hochaufloesende PNG-Vorschaubilder (Vorderseite + Rueckseite)
aus einem ZIP-Paket mit den generierten Gerber-Dateien.

Aufruf:
    python3 src/render_preview.py output/SK9822_5x4.zip
    python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 100
    python3 src/render_preview.py output/SK9822_5x4.zip --min-size 3000
    python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 40 --scale 2

Ausgabe: output/<name>_front.png  und  output/<name>_back.png
"""

from __future__ import annotations
import argparse
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pygerber.gerberx3.api.v2 import (
    GerberFile, GerberFileInfo, FileTypeEnum, ColorScheme,
    ImageFormatEnum, PixelFormatEnum,
)
from PIL import Image


# -- data types --------------------------------------------------------------

@dataclass
class LayerSpec:
    data: bytes | None
    ftype: FileTypeEnum
    scheme: ColorScheme


# -- helpers -----------------------------------------------------------------

def _find(names: list[str], *keywords: str) -> str | None:
    for kw in keywords:
        for n in names:
            if kw.lower() in n.lower():
                return n
    return None


def _board_extent_mm(
    gko: bytes | None, gtl: bytes | None, gbl: bytes | None,
) -> tuple[float, float]:
    def extent(data: bytes) -> tuple[float, float] | None:
        xs, ys = [], []
        for m in re.finditer(rb"X(-?\d+)Y(-?\d+)", data):
            xs.append(int(m.group(1)) / 1_000_000)
            ys.append(int(m.group(2)) / 1_000_000)
        if not xs:
            return None
        return max(xs) - min(xs), max(ys) - min(ys)
    for data in (gko, gtl, gbl):
        if data:
            e = extent(data)
            if e:
                return e
    return 100.0, 100.0


def _calc_dpmm(
    dpmm: int, scale: float, min_size: int | None,
    board_w_mm: float, board_h_mm: float,
) -> int:
    effective = int(dpmm * scale)
    if min_size:
        shorter_mm = min(board_w_mm, board_h_mm)
        needed = int(min_size / shorter_mm)
        effective = max(effective, needed)
    return max(effective, 1)


def _add_solid_border(
    img: Image.Image, border_mm: float, dpmm: int,
    colour: tuple[int, int, int, int] = (0, 0, 0, 255),
) -> None:
    px = max(1, int(border_mm * dpmm))
    w, h = img.size
    for x in range(w):
        for y in range(px):
            img.putpixel((x, y), colour)
            img.putpixel((x, h - 1 - y), colour)
    for y in range(px, h - px):
        for x in range(px):
            img.putpixel((x, y), colour)
            img.putpixel((w - 1 - x, y), colour)


# -- rendering ---------------------------------------------------------------

def _parse_excellon_drill(
    source: bytes,
) -> list[tuple[float, list[tuple[float, float]]]] | None:
    """Parse Excellon drill file, return [(dia_mm, [(x,y),...]), ...] per tool."""
    try:
        text = source.decode("utf-8", errors="replace")
    except Exception:
        return None

    # find tool definitions: T1C0.300, T2C1.000, ...
    tools: dict[str, float] = {}
    for m in re.finditer(r"T(\d+)C(\d+\.\d+)", text):
        tools[m.group(1)] = float(m.group(2))
    if not tools:
        return None

    # split by tool sections: each "Tn" starts a new block of holes
    # We'll find all Tn blocks and collect holes after each
    result: list[tuple[float, list[tuple[float, float]]]] = []
    # Strategy: split on "T\d" boundaries, then parse holes in each section
    sections = re.split(r"(?=T\d+\n)", text)
    for sec in sections:
        m_tool = re.match(r"T(\d+)", sec)
        if not m_tool:
            continue
        tool_num = m_tool.group(1)
        dia = tools.get(tool_num)
        if dia is None:
            continue
        holes: list[tuple[float, float]] = []
        for m in re.finditer(r"X\+(\d{6})Y\+(\d{6})", sec):
            holes.append((float(m.group(1)) / 1000.0,
                          float(m.group(2)) / 1000.0))
        if holes:
            result.append((dia, holes))
    return result if result else None


def _draw_drill_on_image(
    img: Image.Image,
    layer_info: GerberFileInfo,
    drill_data: bytes,
    dpmm: int,
    colour: tuple[int, int, int, int] = (0, 0, 0, 255),
) -> None:
    """Draw drill holes directly onto a pygerber-rendered image (in-place).

    Uses the SAME coordinate space as pygerber: Gerber (x,y) → image
    pixel (round((x - info.min_x)*dpmm), round((y - info.min_y)*dpmm)).
    This guarantees pixel-perfect alignment with all features in the image.
    """
    parsed = _parse_excellon_drill(drill_data)
    if not parsed:
        return
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    origin_x = float(layer_info.min_x_mm)
    max_y = float(layer_info.max_y_mm)
    for dia, holes in parsed:
        radius_px = max(1, int(dia / 2 * dpmm))
        print(f"    {len(holes)} Bohrungen,  O {dia:.2f} mm")
        for hx, hy in holes:
            cx = round((hx - origin_x) * dpmm)
            cy = round((max_y - hy) * dpmm)
            draw.ellipse(
                (cx - radius_px, cy - radius_px,
                 cx + radius_px, cy + radius_px),
                fill=colour,
            )


# -- pin-1 markers -----------------------------------------------------------

def _detect_pin1_offset(gtl: bytes | None, gko: bytes | None) -> tuple[float, float]:
    """Return (do_x, do_y) — local DO pad offset before rotation."""
    import json as _json
    workspace = Path(__file__).parent.parent
    data_dir = workspace / "data"
    if data_dir.is_dir():
        for lcsc_dir in sorted(data_dir.iterdir()):
            fp_path = lcsc_dir / "footprint.json"
            if fp_path.exists():
                try:
                    fp = _json.loads(fp_path.read_text(encoding="utf-8"))
                    for p in fp.get("pads", []):
                        if p.get("signal") == "DO":
                            return (p["x"], -p["y"])
                except Exception:
                    continue
    return (-0.707, 0.800)  # SK9822-EC20 default


def _parse_cpl(csv_data: bytes) -> list[tuple[float, float, float]] | None:
    """Parse CPL CSV, return [(x_mm, y_mm, rotation_deg), ...] for each LED."""
    try:
        text = csv_data.decode("utf-8", errors="replace")
    except Exception:
        return None
    leds: list[tuple[float, float, float]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("Designator"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            x = float(parts[1].replace("mm", ""))
            y = float(parts[2].replace("mm", ""))
            r = float(parts[4])
            leds.append((x, y, r))
        except (ValueError, IndexError):
            continue
    return leds if leds else None


def _draw_pin1_markers(
    img: Image.Image,
    cpl_data: bytes | None,
    global_min_x: float,
    global_min_y: float,
    dpmm: int,
    do_x: float = -0.707,
    do_y: float = +0.800,
    colour: tuple[int, int, int, int] = (255, 0, 0, 255),
) -> None:
    """Draw a small red dot at each LED's pin-1 (DO) pad position."""
    if not cpl_data:
        return
    leds = _parse_cpl(cpl_data)
    if not leds:
        return
    import math
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    r = max(2, int(0.21 * dpmm))
    for cx, cy, rot in leds:
        rad = math.radians(rot)
        c, s = math.cos(rad), math.sin(rad)
        px = cx + (do_x * c - do_y * s)
        py = cy + (do_x * s + do_y * c)
        ix = round((px - global_min_x) * dpmm)
        iy = img.size[1] - 1 - round((py - global_min_y) * dpmm)
        draw.ellipse((ix - r, iy - r, ix + r, iy + r), fill=colour)


# -- rendering ---------------------------------------------------------------

def _parse_and_render(
    source: bytes, ftype: FileTypeEnum, scheme: ColorScheme, dpmm: int,
) -> tuple[Image.Image | None, GerberFileInfo | None]:
    try:
        gf = GerberFile.from_str(source.decode("utf-8"), ftype)
        pf = gf.parse()
        info = pf.get_info()
        buf = io.BytesIO()
        pf.render_raster(buf, color_scheme=scheme, dpmm=dpmm,
                         image_format=ImageFormatEnum.PNG,
                         pixel_format=PixelFormatEnum.RGBA)
        buf.seek(0)
        return Image.open(buf).copy(), info
    except Exception as e:
        print(f"    [uebersprungen] {ftype.value}: {e}")
        return None, None


def _composite(
    layers: list[LayerSpec],
    bg_rgba: tuple[int, int, int, int],
    dpmm: int,
    drill_data: bytes | None = None,
    drill_colour: tuple[int, int, int, int] = (0, 0, 0, 255),
    drill_anchor_ftype: FileTypeEnum = FileTypeEnum.COPPER,
) -> Image.Image | None:
    """Alpha-composite layers with drill holes on the anchor layer.

    Drill holes are drawn ON the anchor layer's pygerber-rendered image
    using that layer's own coordinate system — zero mismatch.
    """
    # -- 1) pre-parse to get global bounding box -----------------------------
    infos: list[GerberFileInfo] = []
    active: list[LayerSpec] = []
    for spec in layers:
        if spec.data is None:
            continue
        try:
            gf = GerberFile.from_str(spec.data.decode("utf-8"), spec.ftype)
            pf = gf.parse()
            infos.append(pf.get_info())
            active.append(spec)
        except Exception as e:
            print(f"    [uebersprungen (parse)] {spec.ftype.value}: {e}")

    if not active:
        return None

    global_min_x = float(min(i.min_x_mm for i in infos))
    global_min_y = float(min(i.min_y_mm for i in infos))
    global_max_x = float(max(i.max_x_mm for i in infos))
    global_max_y = float(max(i.max_y_mm for i in infos))

    # Snap origin to integer pixel boundary
    import math as _math
    global_min_x = _math.floor(global_min_x * dpmm) / dpmm
    global_min_y = _math.floor(global_min_y * dpmm) / dpmm

    canvas_w = int((global_max_x - global_min_x) * dpmm)
    canvas_h = int((global_max_y - global_min_y) * dpmm)
    result = Image.new("RGBA", (canvas_w, canvas_h), bg_rgba)

    # -- 2) render + paste each layer ----------------------------------------
    for spec, info in zip(active, infos):
        img, _ = _parse_and_render(spec.data, spec.ftype, spec.scheme, dpmm)
        if img is None:
            continue

        # Draw drill holes ON the anchor layer image before pasting
        if drill_data and spec.ftype == drill_anchor_ftype:
            _draw_drill_on_image(img, info, drill_data, dpmm,
                                 colour=drill_colour)

        ox = round((float(info.min_x_mm) - global_min_x) * dpmm)
        oy = round((float(info.min_y_mm) - global_min_y) * dpmm)
        result.paste(img, (ox, oy), img)

    return result

    return result


# -- public API --------------------------------------------------------------

def render_zip(
    zip_path: str,
    dpmm: int = 60,
    scale: float = 1.0,
    min_size: int | None = None,
    out_dir: str | None = None,
    border_mm: float = 0.0,
) -> tuple[str, str]:
    zp  = Path(zip_path)
    out = Path(out_dir) if out_dir else zp.parent

    with zipfile.ZipFile(zp) as zf:
        names = zf.namelist()
        def read(*keys) -> bytes | None:
            n = _find(names, *keys)
            return zf.read(n) if n else None

        gtl = read("F_Cu",      ".gtl")
        gbl = read("B_Cu",      ".gbl")
        gts = read("F_Mask",    ".gts")
        gbs = read("B_Mask",    ".gbs")
        gto = read("F_SilkS",   "SilkS", ".gto")
        gko = read("Edge_Cuts", ".gko")
        drl = read(".drl")
        cpl = read("CPL",       ".csv")

    bw, bh = _board_extent_mm(gko, gtl, gbl)
    effective_dpmm = _calc_dpmm(dpmm, scale, min_size, bw, bh)

    # global bbox for pin1 marker coordinate mapping
    ginfo = (GerberFile.from_str(gko.decode("utf-8"), FileTypeEnum.EDGE)
             .parse().get_info() if gko else
             GerberFile.from_str(gtl.decode("utf-8"), FileTypeEnum.COPPER)
             .parse().get_info() if gtl else None)
    gmin_x = float(ginfo.min_x_mm) if ginfo else 0.0
    gmin_y = float(ginfo.min_y_mm) if ginfo else 0.0
    # snap to pixel grid (same as _composite)
    import math as _math2
    gmin_x = _math2.floor(gmin_x * effective_dpmm) / effective_dpmm
    gmin_y = _math2.floor(gmin_y * effective_dpmm) / effective_dpmm

    # auto-detect DO pad position from Gerber or footprint data
    do_x, do_y = _detect_pin1_offset(gtl, gko)

    stem       = zp.stem
    front_path = out / f"{stem}_front.png"
    back_path  = out / f"{stem}_back.png"
    dpi_approx = int(effective_dpmm * 25.4)

    print(f"Board:  {bw:.1f} x {bh:.1f} mm")
    print(f"dpmm:   {effective_dpmm}  (~ {dpi_approx} dpi)")
    print(f"Pixels: ~ {int(bw*effective_dpmm)} x {int(bh*effective_dpmm)}\n")

    # -- front (Edge, Mask, Copper, Silk) — drill on copper (GTL) ----------
    print(f"Rendere Vorderseite  ->  {front_path.name}")
    front = _composite([
        LayerSpec(gko, FileTypeEnum.EDGE,   ColorScheme.SOLDER_MASK_ALPHA),
        LayerSpec(gts, FileTypeEnum.MASK,   ColorScheme.SOLDER_MASK_ALPHA),
        LayerSpec(gtl, FileTypeEnum.COPPER, ColorScheme.COPPER_ALPHA),
        LayerSpec(gto, FileTypeEnum.LEGEND, ColorScheme.SILK_ALPHA),
    ], bg_rgba=(25, 90, 25, 255), dpmm=effective_dpmm, drill_data=drl)

    if front:
        _draw_pin1_markers(front, cpl, gmin_x, gmin_y, effective_dpmm,
                           do_x=do_x, do_y=do_y)
        if border_mm > 0:
            _add_solid_border(front, border_mm, effective_dpmm)
        final = front.convert("RGB")
        final.save(str(front_path), dpi=(dpi_approx, dpi_approx), optimize=True)
        print(f"  -> {front_path}  ({final.size[0]} x {final.size[1]} px)")
    else:
        print("  [FEHLER] Kein Layer gerendert")

    # -- back (Edge, Mask, Copper) — drill on copper (GBL) -----------------
    print(f"Rendere Rueckseite    ->  {back_path.name}")
    back = _composite([
        LayerSpec(gko, FileTypeEnum.EDGE,   ColorScheme.SOLDER_MASK_ALPHA),
        LayerSpec(gbs, FileTypeEnum.MASK,   ColorScheme.SOLDER_MASK_ALPHA),
        LayerSpec(gbl, FileTypeEnum.COPPER, ColorScheme.COPPER_ALPHA),
    ], bg_rgba=(20, 75, 20, 255), dpmm=effective_dpmm, drill_data=drl)

    if back:
        _draw_pin1_markers(back, cpl, gmin_x, gmin_y, effective_dpmm,
                           do_x=do_x, do_y=do_y)
        if border_mm > 0:
            _add_solid_border(back, border_mm, effective_dpmm)
        final = back.convert("RGB")
        final.save(str(back_path), dpi=(dpi_approx, dpi_approx), optimize=True)
        print(f"  -> {back_path}  ({final.size[0]} x {final.size[1]} px)")
    else:
        print("  [FEHLER] Kein Layer gerendert")

    return str(front_path), str(back_path)


# -- CLI --------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gerber ZIP -> hochaufloesende PNG Vorschau",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python3 src/render_preview.py output/SK9822_5x4.zip
  python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 100
  python3 src/render_preview.py output/SK9822_5x4.zip --min-size 4000
  python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 40 --scale 2.5
  python3 src/render_preview.py output/SK9822_5x4.zip --border 1.0
        """)
    parser.add_argument("zip",
        help="Pfad zum ZIP (z.B. output/SK9822_5x4.zip)")
    parser.add_argument("--dpmm", type=int, default=60,
        help="Pixel pro mm (Standard: 60 ~ 1524 dpi)")
    parser.add_argument("--scale", type=float, default=1.0,
        help="Multiplikator auf dpmm (z.B. --scale 2)")
    parser.add_argument("--min-size", type=int, default=None, metavar="PX",
        help="Kuerzere Bildseite auf min. N Pixel skalieren")
    parser.add_argument("--out", type=str, default=None,
        help="Ausgabeverzeichnis (Standard: gleicher Ordner wie ZIP)")
    parser.add_argument("--border", type=float, default=0.0,
        help="Schwarzer Rand um das Board in mm")
    args = parser.parse_args()

    render_zip(args.zip, dpmm=args.dpmm, scale=args.scale,
               min_size=args.min_size, out_dir=args.out, border_mm=args.border)
