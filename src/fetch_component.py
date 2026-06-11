"""
EasyEDA/JLCPCB Komponentendaten-Fetcher

Laedt Bauteil-Metadaten direkt von der EasyEDA-API (kein Login noetig)
und speichert sie unter:

    data/{JLCPCB_PART}/component.json   -- normalisierte Metadaten
    data/{JLCPCB_PART}/footprint.json   -- Pad-Geometrie aus Package-Daten
    data/{JLCPCB_PART}/raw.json         -- vollstaendige API-Rohdaten

Verwendung als Script:
    python3 fetch_component.py C2909059
    python3 fetch_component.py C2909059 --force   # Cache ignorieren

Verwendung als Modul:
    from fetch_component import fetch_component
    info = fetch_component("C2909059")
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


WORKSPACE_ROOT = Path(__file__).parent.parent
DATA_DIR       = WORKSPACE_ROOT / "data"

API_URL = "https://easyeda.com/api/products/{lcsc_id}/components"
HEADERS = {
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate",
    "Content-Type":    "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent":      (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://easyeda.com/",
}

# EasyEDA-Einheit: 1 unit = 10 mil = 0.254 mm
EASYEDA_SCALE = 0.254


# ---------------------------------------------------------------------------
# Footprint-Parser
# ---------------------------------------------------------------------------

def _parse_pads(shape_list: list[str], origin_x: float, origin_y: float) -> list[dict]:
    """
    PAD-Eintraege aus EasyEDA shape-Liste parsen und in mm umrechnen.

    EasyEDA PAD-Format:
        PAD~RECT~cx~cy~width~height~layer~~padnum~rotation~bbox~...~sig_hint

    Gibt Liste von Dicts zurueck:
        {number, x, y, width, height}
    """
    pads = []
    for shape in shape_list:
        if not shape.startswith("PAD~"):
            continue
        parts = shape.split("~")
        # parts[0]=PAD, [1]=form, [2]=cx, [3]=cy, [4]=width, [5]=height,
        # [6]=layer, [7]=net, [8]=padnum, [9]=rotation, ...
        try:
            cx     = float(parts[2])
            cy     = float(parts[3])
            width  = float(parts[4])
            height = float(parts[5])
            padnum = parts[8]
        except (IndexError, ValueError):
            continue

        pads.append({
            "number": padnum,
            "x":      round((cx - origin_x) * EASYEDA_SCALE, 6),
            "y":      round((cy - origin_y) * EASYEDA_SCALE, 6),
            "width":  round(width  * EASYEDA_SCALE, 6),
            "height": round(height * EASYEDA_SCALE, 6),
        })
    return sorted(pads, key=lambda p: int(p["number"]))


def _parse_origin(canvas_str: str) -> tuple[float, float]:
    """
    Referenzpunkt (c_origin) aus dem canvas-String lesen.

    EasyEDA Pro Package canvas:
    CA~w~h~bg~grid_vis~grid_color~snap~...~line~scale~unit~...~ox~oy~...

    Index 16 = origin_x, Index 17 = origin_y (0-basiert).
    """
    parts = canvas_str.split("~")
    try:
        return float(parts[16]), float(parts[17])
    except (IndexError, ValueError):
        return 0.0, 0.0


def _parse_pin1_marker(shape_list: list[str], origin_x: float, origin_y: float) -> tuple[float, float] | None:
    """
    Seitendruckkreis (Layer 3) als Pin-1-Marker suchen.
    CIRCLE~x~y~... auf Layer 3 = TopSilk
    """
    for shape in shape_list:
        if not shape.startswith("CIRCLE~"):
            continue
        parts = shape.split("~")
        try:
            layer = int(parts[4]) if len(parts) > 4 else 0
        except ValueError:
            continue
        if layer == 3:
            try:
                cx = (float(parts[1]) - origin_x) * EASYEDA_SCALE
                cy = (float(parts[2]) - origin_y) * EASYEDA_SCALE
                return round(cx, 4), round(cy, 4)
            except (IndexError, ValueError):
                continue
    return None


def _parse_footprint(raw: dict[str, Any]) -> dict[str, Any]:
    """Footprint-Geometrie aus API-Rohdaten extrahieren."""
    pkg = raw.get("result", {}).get("packageDetail", {})
    data_str = pkg.get("dataStr", {})
    canvas   = data_str.get("canvas", "")
    shapes   = data_str.get("shape", [])

    origin_x, origin_y = _parse_origin(canvas)
    pads = _parse_pads(shapes, origin_x, origin_y)
    pin1 = _parse_pin1_marker(shapes, origin_x, origin_y)

    # Gehaeuse-Groesse aus Outline berechnen (SVGNODE oder SOLIDREGION)
    body_w = raw["result"]["packageDetail"]["dataStr"]["head"]["c_para"].get("package", "")

    return {
        "easyeda_scale":  EASYEDA_SCALE,
        "origin":         [origin_x, origin_y],
        "pads":           pads,
        "pin1_marker":    list(pin1) if pin1 else None,
    }


# EasyEDA-interne Signalnamen → normalisierte Projektnamen
_SIGNAL_ALIASES: dict[str, str] = {
    "SDO": "DO",
    "SDI": "DI",
    "CKO": "CO",
    "CKL": "CI",
    "VDD": "VDD",
    "GND": "GND",
}


def _parse_schematic_pin_signals(raw: dict[str, Any]) -> dict[str, str]:
    """
    Signalnamen aus dem Schaltzeichen extrahieren.

    EasyEDA Pin-Shape-Format:
        P~show~locked~pinnum~x~y~rot~id~unk^^x~y^^path^^1~x~y~rot~SIGNAL~...^^...

    Gibt {pad_number_str: normalized_signal} zurueck.
    """
    shapes = raw.get("result", {}).get("dataStr", {}).get("shape", [])
    mapping: dict[str, str] = {}
    for shape in shapes:
        if not shape.startswith("P~"):
            continue
        header = shape.split("^^")[0]
        parts  = header.split("~")
        try:
            pin_num = parts[3]
        except IndexError:
            continue

        blocks = shape.split("^^")
        # Block [3] hat Format: 1~x~y~rot~SIGNAL~position~...
        if len(blocks) > 3:
            sig_parts = blocks[3].split("~")
            if len(sig_parts) > 4:
                raw_sig = sig_parts[4].strip()
                mapping[pin_num] = _SIGNAL_ALIASES.get(raw_sig, raw_sig)
    return mapping


# ---------------------------------------------------------------------------
# Normalisierung
# ---------------------------------------------------------------------------

def _normalize(lcsc_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Metadaten-Felder normalisieren."""
    result = raw.get("result", {})
    c_para = result.get("dataStr", {}).get("head", {}).get("c_para", {})

    return {
        "jlcpcb_part":  lcsc_id,
        "mfr_part":     c_para.get("Manufacturer Part") or result.get("title", ""),
        "manufacturer": c_para.get("Manufacturer", ""),
        "description":  result.get("description", ""),
        "package":      c_para.get("package", ""),
        "part_class":   c_para.get("JLCPCB Part Class", ""),
        "smt":          bool(result.get("SMT", False)),
    }


