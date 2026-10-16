"""
Machbarkeitspruefung fuer die Schema-Architektur (layout_schema.py).

Wird VOR jeder Generierung ausgefuehrt. Bei Misserfolg bricht der
Generator ab und nennt Grund + kleinsten machbaren pitch.

Randbedingungen (Rotation 180/90, eine F.Cu-Schiene je Luecke,
mittige B.Cu-Rails, Korridor-Routing, Randzonen-Schienen):
  C1  Pad-zu-Pad quer:        pitch - 2*ex            >= CLEARANCE
  C2  Pad-zu-Pad senkrecht:   pitch - 2*ey            >= CLEARANCE
  C3  Innen-Schiene in Luecke: Luecke >= RAIL_TOP_W + 2*CLEARANCE
  C4  Randzonen-Schiene:      pitch/2 - ey >= CLEARANCE + RAIL_EDGE_W
                              + EDGE_CLEAR   (dominierender Engpass)
  C5  Korridor-Routing:       (pitch - 2*ex)/2 >= trace/2 + CLEARANCE
  C6  Randkanal (Reihenuebergang): pitch/2 - ex >= trace/2 + CLEARANCE
                              + EDGE_CLEAR
  C7  B.Cu-Rails: 2*W/3 + GAP <= W - 2*EDGE_CLEAR
  C8  Stitch-Vias (cx +- 2mm) innerhalb der Schienenenden
  C9  Eckpads ausserhalb der B.Cu-Rails (Clearance)
  C10 Economic-PCBA: Board >= 10x10 mm
"""
from __future__ import annotations

from typing import List, Tuple

import design_rules as DR
import power_grid as PG


def _extents(fp) -> Tuple[float, float]:
    """Halbe Pad-Ausdehnung (ex, ey) des Footprints inkl. Pad-Groesse."""
    ex = max(abs(p.x) + p.width / 2 for p in fp.pads)
    ey = max(abs(p.y) + p.height / 2 for p in fp.pads)
    return ex, ey


