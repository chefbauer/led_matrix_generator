"""
Power-Grid-Geometrie (Schema-Vorlage: tools/layout_schema.py).

Rueckseite (B.Cu):
  Zwei vertikale mittige Stromschienen: GND links, VCC rechts, je W/3
  breit, mit GAP zueinander (treffen sich in der Mitte). Volle Boardhoehe.
  Anschlusspads: GND/VCC = freigelegte Rail-Enden oben+unten (Exposures),
  DIN (oben-links) und DOUT (unten-links) als isolierte SMD-Eckpads.

Vorderseite (F.Cu):
  Je Luecke zwischen zwei LED-Reihen EINE horizontale Schiene; Netz
  alternierend VCC/GND, bestimmt durch die einander gegenueberliegenden
  Power-Pads (Rotation 180/90 gemäss matrix.py). Die Schiene spannt nur
  ueber die Power-Pad-Spalten (Daten-Pads bleiben frei) und endet an der
  aeussersten Power-Pad-Kante. Stubs zu jedem gegenueberliegenden
  Power-Pad. Randzonen (ueber erster / unter letzter Reihe) erhalten je
  eine Rand-Schiene (Netz = dortige Power-Pad-Seite).
  3 Stitching-Vias pro Schiene, 2 mm Abstand, mittig auf der
  zugehoerigen B.Cu-Schiene (verbindet F.Cu-Schiene mit B.Cu-Rail).

Alle Masse in mm, Koordinaten Ursprung links-unten.
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple

import design_rules as DR

GAP = 1.0            # Abstand der beiden B.Cu-Rails zueinander
RAIL_MIN = 2.5       # Mindestbreite je B.Cu-Rail -> sonst Abbruch
VIA_AMP = 0.3        # A: Tragfahigkeit eines 0.3mm-Vias (JLC)


def _rail_w_for_amp(i_a: float) -> float:
    """Leiterbahnbreite (mm) fuer i_a Ampere: IPC-2221 aussen, 1 oz, dT=10C.
    I = 0.048 * dT^0.44 * A^0.75 (A in mil^2) -> invertiert."""
    a_mil2 = (i_a / (0.048 * 10 ** 0.44)) ** (1.0 / 0.75)
    return a_mil2 / 1.378 * 0.0254
RAIL_TOP_W = 0.4     # Breite der F.Cu-Innenschienen
RAIL_EDGE_W = 0.3    # Randzonen-Schienen: schmaler (0.7mm-Zone)
STUB_W = 0.3         # Stub-Breite zu den Power-Pads
STITCH_DX = 2.0      # Vias pro Schiene: 3 Stueck, 2 mm Abstand
N_STITCH = 3
EDGE_VIA_PAD = 0.6   # Rand-Vias (2x pro Randzonen-Schiene): gleich wie
                     # innen; Position neben dem Power-Pad der Randreihe
CONN_W = 2.5         # DIN/DOUT-Anschlusspads (B.Cu), randbuendig
CONN_H = 5.0
PWR_PAD = 5.0        # VCC/GND-Anschlussflaechen (randbuendig, auf Rail)

Rect = Tuple[float, float, float, float]


def _rot(px: float, py: float, deg: float) -> Tuple[float, float]:
    """Pad-Offset um Bestueckungsrotation drehen."""
    import math
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return px * c - py * s, px * s + py * c


def pad_pos(led, signal: str, fp) -> Tuple[float, float, float, float]:
    """Absolute Pad-Mitte (x, y) + Pad-Abmessungen (w, h) nach Rotation."""
    for p in fp.pads:
        if p.signal == signal:
            ox, oy = _rot(p.x, p.y, led.rotation)
            if int(led.rotation) % 180 == 90:
                w, h = p.height, p.width
            else:
                w, h = p.width, p.height
            return led.x + ox, led.y + oy, w, h
    raise KeyError(signal)


def facing_pads(row_leds, up: bool, fp):
    """Pads einer Reihe, die nach oben (up=True) bzw. unten zeigen.
    Liefert (signal, x, y_edge, w, h) je Pad."""
    out = []
    for led in row_leds:
        for p in fp.pads:
            ox, oy = _rot(p.x, p.y, led.rotation)
            if (oy > 0) == up:
                w, h = (p.height, p.width) if int(led.rotation) % 180 == 90 \
                    else (p.width, p.height)
                edge = led.y + oy + (h / 2 if up else -h / 2)
                out.append((p.signal, led.x + ox, edge, w, h))
    return out


def compute_power_grid(leds, fp, W: float, H: float, pitch: float,
                       led_ma: float = 15.0) -> dict:
    """Komplette Power-Geometrie. Siehe Modul-Doku.

    led_ma: Strom pro LED (mA) -> bestimmt Stitch-Via-Anzahl:
    n = max(3, naechste ungerade Zahl >= 2*I_Reihe/0.3A)  [doppelte Sicherheit]
    Position: symmetrisch links/mitte/rechts auf der B.Cu-Rail.
    """
    rows = sorted({led.row for led in leds})
    by_row = {r: [l for l in leds if l.row == r] for r in rows}

    # --- B.Cu: zwei mittige Rails, maximale Breite ----------------------
    # Breite = halbe Boardbreite - GAP/2 - DIN/DOUT-Anschlusspads
    # - Clearance zu denselben. Unter RAIL_MIN -> Abbruch.
    rw = (W - GAP) / 2 - CONN_W - DR.MIN_SPACING
    if rw < RAIL_MIN:
        raise ValueError(
            f"B.Cu-Rails zu schmal: {rw:.2f}mm < {RAIL_MIN}mm "
            f"(Board {W:.1f} x {H:.1f}mm). Groessere Matrix noetig.")
    gnd = (CONN_W + DR.MIN_SPACING, DR.EDGE_CLEAR,
           W / 2 - GAP / 2, H - DR.EDGE_CLEAR)
    vcc = (W / 2 + GAP / 2, DR.EDGE_CLEAR,
           W - CONN_W - DR.MIN_SPACING, H - DR.EDGE_CLEAR)
    rails_bottom = [("GND", gnd), ("VCC", vcc)]
    rail_cx = {"GND": (gnd[0] + gnd[2]) / 2, "VCC": (vcc[0] + vcc[2]) / 2}
    rail_cx_bounds = {"GND": (gnd[0], gnd[2]), "VCC": (vcc[0], vcc[2])}
    cols = len(by_row[rows[0]])
    i_row = cols * led_ma / 1000.0

    # --- F.Cu: eine Schiene je Luecke + Randzonen ----------------------
    rails_top = []      # {net, y, x0, x1}
    gaps = []           # (upper_row, lower_row)
    for r in rows[1:]:
        gaps.append((r, r - 1))

    def make_rail(up_leds, down_leds, y_up_edge, y_dn_edge):
        """up_leds: Reihe deren Pads nach UNTEN zeigen (obere Reihe),
        down_leds: Reihe deren Pads nach OBEN zeigen (untere Reihe)."""
        dn = facing_pads(up_leds, up=False, fp=fp)     # zeigen nach unten
        up = facing_pads(down_leds, up=True, fp=fp)    # zeigen nach oben
        nets_up = {s for s, *_ in dn if s in ("VDD", "GND")}
        nets_dn = {s for s, *_ in up if s in ("VDD", "GND")}
        if nets_up != nets_dn or len(nets_up) != 1:
            raise RuntimeError(
                f"Power-Pads gegenueberliegend, aber Netze stimmen nicht: "
                f"{nets_up} vs {nets_dn} -> Rotation fehlerhaft")
        net = "VCC" if nets_up == {"VDD"} else "GND"
        stub_x = [x for s, x, e, w, h in dn + up if s in ("VDD", "GND")]
        y = (min(y_up_edge) + max(y_dn_edge)) / 2.0
        # Breite: ampazitaetsbasiert mit doppelter Sicherheit (IPC-2221
        # aussen, 1oz, dT=10C), Minimum RAIL_TOP_W, Obergrenze = Luecke
        # minus 2x Clearance.
        gap_h = min(y_up_edge) - max(y_dn_edge)
        w_need = _rail_w_for_amp(2 * i_row)
        w_rail = min(gap_h - 2 * DR.CLEARANCE, max(RAIL_TOP_W, w_need))
        # Abschluss buendig mit der aeussersten Stichleitung (nicht Padkante)
        rails_top.append({"net": net, "y": y,
                          "x0": min(stub_x) - STUB_W / 2,
                          "x1": max(stub_x) + STUB_W / 2,
                          "w": w_rail,
                          "stubs": [(x, e) for s, x, e, w, h in dn + up
                                    if s in ("VDD", "GND")]})

    for (ru, rl) in gaps:
        up_edge = [e for s, x, e, w, h in facing_pads(by_row[ru], False, fp)]
        dn_edge = [e for s, x, e, w, h in facing_pads(by_row[rl], True, fp)]
        make_rail(by_row[ru], by_row[rl], up_edge, dn_edge)

    # Randzonen: ueber oberster Reihe / unter unterster Reihe
    top_row, bot_row = rows[-1], rows[0]
    e_top = [e for s, x, e, w, h in facing_pads(by_row[top_row], True, fp)]
    e_bot = [e for s, x, e, w, h in facing_pads(by_row[bot_row], False, fp)]
    # nur Power-Pads bestimmen Netz; Rand-Schiene liegt zwischen Pad-Kante
    # und Boardrand (Clearance eingehalten durch y-Position unten)
    def edge_rail(row_leds, up: bool):
        # Randzone: nur 0.65-0.7 mm zwischen Pad-Kante und Boardrand ->
        # schmale Schiene (0.3) mit je EINEM Rand-Via (0.6-Pad passt nur
        # mit eingezogener Y-Position), das auf der B.Cu-Expose-Flaeche
        # sitzt und die Schiene beruehrt.
        pads = facing_pads(row_leds, up, fp)
        nets = {s for s, *_ in pads if s in ("VDD", "GND")}
        if len(nets) != 1:
            raise RuntimeError(f"Randzone-Netz nicht eindeutig: {nets}")
        net = "VCC" if nets == {"VDD"} else "GND"
        pw = [(x, e) for s, x, e, w, h in pads if s in ("VDD", "GND")]
        # Dynamische Breite: Platz zwischen Pad-Kante (+Clearance) und
        # Boardrand (-EDGE_CLEAR). Bei p3 ergibt das exakt die bisherigen
        # 0.3mm, bei groesserem Pitch breitere Randzonen-Schienen.
        if up:   # ueber der Reihe
            w_edge = (H - DR.EDGE_CLEAR) - (max(e for _, e in pw) + DR.CLEARANCE)
            y = max(e for _, e in pw) + DR.CLEARANCE + w_edge / 2
        else:
            w_edge = (min(e for _, e in pw) - DR.CLEARANCE) - DR.EDGE_CLEAR
            y = min(e for _, e in pw) - DR.CLEARANCE - w_edge / 2
        # Abschluss buendig mit der aeussersten Stichleitung
        rails_top.append({"net": net, "y": y,
                          "x0": min(x for x, _ in pw) - STUB_W / 2,
                          "x1": max(x for x, _ in pw) + STUB_W / 2,
                          "w": w_edge, "stubs": pw, "edge": True})

    edge_rail(by_row[top_row], up=True)
    edge_rail(by_row[bot_row], up=False)

    # --- Stitching-Vias: Basis 3 (links/mitte/rechts auf der B.Cu-Rail),
    #     bei mehr Strom 5/7/9... symmetrisch; doppelte Sicherheit gegen
    #     Via-Tragfahigkeit VIA_AMP.
    n_via = max(N_STITCH, math.ceil(2 * i_row / VIA_AMP))
    if n_via % 2 == 0:
        n_via += 1
    stitch_vias = []
    for rail in rails_top:
        rx0, rx1 = rail_cx_bounds[rail["net"]]
        lo = max(rail["x0"], rx0) + 0.35
        hi = min(rail["x1"], rx1) - 0.35
        if hi <= lo:
            continue
        if rail.get("edge"):
            # Randzonen: Vias neben Power-Pads (bewaehrte Position: Pad-
            # Rand + 0.25, auf Padkanten-Hoehe -> kein Konflikt mit
            # Boardrand/Datenkette). Auswahl links/mitte/rechts ueber die
            # dafuer in Frage kommenden Pads der Randreihe.
            pad_off = 0.225 + 0.3 + 0.025
            cands = sorted((x + pad_off, e) for (x, e) in rail["stubs"]
                           if lo <= x + pad_off <= hi)
            if not cands:
                continue
            k = min(n_via, len(cands))
            idx = sorted({round(i * (len(cands) - 1) / (k - 1)) if k > 1
                          else (len(cands) - 1) // 2 for i in range(k)})
            for j in idx:
                x, e = cands[j]
                stitch_vias.append((x, e, rail["net"], DR.VIA_PAD_D))
            continue
        for i in range(n_via):
            x = lo + i * (hi - lo) / (n_via - 1)
            stitch_vias.append((x, rail["y"], rail["net"], DR.VIA_PAD_D))

    # --- B.Cu-Anschlusspads --------------------------------------------
    # DIN/DOUT: 2.5 x 5 mm, VCC/GND: 5 x 5 mm, direkt am Boardrand
    # (Randabstand bewusst ignoriert, vom Anwender verlangt).
    # DOUT-Ecke folgt dem Kettenende: unten-links bei gerader,
    # unten-rechts bei ungerader Zeilenzahl.
    dout_right = len(rows) % 2 == 1
    corner_pads = {
        "DIN":  (0.0, H - CONN_H, CONN_W, H),
        "DOUT": ((W - CONN_W, 0.0, W, CONN_H) if dout_right
                 else (0.0, 0.0, CONN_W, CONN_H)),
    }
    gnd_cx = (gnd[0] + gnd[2]) / 2
    vcc_cx = (vcc[0] + vcc[2]) / 2
    # Anschlussflaechen nicht ueber Rail-Breite (sonst Kollision mit DIN/DOUT-Pads)
    pw = min(PWR_PAD, rw)
    exposures = [
        ((gnd_cx - pw / 2, H - pw, gnd_cx + pw / 2, H), "GND"),
        ((vcc_cx - pw / 2, H - pw, vcc_cx + pw / 2, H), "VCC"),
        ((gnd_cx - pw / 2, 0.0, gnd_cx + pw / 2, pw), "GND"),
        ((vcc_cx - pw / 2, 0.0, vcc_cx + pw / 2, pw), "VCC"),
    ]

    return {
        "rails_bottom": rails_bottom,
        "rails_top": rails_top,
        "stitch_vias": stitch_vias,
        "corner_pads": corner_pads,
        "exposures": exposures,
    }


if __name__ == "__main__":
    from footprint import footprint_from_data
    from matrix import generate_matrix
    fp = footprint_from_data("C41413180")
    leds = generate_matrix(8, 8, 3.0, fp)
    W, H = 24.0, 24.0
    pg = compute_power_grid(leds, fp, W, H, 3.0)
    nets = [(r["net"], round(r["y"], 2), round(r["x0"], 2), round(r["x1"], 2))
            for r in pg["rails_top"]]
    for n in nets:
        print("F.Cu-Schiene:", n)
    print("Stitch-Vias:", len(pg["stitch_vias"]))
    assert len(pg["rails_top"]) == 9, "7 Luecken + 2 Randzonen"
    seq = [n[0] for n in nets]
    assert seq.count("GND") == 5 and seq.count("VCC") == 4, seq
    assert len(pg["stitch_vias"]) >= 7 * 3 + 2 * 2, "min. 7x3 Innen + 2x2 Rand"
    ws = [r["w"] for r in pg["rails_top"] if not r.get("edge")]
    assert all(abs(w - RAIL_TOP_W) < 1e-3 for w in ws), ws  # 15mA -> Minimum
    print("OK: 9 Schienen (5x GND, 4x VCC), %d Stitch-Vias, Innen-Breite %.2fmm"
          % (len(pg["stitch_vias"]), ws[0]))
