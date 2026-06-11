"""
Orthogonal/45-Grad-Router fuer Top-Copper Daten-Traces.

Erzeugt Leiterbahnpfade mit ausschliesslich horizontalen, vertikalen
und 45-Grad-Segmenten (PCB-Standard: H/V/45).

Routing-Strategien (Prioritaet):
  1. Direkt gerade  (wenn Start und Ziel auf gleicher H- oder V-Achse)
  2. L-Route H->V   (erst horizontal, dann vertikal)
  3. L-Route V->H   (erst vertikal, dann horizontal)
  4. 45-Fase Start  (diagonal bis Achsenausgleich, dann gerade)
  5. 45-Fase Ende   (gerade bis Knie, dann 45-Grad ans Ziel)
  6. Fallback: direkte Verbindung mit Warnung

Kollisionsabfrage:
  Konservative AABB-Pruefung: die thematische Bounding-Box einer Trace
  (Segmentuell erweitert um Leiterbahnbreite/2) wird gegen alle
  LED-Koerper-Rechtecke (erweitert um Clearance) geprueft.
  Quell- und Ziel-LED werden dabei ausgeschlossen.
"""

from __future__ import annotations

import math
import warnings
from typing import List, Tuple

# Typ-Alias
Point  = Tuple[float, float]
Path   = List[Point]
Rect   = Tuple[float, float, float, float]   # (cx, cy, w, h)


# ---------------------------------------------------------------------------
# AABB-Hilfsfunktionen
# ---------------------------------------------------------------------------

def _seg_aabb(x1: float, y1: float, x2: float, y2: float, half_w: float) -> Rect:
    """Achsenparallele Bounding-Box eines Liniensegments mit halbem Querschnitt."""
    return (
        min(x1, x2) - half_w,
        min(y1, y2) - half_w,
        max(x1, x2) + half_w,
        max(y1, y2) + half_w,
    )


def _aabb_overlap(a: Rect, b: Rect) -> bool:
    """True wenn zwei AABBs sich ueberlappen (nicht nur beruehren)."""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _obstacle_aabb(obs: Tuple[float, float, float, float], clearance: float) -> Rect:
    cx, cy, ow, oh = obs
    hw, hh = ow / 2 + clearance, oh / 2 + clearance
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def _path_clear(
    waypoints: Path,
    obstacles: List[Tuple[float, float, float, float]],
    trace_w: float,
    clearance: float,
) -> bool:
    """True wenn kein Segment des Pfades ein Hindernis beruehrt."""
    hw = trace_w / 2
    obs_boxes = [_obstacle_aabb(o, clearance) for o in obstacles]
    for i in range(len(waypoints) - 1):
        x1, y1 = waypoints[i]
        x2, y2 = waypoints[i + 1]
        seg = _seg_aabb(x1, y1, x2, y2, hw)
        for box in obs_boxes:
            if _aabb_overlap(seg, box):
                return False
    return True


# ---------------------------------------------------------------------------
# Routing-Strategien
# ---------------------------------------------------------------------------

def _route_candidates(x1: float, y1: float, x2: float, y2: float) -> List[Path]:
    """
    Alle moeglichen H/V/45-Pfade von (x1,y1) nach (x2,y2) aufzaehlen.

    Gibt eine Liste von Pfad-Kandidaten zurueck, sortiert nach Prioritaet.
    """
    dx = x2 - x1
    dy = y2 - y1
    adx, ady = abs(dx), abs(dy)
    sx = 1.0 if dx >= 0 else -1.0
    sy = 1.0 if dy >= 0 else -1.0
    EPS = 1e-6

    candidates: List[Path] = []

    # 1. Direkt gerade (H oder V)
    if adx < EPS or ady < EPS:
        candidates.append([(x1, y1), (x2, y2)])

    # 2. L-Route: erst H, dann V
    candidates.append([(x1, y1), (x2, y1), (x2, y2)])

    # 3. L-Route: erst V, dann H
    candidates.append([(x1, y1), (x1, y2), (x2, y2)])

    # 4. 45-Fase am Start: diagonal bis Achsenausgleich, dann gerade
    if adx > EPS and ady > EPS:
        diag = min(adx, ady)
        mid = (x1 + sx * diag, y1 + sy * diag)
        candidates.append([(x1, y1), mid, (x2, y2)])

    # 5. 45-Fase am Ende: gerade bis Knie, dann diagonal
    if adx > EPS and ady > EPS:
        diag = min(adx, ady)
        mid = (x2 - sx * diag, y2 - sy * diag)
        candidates.append([(x1, y1), mid, (x2, y2)])

    # 6. Vollstaendig 45-Diagonal + Rest (nur wenn gleiche Laenge in H und V)
    if abs(adx - ady) < EPS:
        candidates.append([(x1, y1), (x2, y2)])

    return candidates


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def route(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    all_leds: List[Tuple[float, float, float, float]],  # (cx, cy, w, h)
    src_pos: Tuple[float, float],
    dst_pos: Tuple[float, float],
    trace_w: float = 0.15,
    clearance: float = 0.10,
) -> Path:
    """
    Berechnet einen kollisionsfreien H/V/45-Pfad von (x1,y1) nach (x2,y2).

    Parameters
    ----------
    all_leds : list of (cx, cy, body_w, body_h)
        Alle LED-Koerper als Rechtecke. Quell- und Ziel-LED werden
        anhand von src_pos/dst_pos aus der Kollisionsliste entfernt.
    src_pos, dst_pos : (x, y)
        Mittelpunkt-Koordinaten der Quell- bzw. Ziel-LED.
    trace_w : float
        Leiterbahnbreite in mm.
    clearance : float
        Mindestabstand zur LED-Koerperkante in mm.

    Returns
    -------
    List of (x, y) Waypoints.
    """
    # Quell- und Ziel-LED aus Hindernisliste ausschliessen
    EPS = 0.01
    obstacles = [
        obs for obs in all_leds
        if not (abs(obs[0] - src_pos[0]) < EPS and abs(obs[1] - src_pos[1]) < EPS)
        and not (abs(obs[0] - dst_pos[0]) < EPS and abs(obs[1] - dst_pos[1]) < EPS)
    ]

    for candidate in _route_candidates(x1, y1, x2, y2):
        if _path_clear(candidate, obstacles, trace_w, clearance):
            return candidate

    # Fallback: direkter Weg (koennte kollidieren)
    warnings.warn(
        f"Router: kein kollisionsfreier Pfad von ({x1:.3f},{y1:.3f}) "
        f"nach ({x2:.3f},{y2:.3f}) gefunden – Fallback direkt.",
        stacklevel=2,
    )
    return [(x1, y1), (x2, y2)]


def led_obstacles(
    leds: list,
    fp_body_w: float,
    fp_body_h: float,
) -> List[Tuple[float, float, float, float]]:
    """
    Erstellt die Hindernisliste aus allen LED-Positionen.

    Returns [(cx, cy, body_w, body_h), ...]
    """
    return [(led.x, led.y, fp_body_w, fp_body_h) for led in leds]