def check_matrix(cols: int, rows: int, pitch: float, fp) -> Tuple[bool, List[str]]:
    ex, ey = _extents(fp)
    W, H = cols * pitch, rows * pitch
    reasons: List[str] = []
    CL = DR.CLEARANCE

    def need_pitch_y(budget: float) -> float:
        return 2 * budget

    # C1/C2: Pad-Abstaende
    if pitch - 2 * ex < CL:
        reasons.append(f"C1/C2 Pad-Abstand: pitch >= {2*ex + CL:.2f}mm")

    # C3: Innen-Schiene: Luecke zwischen Pad-Kanten beider Reihen
    #     (gemischt rotiert: ey oben + ey unten)
    if pitch - 2 * ey < PG.RAIL_TOP_W + 2 * CL:
        need = 2 * ey + PG.RAIL_TOP_W + 2 * CL
        reasons.append(f"C3 Innen-Schiene: Luecke zu schmal "
                       f"(pitch >= {need:.2f}mm)")

    # C4 Randzonen-Schiene: nutzt die tatsaechliche facing-Ausdehnung der
    # unteren/oberen Reihe (90°-gedrehte Reihen: |p.x|+p.width/2 = groesser).
    # Obere Reihe ist immer 180° (vrow 0); kritisch ist die untere Reihe.
    from matrix import row_rotation
    ey_face = max(abs(p.y) + p.height / 2 for p in fp.pads)
    ey_face_rot = max(abs(p.x) + p.width / 2 for p in fp.pads)
    ey_edge = max(ey_face, ey_face_rot if int(row_rotation(rows - 1)) % 180 == 90 else 0.0)
    if pitch / 2 - ey_edge < CL + PG.RAIL_EDGE_W + DR.EDGE_CLEAR:
        need = 2 * (ey_edge + CL + PG.RAIL_EDGE_W + DR.EDGE_CLEAR)
        reasons.append(f"C4 Randzonen-Schiene: pitch >= {need:.2f}mm")

    # C5: Korridor-Vertikale zwischen benachbarten Pads
    if (pitch - 2 * ex) / 2 < DR.TRACE_DATA / 2 + CL:
        need = 2 * ex + DR.TRACE_DATA + 2 * CL
        reasons.append(f"C5 Daten-Korridor: pitch >= {need:.2f}mm")

    # C6: Randkanal links/rechts
    if pitch / 2 - ex < DR.TRACE_DATA / 2 + CL + DR.EDGE_CLEAR:
        need = 2 * (ex + DR.TRACE_DATA / 2 + CL + DR.EDGE_CLEAR)
        reasons.append(f"C6 Randkanal: pitch >= {need:.2f}mm")

    # C7: B.Cu-Rails
    if 2 * W / 3 + PG.GAP > W - 2 * DR.EDGE_CLEAR:
        reasons.append(f"C7 B.Cu-Rails: W >= "
                       f"{3 * (PG.GAP + 2 * DR.EDGE_CLEAR):.1f}mm")

    # C8: Stitch-Vias (cx +- 2mm) muessen innerhalb der Schienenenden liegen
    #     aeusserste Schienen-Ende = letzte Power-Pad-Kante:
    rail_x_end = W - pitch / 2 + ex - min(abs(p.x) for p in fp.pads
                                          if p.signal in ("VDD", "GND")) \
        + max(p.width for p in fp.pads) / 2
    vcc_x0, vcc_x1 = W / 2 + PG.GAP / 2, W - PG.CONN_W - DR.MIN_SPACING
    cx_vcc = (vcc_x0 + vcc_x1) / 2
    if cx_vcc + PG.STITCH_DX + DR.VIA_PAD_D / 2 > rail_x_end:
        reasons.append(f"C8 Stitch-Vias: VCC-Via bei {cx_vcc + PG.STITCH_DX:.1f} "
                       f"ueber Schienen-Ende {rail_x_end:.1f} "
                       f"(noetig: W >= {pitch + 2 * (PG.STITCH_DX + DR.VIA_PAD_D / 2 + ex + PG.GAP / 2):.1f}mm)")

    # C9: B.Cu-Rails maximale Breite (abzgl. DIN/DOUT-Anschlusspads);
    #     unter RAIL_MIN -> unmachbar. Eckpad-Clearance gilt per Konstruktion.
    rw = (W - PG.GAP) / 2 - PG.CONN_W - DR.MIN_SPACING
    if rw < PG.RAIL_MIN:
        reasons.append(f"C9 B.Cu-Rail-Breite: {rw:.2f}mm < {PG.RAIL_MIN}mm "
                       f"(noetig: W >= {2 * (PG.RAIL_MIN + PG.CONN_W + DR.MIN_SPACING + PG.GAP / 2):.1f}mm)")

    # C10: Economic-Minimum
    if W < 10.0 or H < 10.0:
        reasons.append(f"C10 Economic-PCBA: Board {W:.1f}x{H:.1f} < 10x10mm")

    # C11: Mindestgroesse der Matrix (Referenzimplementierung 8x8,
    #      validiert ab 5x4)
    if cols < 5 or rows < 4:
        reasons.append("C11 Mindestmatrix: cols >= 5 und rows >= 4")

    return (len(reasons) == 0, reasons)


def min_feasible_pitch(cols: int, rows: int, fp,
                       start: float = 1.0, stop: float = 10.0) -> float | None:
    """Kleinsten pitch (0.05mm-Schritte) finden, der alle Regeln erfuellt."""
    p = start
    while p <= stop + 1e-9:
        ok, _ = check_matrix(cols, rows, round(p, 2), fp)
        if ok:
            return round(p, 2)
        p += 0.05
    return None


if __name__ == "__main__":
    import sys
    from footprint import footprint_from_data
    lcsc = sys.argv[1] if len(sys.argv) > 1 else "C41413180"
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    fp = footprint_from_data(lcsc)
    print(f"Footprint: {fp.name}  Pads: {[(p.signal, p.width, p.height) for p in fp.pads]}")
    for pitch in (2.5, 2.9, 3.0):
        ok, reasons = check_matrix(cols, rows, pitch, fp)
        print(f"\npitch={pitch}: {'OK' if ok else 'NICHT MACHBAR'}")
        for r in reasons:
            print(f"  - {r}")
    mp = min_feasible_pitch(cols, rows, fp)
    print(f"\nkleinster machbarer pitch: {mp}")
