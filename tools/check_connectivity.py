"""Konnektivitaets-Check: Prueft Netz-Bildung des generierten Layouts.

1. GND/VCC: alle 64 Power-Pads haengen an je EINEM Netz (Rails+Stubs+Vias).
2. Datenkette: L1.DO -> L2.DI -> ... -> L64, plus DIN-/DOUT-Anschlusspads.
3. Schienen-Netze alternieren pro Zeilengrenze.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from drc_geometry import collect_copper, shape_gap

def main(pitch=3.0, cols=8, rows=8):
    copper, (leds, pg, dc, W, H) = collect_copper(cols, rows, pitch)

    parent = list(range(len(copper)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj: parent[ri] = rj

    # 1) Gleichlagige Beruehrung/UEberlappung gleicher Netzen unionieren
    by_layer = {}
    for i, it in enumerate(copper):
        by_layer.setdefault(it[0], []).append(i)
    for layer, idxs in by_layer.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                ia, ib = idxs[a], idxs[b]
                if copper[ia][1] == copper[ib][1] and \
                   shape_gap(copper[ia], copper[ib]) <= 1e-9:
                    union(ia, ib)
    # 2) Vias: F.Cu-Pad und B.Cu-Pad des gleichen Netzes an gleicher Stelle
    vias = [i for i, it in enumerate(copper) if "via" in it[3]]
    for a in range(len(vias)):
        for b in range(a + 1, len(vias)):
            ia, ib = vias[a], vias[b]
            if copper[ia][0] != copper[ib][0] and copper[ia][1] == copper[ib][1] \
               and shape_gap(copper[ia], copper[ib]) <= 1e-9:
                union(ia, ib)

    def net_of(label_part):
        for i, it in enumerate(copper):
            if label_part in it[3]:
                return find(i)
        return None

    # --- Check 1: alle GND-Pads auf einem Netz, alle VDD-Pads auf einem Netz
    gnd_ids = [i for i, it in enumerate(copper) if it[3].startswith("pad GND")]
    vdd_ids = [i for i, it in enumerate(copper) if it[3].startswith("pad VDD")]
    ok = True
    for name, ids in (("GND", gnd_ids), ("VCC", vdd_ids)):
        roots = {find(i) for i in ids}
        status = "OK" if len(roots) == 1 else f"FEHLER: {len(roots)} Inseln"
        print(f"[1] {name}: {len(ids)} Pads -> {status}")
        ok &= len(roots) == 1 and len(ids) == cols * rows

    # --- Check 2: Datenkette L_k.DO -> L_{k+1}.DI fuer alle Nachbarn
    def pad_net(ref, sig):
        for i, it in enumerate(copper):
            if it[3] == f"pad {sig} {ref}":
                return find(i)
        raise KeyError(ref + sig)
    bad = []
    for k in range(len(leds) - 1):
        if pad_net(leds[k].ref, "DO") != pad_net(leds[k + 1].ref, "DI"):
            bad.append(f"{leds[k].ref}.DO !-> {leds[k+1].ref}.DI")
    print(f"[2] Datenkette {len(leds)-1} Uebergange: " + ("OK" if not bad else "FEHLER " + "; ".join(bad[:5])))
    ok &= not bad
    # DIN-/DOUT-Anschlusspads an Kettenenden
    din_ok = any(it[3].startswith("corner DIN") and find(i) == pad_net(leds[0].ref, "DI")
                 for i, it in enumerate(copper))
    dout_ok = any(it[3].startswith("corner DOUT") and find(i) == pad_net(leds[-1].ref, "DO")
                  for i, it in enumerate(copper))
    print(f"[2b] DIN-Pad an L1.DI: {'OK' if din_ok else 'FEHLER'} | "
          f"DOUT-Pad an L64.DO: {'OK' if dout_ok else 'FEHLER'}")
    ok &= din_ok and dout_ok

    # --- Check 3: Schienen-Netze alternieren
    rails = sorted(pg["rails_top"], key=lambda r: r["y"])
    seq = [r["net"] for r in rails]
    alt = all(seq[i] != seq[i + 1] for i in range(len(seq) - 1))
    print(f"[3] {len(rails)} F.Cu-Schienen Netze {seq[:4]}...: " + ("OK alternierend" if alt else "FEHLER"))
    ok &= alt

    # --- Check 4: B.Cu-Rails mit Stitching-Vias verbunden
    for net in ("GND", "VCC"):
        br = [i for i, it in enumerate(copper) if it[3] == f"rail_bottom {net}"]
        sv = [i for i, it in enumerate(copper) if it[3] == "stitch via" and it[1] == net]
        conn = all(any(find(s) == find(b) for s in sv) for b in br)
        n_stitch = len({(copper[i][2][0], copper[i][2][1]) for i in sv})
        print(f"[4] B.Cu {net}-Rail(s) an {n_stitch} Stitch-Vias angebunden: {'OK' if conn else 'FEHLER'}")
        ok &= conn

    print("\nGESAMT:", "OK" if ok else "FEHLER")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
