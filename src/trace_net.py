"""
Netz-Tracer: Flood-Fill auf Top+Bottom Copper, um VCC/GND zu visualisieren.

Verbundenes Kupfer wird rot/blau eingefaerbt — Kurzschluesse sind
sofort sichtbar.

Aufruf:
    python3 src/trace_net.py output/SK9822_5x4.zip --dpmm 100
"""

from __future__ import annotations
import argparse
import io
import json
import math
import re
import zipfile
from collections import deque
from pathlib import Path

from pygerber.gerberx3.api.v2 import (
    GerberFile, FileTypeEnum, ColorScheme,
    ImageFormatEnum, PixelFormatEnum,
)
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _find(names: list[str], *keywords: str) -> str | None:
    for kw in keywords:
        for n in names:
            if kw.lower() in n.lower():
                return n
    return None


def _load_footprint_pads(zp: Path) -> list[dict]:
    """Alle Pads aus data/*/footprint.json auf der Platte (Y-geflippt)."""
    workspace = Path(__file__).parent.parent
    data_dir = workspace / "data"
    if data_dir.is_dir():
        for lcsc_dir in sorted(data_dir.iterdir()):
            fp_path = lcsc_dir / "footprint.json"
            if fp_path.exists():
                fp = json.loads(fp_path.read_text(encoding="utf-8"))
                return [
                    {"signal": p["signal"], "x": p["x"], "y": -p["y"],
                     "w": p["width"], "h": p["height"]}
                    for p in fp["pads"]
                ]
    return []


