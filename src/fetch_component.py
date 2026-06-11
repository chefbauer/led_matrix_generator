"""
EasyEDA/JLCPCB Komponentendaten-Fetcher

Laedt Bauteil-Metadaten direkt von der EasyEDA-API (kein Login noetig)
und speichert sie als JSON-Cache unter:

    data/{JLCPCB_PART_NUMBER}/component.json

Gespeicherte Felder (normalisiert):
    jlcpcb_part     z.B. "C2909059"
    mfr_part        z.B. "SK9822-EC20"
    manufacturer    z.B. "Opsco Optoelectronics"
    description     z.B. "..."
    package         z.B. "LED-SMD_6P-L2.0-W2.0-P0.80-TL"
    part_class      z.B. "Extended Part"
    smt             True

Verwendung als Script:
    python3 fetch_component.py C2909059
    python3 fetch_component.py C2909059 C1234567 ...

Verwendung als Modul:
    from fetch_component import fetch_component, DATA_DIR
    info = fetch_component("C2909059")
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Interne Helfer
# ---------------------------------------------------------------------------

def _fetch_raw(lcsc_id: str) -> dict[str, Any]:
    """Rohe API-Antwort von EasyEDA holen."""
    import gzip as _gzip

    url = API_URL.format(lcsc_id=lcsc_id)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        raw = resp.read()
        encoding = resp.headers.get("Content-Encoding", "")
        if encoding == "gzip":
            raw = _gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _normalize(lcsc_id: str, api: dict[str, Any]) -> dict[str, Any]:
    """Relevante Felder aus der API-Antwort extrahieren und normalisieren."""
    result = api.get("result", {})
    c_para = result.get("dataStr", {}).get("head", {}).get("c_para", {})

    mfr_part    = c_para.get("Manufacturer Part") or result.get("title", "")
    manufacturer = c_para.get("Manufacturer", "")
    package      = c_para.get("package", "")
    part_class   = c_para.get("JLCPCB Part Class", "")
    description  = result.get("description", "")
    smt: bool    = bool(result.get("SMT", False))

    return {
        "jlcpcb_part":  lcsc_id,
        "mfr_part":     mfr_part,
        "manufacturer": manufacturer,
        "description":  description,
        "package":      package,
        "part_class":   part_class,
        "smt":          smt,
    }


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def fetch_component(lcsc_id: str, force: bool = False) -> dict[str, Any]:
    """
    Komponentendaten laden (Cache-first).

    Parameters
    ----------
    lcsc_id : str
        JLCPCB/LCSC-Teilenummer, z.B. "C2909059"
    force : bool
        Cache ignorieren und neu laden.

    Returns
    -------
    dict mit den normalisierten Komponentendaten.
    """
    part_dir  = DATA_DIR / lcsc_id
    json_path = part_dir / "component.json"

    if json_path.exists() and not force:
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
        raise RuntimeError(
            f"API hat Fehler gemeldet fuer {lcsc_id}: {raw.get('message', raw)}"
        )

    data = _normalize(lcsc_id, raw)

    # Rohdaten ebenfalls speichern fuer spaetere Nutzung
    part_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (part_dir / "raw.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[saved]  {json_path.relative_to(WORKSPACE_ROOT)}")

    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(f"Verwendung: {sys.argv[0]} <JLCPCB-Teilenummer> [...]")
        print(f"Beispiel:   {sys.argv[0]} C2909059")
        sys.exit(1)

    force = "--force" in sys.argv
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
        except RuntimeError as exc:
            print(f"[ERROR]  {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