# ---------------------------------------------------------------------------
# HTTP-Fetch
# ---------------------------------------------------------------------------

def _fetch_raw(lcsc_id: str) -> dict[str, Any]:
    import gzip as _gzip
    url = API_URL.format(lcsc_id=lcsc_id)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "") == "gzip":
            raw = _gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def fetch_component(lcsc_id: str, force: bool = False) -> dict[str, Any]:
    """
    Komponentendaten laden (Cache-first).

    Speichert:
      data/{lcsc_id}/component.json  -- Metadaten
      data/{lcsc_id}/footprint.json  -- Pad-Geometrie
      data/{lcsc_id}/raw.json        -- Rohdaten

    Returns normalisierte Metadaten.
    """
    part_dir      = DATA_DIR / lcsc_id
    json_path     = part_dir / "component.json"
    fp_path       = part_dir / "footprint.json"

    if json_path.exists() and fp_path.exists() and not force:
        with json_path.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        print(f"[cache]  {lcsc_id} -> {json_path.relative_to(WORKSPACE_ROOT)}")
        return data

    print(f"[fetch]  {lcsc_id} ...")
    try:
        raw = _fetch_raw(lcsc_id)
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"API-Fehler fuer {lcsc_id}: {exc}") from exc

    if not raw.get("success"):
        raise RuntimeError(f"API Fehler fuer {lcsc_id}: {raw.get('message', raw)}")

    data = _normalize(lcsc_id, raw)
    fp   = _parse_footprint(raw)

    # Signale aus Schaltzeichen ergaenzen
    sig_map = _parse_schematic_pin_signals(raw)
    for pad in fp["pads"]:
        pad["signal"] = sig_map.get(pad["number"], "")

    part_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    fp_path.write_text(json.dumps(fp, indent=2, ensure_ascii=False), encoding="utf-8")
    (part_dir / "raw.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[saved]  {json_path.relative_to(WORKSPACE_ROOT)}")
    print(f"[saved]  {fp_path.relative_to(WORKSPACE_ROOT)}")

    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Verwendung: {sys.argv[0]} <JLCPCB-Teilenummer> [--force]")
        print(f"Beispiel:   {sys.argv[0]} C2909059")
        sys.exit(1)

    force    = "--force" in sys.argv
    part_ids = [a for a in sys.argv[1:] if not a.startswith("-")]

    for pid in part_ids:
        try:
            info = fetch_component(pid, force=force)
            print(
                f"  mfr_part:    {info['mfr_part']}\n"
                f"  manufacturer:{info['manufacturer']}\n"
                f"  package:     {info['package']}\n"
                f"  part_class:  {info['part_class']}\n"
                f"  smt:         {info['smt']}\n"
            )
            # Footprint-Zusammenfassung anzeigen
            fp_path = DATA_DIR / pid / "footprint.json"
            if fp_path.exists():
                with fp_path.open() as f:
                    fp = json.load(f)
                print(f"  pads ({len(fp['pads'])}):")
                for p in fp["pads"]:
                    print(f"    Pad {p['number']:>2} {p.get('signal','?'):>5}: "
                          f"({p['x']:+.4f}, {p['y']:+.4f}) mm  "
                          f"{p['width']:.4f}x{p['height']:.4f} mm")
                if fp.get("pin1_marker"):
                    print(f"  pin1_marker: {fp['pin1_marker']}")
        except RuntimeError as exc:
            print(f"[ERROR]  {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
