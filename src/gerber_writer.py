"""
Gerber RS-274X Writer.

Koordinaten werden intern in nm (Nanometer) als Integer gespeichert,
Ausgabe erfolgt mit Format FSLAX46Y46 (4 Vorkomma, 6 Nachkomma Stellen, mm).
Das entspricht einer Aufloesung von 1 nm = ausreichend fuer PCB.

Einheit: mm  -> Faktor 1_000_000 (1 mm = 1_000_000 Einheiten bei .6 Nachkomma)
"""

from __future__ import annotations
from typing import List, Tuple, Optional
from enum import Enum, auto

# 1 mm = 10^6 Einheiten bei X4.6 Format
MM = 1_000_000


def _fmt(val_mm: float) -> str:
    """Float mm -> Gerber-Koordinaten-String (kein Dezimalpunkt, X4.6)."""
    return str(round(val_mm * MM))


class ApertureShape(Enum):
    CIRCLE = "C"
    RECT   = "R"
    OBLONG = "O"   # Oblong (abgerundetes Rechteck)


class GerberWriter:
    """
    Baut eine einzelne Gerber-Lage auf und gibt sie als String aus.

    Verwendung:
        g = GerberWriter("Top Copper")
        ap = g.add_aperture(ApertureShape.RECT, width=0.6, height=0.35)
        g.flash(ap, x=2.0, y=2.0)
        g.draw(ap_trace, x1=2.0, y1=2.0, x2=7.0, y2=2.0)
        print(g.render())
    """

    def __init__(self, comment: str = ""):
        self.comment = comment
        self._apertures: List[str] = []   # Apertur-Definitionen
        self._body: List[str] = []        # Zeichenbefehle
        self._ap_idx = 10                 # Erste Apertur-ID (D10+)
        self._current_ap: Optional[int] = None

    # ------------------------------------------------------------------
    # Apertur-Verwaltung
    # ------------------------------------------------------------------

    def add_aperture(
        self,
        shape: ApertureShape,
        width: float,
        height: Optional[float] = None,
        *,
        hole: Optional[float] = None,
    ) -> int:
        """
        Apertur definieren und ID zurueckgeben.

        Args:
            shape:  CIRCLE, RECT oder OBLONG
            width:  Breite (oder Durchmesser bei CIRCLE) in mm
            height: Hoehe in mm (nur bei RECT/OBLONG)
            hole:   Optionaler Innendurchmesser (fuer Pads mit Loch) in mm

        Returns:
            Apertur-ID (Ganzzahl, z.B. 10)
        """
        ap_id = self._ap_idx
        self._ap_idx += 1

        if shape == ApertureShape.CIRCLE:
            params = f"{width:.6f}"
        else:
            h = height if height is not None else width
            params = f"{width:.6f}X{h:.6f}"

        if hole is not None:
            params += f"X{hole:.6f}"

        self._apertures.append(f"%ADD{ap_id}{shape.value},{params}*%")
        return ap_id

    def _select(self, ap_id: int):
        if self._current_ap != ap_id:
            self._body.append(f"G54D{ap_id}*")
            self._current_ap = ap_id

    # ------------------------------------------------------------------
    # Zeichenbefehle
    # ------------------------------------------------------------------

    def flash(self, ap_id: int, x: float, y: float):
        """Pad-Flash an Position (x, y) in mm."""
        self._select(ap_id)
        self._body.append(f"X{_fmt(x)}Y{_fmt(y)}D03*")

    def move(self, x: float, y: float):
        """Werkzeug heben und bewegen (kein Zeichnen)."""
        self._body.append(f"X{_fmt(x)}Y{_fmt(y)}D02*")

    def draw(self, ap_id: int, x1: float, y1: float, x2: float, y2: float):
        """Linie von (x1,y1) nach (x2,y2) in mm."""
        self._select(ap_id)
        self._body.append(f"X{_fmt(x1)}Y{_fmt(y1)}D02*")
        self._body.append(f"X{_fmt(x2)}Y{_fmt(y2)}D01*")

    def rect_outline(self, ap_id: int, x0: float, y0: float, x1: float, y1: float):
        """Geschlossenes Rechteck als Linienzug (Board Outline)."""
        self._select(ap_id)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        self._body.append(f"X{_fmt(corners[0][0])}Y{_fmt(corners[0][1])}D02*")
        for cx, cy in corners[1:]:
            self._body.append(f"X{_fmt(cx)}Y{_fmt(cy)}D01*")

    # ------------------------------------------------------------------
    # Ausgabe
    # ------------------------------------------------------------------

    def render(self) -> str:
        lines: List[str] = []
        if self.comment:
            lines.append(f"G04 {self.comment} *")
        # Header
        lines += [
            "%FSLAX46Y46*%",   # Koordinatenformat: 4 Vor-, 6 Nachkommastellen
            "%MOMM*%",         # Einheit Millimeter
            "%LPD*%",          # Layer Polarity: Dark
        ]
        # Apertur-Definitionen
        lines += self._apertures
        # Linear-Modus
        lines.append("G01*")
        # Zeichenbefehle
        lines += self._body
        # Dateiende
        lines.append("M02*")
        return "\n".join(lines) + "\n"
