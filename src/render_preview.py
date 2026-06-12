"""
Gerber-Preview-Renderer.

Erzeugt PNG-Vorschaubilder (Vorderseite + Rückseite) aus einem ZIP-Paket
mit den generierten Gerber-Dateien.

Aufruf:
    python3 src/render_preview.py output/SK9822_5x4.zip
    python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 40

Ausgabe: output/<name>_front.png  und  output/<name>_back.png
"""

from __future__ import annotations
import argparse
import io
import zipfile
from pathlib import Path

from pygerber.gerberx3.api.v2 import (
    GerberFile, FileTypeEnum, ColorScheme,
    ImageFormatEnum, PixelFormatEnum,
)
from PIL import Image


def _find(names: list[str], *keywords: str) -> str | None:
    for kw in keywords:
        for n in names:
            if kw.lower() in n.lower():
                return n
    return None


def _render_layer(
    source: bytes,
    file_type: FileTypeEnum,
    color_scheme: ColorScheme,
    dpmm: int,
) -> Image.Image | None:
    """Einzelnen Gerber-Layer als RGBA-PIL-Bild rendern."""
    try:
        gf  = GerberFile.from_str(source.decode("utf-8"), file_type)
        pf  = gf.parse()
        buf = io.BytesIO()
        pf.render_raster(
            buf,
            color_scheme=color_scheme,
            dpmm=dpmm,
            image_format=ImageFormatEnum.PNG,
            pixel_format=PixelFormatEnum.RGBA,
        )
        buf.seek(0)
        return Image.open(buf).copy()   # .copy() schließt den BytesIO-Buffer aus
    except Exception as e:
        print(f"    [übersprungen] {file_type.value}: {e}")
        return None


def _composite(
    layers: list[tuple[bytes | None, FileTypeEnum, ColorScheme]],
    bg_rgba: tuple,
    dpmm: int,
) -> Image.Image | None:
    """Mehrere Layer-PNGs alpha-composite zusammensetzen."""
    result: Image.Image | None = None
    for data, ftype, scheme in layers:
        if data is None:
            continue
        layer_img = _render_layer(data, ftype, scheme, dpmm)
        if layer_img is None:
            continue
        if result is None:
            result = Image.new("RGBA", layer_img.size, bg_rgba)
        if layer_img.size != result.size:
            layer_img = layer_img.resize(result.size, Image.LANCZOS)
        result = Image.alpha_composite(result, layer_img)
    return result


def render_zip(zip_path: str, dpmm: int = 20, out_dir: str | None = None) -> tuple[str, str]:
    """
    Rendert Vorder- und Rückseite als PNG.
    Returns: (front_path, back_path)
    """
    zp  = Path(zip_path)
    out = Path(out_dir) if out_dir else zp.parent

    with zipfile.ZipFile(zp) as zf:
        names = zf.namelist()

        def read(*keys) -> bytes | None:
            n = _find(names, *keys)
            return zf.read(n) if n else None

        gtl = read("F_Cu",     ".gtl")
        gbl = read("B_Cu",     ".gbl")
        gts = read("F_Mask",   ".gts")
        gbs = read("B_Mask",   ".gbs")
        gto = read("F_SilkS",  "SilkS", ".gto")
        gko = read("Edge_Cuts", ".gko")

    stem       = zp.stem
    front_path = out / f"{stem}_front.png"
    back_path  = out / f"{stem}_back.png"

    print(f"Rendere Vorderseite  →  {front_path.name}  (dpmm={dpmm})")
    front = _composite([
        (gko, FileTypeEnum.EDGE,   ColorScheme.SOLDER_MASK_ALPHA),
        (gts, FileTypeEnum.MASK,   ColorScheme.SOLDER_MASK_ALPHA),
        (gtl, FileTypeEnum.COPPER, ColorScheme.COPPER_ALPHA),
        (gto, FileTypeEnum.LEGEND, ColorScheme.SILK_ALPHA),
    ], bg_rgba=(25, 90, 25, 255), dpmm=dpmm)

    if front:
        front.convert("RGB").save(str(front_path))
        print(f"  → {front_path}  ({front.size[0]}×{front.size[1]} px)")
    else:
        print("  [FEHLER] Kein Layer gerendert")

    print(f"Rendere Rückseite    →  {back_path.name}  (dpmm={dpmm})")
    back = _composite([
        (gko, FileTypeEnum.EDGE,   ColorScheme.SOLDER_MASK_ALPHA),
        (gbs, FileTypeEnum.MASK,   ColorScheme.SOLDER_MASK_ALPHA),
        (gbl, FileTypeEnum.COPPER, ColorScheme.COPPER_ALPHA),
    ], bg_rgba=(20, 75, 20, 255), dpmm=dpmm)

    if back:
        back.convert("RGB").save(str(back_path))
        print(f"  → {back_path}  ({back.size[0]}×{back.size[1]} px)")
    else:
        print("  [FEHLER] Kein Layer gerendert")

    return str(front_path), str(back_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerber ZIP → PNG Vorschau")
    parser.add_argument("zip",    help="Pfad zum ZIP (z.B. output/SK9822_5x4.zip)")
    parser.add_argument("--dpmm", type=int, default=20,
                        help="Pixel pro mm (Standard: 20 ≈ 508 dpi)")
    parser.add_argument("--out",  type=str, default=None,
                        help="Ausgabeverzeichnis (Standard: gleicher Ordner wie ZIP)")
    args = parser.parse_args()

    render_zip(args.zip, dpmm=args.dpmm, out_dir=args.out)

