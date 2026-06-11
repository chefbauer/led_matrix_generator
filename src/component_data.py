"""
Komponentendaten-Loader.

Laedt gecachte Bauteil-Informationen aus data/{JLCPCB_PART}/component.json
und stellt sie als typisiertes ComponentInfo-Objekt bereit.

Falls die Datei nicht existiert, wirft dieser Modul eine klare Fehlermeldung
mit Hinweis auf fetch_component.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).parent.parent
DATA_DIR       = WORKSPACE_ROOT / "data"


@dataclass
class ComponentInfo:
    """Normalisierte Bauteil-Metadaten aus der EasyEDA/JLCPCB-API."""
    jlcpcb_part:  str   # z.B. "C2909059"
    mfr_part:     str   # z.B. "SK9822-EC20"
    manufacturer: str   # z.B. "Opsco Optoelectronics"
    description:  str
    package:      str   # EasyEDA-Footprint-Name
    part_class:   str   # "Basic Part" | "Extended Part"
    smt:          bool


def load_component(lcsc_id: str) -> ComponentInfo:
    """
    Laedt gecachte Komponentendaten.

    Raises
    ------
    FileNotFoundError
        Wenn die Daten noch nicht gefetcht wurden.
        Loesung: `python3 src/fetch_component.py {lcsc_id}` ausfuehren.
    """
    json_path = DATA_DIR / lcsc_id / "component.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"Keine gecachten Daten fuer '{lcsc_id}'.\n"
            f"Bitte erst ausführen: python3 src/fetch_component.py {lcsc_id}"
        )
    with json_path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return ComponentInfo(**raw)


def load_components(lcsc_ids: list[str]) -> dict[str, ComponentInfo]:
    """Mehrere Bauteile laden. Gibt {lcsc_id: ComponentInfo} zurueck."""
    return {pid: load_component(pid) for pid in lcsc_ids}