def _parse_cpl(zf: zipfile.ZipFile) -> list[tuple[float, float, float]]:
    """CPL CSV -> [(x_mm, y_mm, rotation_deg), ...]."""
    cpl_name = _find(zf.namelist(), "CPL", ".csv")
    if not cpl_name:
        return []
    text = zf.read(cpl_name).decode("utf-8", errors="replace")
    leds: list[tuple[float, float, float]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("Designator"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            leds.append((
                float(parts[1].replace("mm", "")),
                float(parts[2].replace("mm", "")),
                float(parts[4]),
            ))
        except (ValueError, IndexError):
            continue
    return leds


# ---------------------------------------------------------------------------
# flood-fill
# ---------------------------------------------------------------------------

def _flood_fill(mask: Image.Image, seed: tuple[int, int],
                max_pix: int = 20_000_000) -> Image.Image:
    """BFS flood-fill on '1'-mode mask, returns '1'-mode connected component."""
    w, h = mask.size
    visited = Image.new("1", (w, h), 0)
    pm = mask.load()
    pv = visited.load()
    sx, sy = seed
    if sx < 0 or sx >= w or sy < 0 or sy >= h or not pm[sx, sy]:
        return visited
    q: deque[tuple[int, int]] = deque()
    q.append((sx, sy))
    pv[sx, sy] = 1
    cnt = 0
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        pass  # done in loop below
    while q and cnt < max_pix:
        x, y = q.popleft()
        cnt += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                if pm[nx, ny] and not pv[nx, ny]:
                    pv[nx, ny] = 1
                    q.append((nx, ny))
    return visited


# ---------------------------------------------------------------------------
# copper mask builder (GTL + GBL union)
# ---------------------------------------------------------------------------

def _copper_mask(
    zf: zipfile.ZipFile, dpmm: int,
) -> tuple[Image.Image, float, float]:
    """
    Build a binary '1'-mode mask from GTL+GBL (union) + via bridges.
    Returns (mask, global_min_x_mm, global_min_y_mm).
    """
    layers = [
        ("matrix-F_Cu.gtl", FileTypeEnum.COPPER),
        ("matrix-B_Cu.gbl", FileTypeEnum.COPPER),
    ]
    imgs: list[tuple[Image.Image, float, float]] = []
    for fname, ftype in layers:
        data = zf.read(fname)
        if data is None:
            continue
        gf = GerberFile.from_str(data.decode("utf-8"), ftype)
        pf = gf.parse()
        info = pf.get_info()
        buf = io.BytesIO()
        pf.render_raster(buf, dpmm=dpmm, color_scheme=ColorScheme.COPPER_ALPHA,
                         image_format=ImageFormatEnum.PNG,
                         pixel_format=PixelFormatEnum.RGBA)
        buf.seek(0)
        img = Image.open(buf).copy()
        imgs.append((img, float(info.min_x_mm), float(info.min_y_mm)))

    # Parse drill holes for via bridges
    drill_holes: list[tuple[float, float]] = []
    for name in zf.namelist():
        if name.endswith(".drl"):
            drl = zf.read(name).decode("utf-8", errors="replace")
            for m in re.finditer(r"X\+(\d{6})Y\+(\d{6})", drl):
                drill_holes.append((float(m.group(1)) / 1000.0,
                                    float(m.group(2)) / 1000.0))
            break

    # global bbox
    gmin_x = min(mx for _, mx, _ in imgs)
    gmin_y = min(my for _, _, my in imgs)
    gmax_x = max(mx + (img.size[0] - 1) / dpmm
                 for img, mx, _ in imgs)
    gmax_y = max(my + (img.size[1] - 1) / dpmm
                 for img, _, my in imgs)

    import math as _math
    gmin_x = _math.floor(gmin_x * dpmm) / dpmm
    gmin_y = _math.floor(gmin_y * dpmm) / dpmm

    cw = int((gmax_x - gmin_x) * dpmm)
    ch = int((gmax_y - gmin_y) * dpmm)
    mask = Image.new("1", (cw, ch), 0)
    pm = mask.load()

    # Paste GTL + GBL copper
    for img, ix, iy in imgs:
        ox = round((ix - gmin_x) * dpmm)
        oy = round((iy - gmin_y) * dpmm)
        px = img.load()
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                if px[x, y][3] > 127:
                    tx, ty = x + ox, y + oy
                    if 0 <= tx < cw and 0 <= ty < ch:
                        pm[tx, ty] = 1

    # Via bridges: fill a small circle at each drill position
    # This connects GTL copper to GBL copper at via locations
    via_r = max(2, int(0.30 * dpmm))  # 0.30mm radius (drill + pad overlap)
    for hx, hy in drill_holes:
        cx = round((hx - gmin_x) * dpmm)
        cy = round((hy - gmin_y) * dpmm)
        rr = via_r * via_r
        for dy in range(-via_r, via_r + 1):
            for dx in range(-via_r, via_r + 1):
                if dx * dx + dy * dy <= rr:
                    tx, ty = cx + dx, cy + dy
                    if 0 <= tx < cw and 0 <= ty < ch:
                        pm[tx, ty] = 1

    return mask, gmin_x, gmin_y


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def trace_nets(
    zip_path: str,
    dpmm: int = 100,
    nets: list[str] | None = None,
) -> tuple[Image.Image | None, Image.Image | None]:
    """
    Erzeugt zwei PNGs:  *_vcc.png  und  *_gnd.png

    Returns: (vcc_img, gnd_img) or (None, None)
    """
    if nets is None:
        nets = ["VCC", "GND"]
    zp = Path(zip_path)
    fp_pads = _load_footprint_pads(zp)
    with zipfile.ZipFile(zp) as zf:
        leds    = _parse_cpl(zf)
        mask, gmin_x, gmin_y = _copper_mask(zf, dpmm)
        gko_data = None
        for n in zf.namelist():
            if ".gko" in n or "Edge" in n:
                gko_data = zf.read(n)
                break

    if not fp_pads or not leds:
        print("Keine Footprint- oder CPL-Daten gefunden.")
        return None, None

    w, h = mask.size
    print(f"Maske: {w}x{h} px  (dpmm={dpmm})")

    results: list[Image.Image | None] = []
    default_colours: list[tuple[int, int, int, int]] = [
        (255, 50, 50, 250),   # VCC = rot
        (50, 150, 255, 250),  # GND = blau
    ]
    default_signals = {"VCC": "VDD", "GND": "GND"}

    for net_name, colour in zip(nets, default_colours):
        signal = default_signals.get(net_name, net_name)
        target = next((p for p in fp_pads if p["signal"] == signal), None)
        if not target:
            print(f"Kein Pad fuer Signal '{signal}' gefunden.")
            results.append(None)
            continue

        tx, ty = target["x"], target["y"]

        # seed from first LED
        seeds: list[tuple[int, int]] = []
        for cx, cy, rot in leds[:1]:
            rad = math.radians(rot)
            c, s = math.cos(rad), math.sin(rad)
            px = cx + (tx * c - ty * s)
            py = cy + (tx * s + ty * c)
            sx = round((px - gmin_x) * dpmm)
            sy = round((py - gmin_y) * dpmm)
            if 0 <= sx < w and 0 <= sy < h:
                seeds.append((sx, sy))

        if not seeds:
            print(f"Keine Seed-Punkte fuer {net_name}.")
            results.append(None)
            continue

        print(f"{net_name}: Seed ({px:.2f},{py:.2f}) px=({seeds[0][0]},{seeds[0][1]})  "
              f"Flood-fill ...")

        filled = _flood_fill(mask, seeds[0])
        pf = filled.load()
        pm = mask.load()

        # build coloured output
        result = Image.new("RGBA", (w, h), (15, 25, 15, 255))
        for y in range(h):
            for x in range(w):
                if pf[x, y]:
                    result.putpixel((x, y), colour)
                elif pm[x, y]:
                    result.putpixel((x, y), (50, 140, 50, 255))

        # board outline overlay
        if gko_data:
            try:
                gf2 = GerberFile.from_str(gko_data.decode("utf-8"), FileTypeEnum.EDGE)
                pf2 = gf2.parse()
                buf2 = io.BytesIO()
                pf2.render_raster(buf2, dpmm=dpmm,
                                  color_scheme=ColorScheme.SOLDER_MASK_ALPHA,
                                  image_format=ImageFormatEnum.PNG,
                                  pixel_format=PixelFormatEnum.RGBA)
                buf2.seek(0)
                outline = Image.open(buf2).copy().convert("RGBA")
                if outline.size == result.size:
                    result = Image.alpha_composite(result, outline)
            except Exception:
                pass

        # seed marker
        draw = ImageDraw.Draw(result)
        for sx, sy in seeds:
            draw.ellipse((sx - 5, sy - 5, sx + 5, sy + 5),
                         fill=(255, 255, 0, 255))

        out_name = zp.parent / f"{zp.stem}_{net_name.lower()}.png"
        result.convert("RGB").save(str(out_name))
        print(f"  -> {out_name}  ({result.size[0]} x {result.size[1]} px)")
        results.append(result)

    return (results[0] if len(results) > 0 else None,
            results[1] if len(results) > 1 else None)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Netz-Tracer fuer LED-Matrix")
    parser.add_argument("zip", help="Pfad zum ZIP")
    parser.add_argument("--dpmm", type=int, default=100,
                        help="Pixel pro mm (Standard: 100)")
    parser.add_argument("--net", type=str, default="ALL",
                        help="Netz: VCC, GND, ALL (default)")
    args = parser.parse_args()

    if args.net.upper() == "ALL":
        trace_nets(args.zip, dpmm=args.dpmm, nets=["VCC", "GND"])
    else:
        trace_nets(args.zip, dpmm=args.dpmm, nets=[args.net.upper()])
