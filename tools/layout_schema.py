"""
Layout-Schema (Review-Grafik, kein Fertigungsartefakt).

Zwei 500x500-PNG:
  layout_front.png  LED-Matrix 8x8: horizontale Serpentine.
                    L1 oben-links, L8 oben-rechts, Zeile fuer Zeile
                    abwaerts mit Richtungwechsel. Bei gerader
                    Zeilenzahl endet L64 unten-links.
  layout_back.png   Rueckseite: zwei vertikale Stromschienen GND + VCC
                    MITTIG nebeneinander (treffen sich in der Mitte mit
                    Mindestabstand GAP), Breite je = W/3.
                    6 Anschlusspads: DIN (oben, zu L1), DOUT (unten,
                    zu L64 - Seite folgt der Kettenrichtung), je
                    GND+VCC-Pad oben und unten (Module verketten).

Massstab: 8x8 @ Pitch 3.0 mm -> 24.0 x 24.0 mm.
"""
from __future__ import annotations

import os
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from footprint import footprint_from_data

_FP = footprint_from_data("C41413180")          # echte Pad-Geometrie

COLS = ROWS = 8
PITCH = 3.0
W = H = COLS * PITCH
MARGIN = 14
PX = (500.0 - 2 * MARGIN) / W      # Pixel pro mm (inkl. Rand)
GAP = 1.0            # mm Mindestabstand zwischen den beiden Schienen

BG = (250, 250, 245)
BOARD = (245, 235, 170)
EDGE = (60, 60, 60)
FCU = (210, 40, 40)
BCU = (40, 90, 210)
SILK = (30, 30, 30)
CHAIN = (0, 120, 0)


def font(size):
    for p in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def mm(v):
    return MARGIN + v * PX


def yflip(v):
    """Platinen-Y (nach oben) -> Bild-Y (nach unten)."""
    return MARGIN + (H - v) * PX


def new_canvas():
    img = Image.new("RGB", (500, 500), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([mm(0), yflip(H), mm(W), yflip(0)], fill=BOARD,
                outline=EDGE, width=2)
    return img, d


def led_centers():
    """LED-Zentren (row, col); row 0 = OBEN (L1 oben-links)."""
    return {(row, col): ((col + 0.5) * PITCH, H - (row + 0.5) * PITCH)
            for row in range(ROWS) for col in range(COLS)}


ROT_MODE = "90"   # "90" = Zeilen 2,4,.. relativ -90°, "180" = relativ 180°
BASE_ROT = 180    # Grunddrehung: DI-Pad oben-links -> DIN oben-links


def row_rot(row):
    """Footprint-Rotation pro Zeile: Grunddrehung BASE_ROT (DIN oben-
    links), Zeilen 2,4,.. (ungerade Indizes) relativ dazu gedreht."""
    if ROT_MODE == "90":
        return BASE_ROT if row % 2 == 0 else BASE_ROT - 90
    return BASE_ROT if row % 2 == 0 else BASE_ROT - 180


def pad_offset(sig, row):
    """Pad-Offset relativ zur LED-Mitte, Zeilenrotation angewendet."""
    import math
    p_ = {q.signal: q for q in _FP.pads}[sig]
    a = math.radians(row_rot(row))
    c, s = math.cos(a), math.sin(a)
    return (p_.x * c - p_.y * s, p_.x * s + p_.y * c)


def chain_order():
    """Horizontale Serpentine: L1 oben-links, L8 oben-rechts, dann
    Zeile fuer Zeile abwaerts mit Richtungwechsel. Bei 8 Zeilen endet
    L64 unten-links (L57 unten-rechts)."""
    order = []
    for row in range(ROWS):
        cols = range(COLS) if row % 2 == 0 else range(COLS - 1, -1, -1)
        order += [(row, col) for col in cols]
    return order


# ---------------------------------------------------------------------------
VCC_C = (210, 40, 40)
GND_C = (30, 80, 180)


def gap_net(row_above):
    """Net der Lücke unter Zeile row_above: das Power-Pad dieser Zeile,
    das nach unten zeigt, bestimmt ihn (GND/VCC)."""
    for sig in ("GND", "VDD"):
        _, oy = pad_offset(sig, row_above)
        if oy < 0:
            return sig
    return None


def edge_net(row, direction):
    """Net der Randzone: Power-Pad der Randzeile, das nach aussen
    (direction=+1 oben / -1 unten) zeigt."""
    for sig in ("GND", "VDD"):
        _, oy = pad_offset(sig, row)
        if oy * direction > 0:
            return sig
    return None


def pad_edge(row, sig, direction):
    """y-Offset und x-Offset des Power-Pads, das in einer Zeile nach
    aussen (direction) zeigt."""
    ox, oy = pad_offset(sig, row)
    ph = _FP.pads[0].height
    pw = _FP.pads[0].width
    if abs(row_rot(row)) == 90:
        ph, pw = pw, ph
    return ox, oy + (ph / 2) * direction


def facing_pad_xspan(row, direction):
    """x-Spanne (min-links, max-rechts) aller Power-Pads einer Zeile,
    die nach direction (=-1 unten / +1 oben) zeigen. Schienen enden an
    der aeusseren Padkante - davor ist Platz fuer die Datenfuehrung."""
    sig = [s for s in ("GND", "VDD")
           if pad_offset(s, row)[1] * direction > 0][0]
    ox, _ = pad_offset(sig, row)
    pw = _FP.pads[0].width
    ph = _FP.pads[0].height
    half = (ph if abs(row_rot(row)) == 90 else pw) / 2
    lefts = [(c + 0.5) * PITCH + ox - half for c in range(COLS)]
    rights = [(c + 0.5) * PITCH + ox + half for c in range(COLS)]
    return min(lefts), max(rights)


def draw_power_rails(d):
    """Prinzip (nicht pixelgenau): EINE horizontale Schiene pro
    Reihenlücke, abwechselnd GND/VCC. Zeilen sind alternierend gedreht
    (ROT_MODE), sodass in jeder Lücke zwei gleichartige Power-Pads
    aufeinander zeigen; die Schiene sitzt mittig mit Clearance und
    stubt kurz zu beiden Pads. Randzonen = Net der aussen zeigenden
    Power-Pads der Randzeilen. Weisse Kreise = Stich-Vias."""
    centers = led_centers()
    gnd_r, vcc_r = rail_rects()
    col_of = {"GND": GND_C, "VDD": VCC_C}

    def rail(y, net, row_above):
        """Schiene endet an den aeusseren Padkanten der gespeisten
        Zeilen (nicht an der Boardkante) -> Datenpfad bleibt frei."""
        color = col_of[net]
        x0, x1 = None, None
        if row_above >= 0:
            a0, a1 = facing_pad_xspan(row_above, -1)
            x0, x1 = a0, a1
        if row_above + 1 < ROWS:
            b0, b1 = facing_pad_xspan(row_above + 1, +1)
            x0 = b0 if x0 is None else min(x0, b0)
            x1 = b1 if x1 is None else max(x1, b1)
        d.line([mm(x0), yflip(y), mm(x1), yflip(y)], fill=color, width=3)
        for col in range(COLS):
            xc = (col + 0.5) * PITCH
            if row_above >= 0:
                sig = [s for s in ("GND", "VDD")
                       if pad_offset(s, row_above)[1] < 0][0]
                ox, ye = pad_edge(row_above, sig, -1)
                y_up = centers[(row_above, 0)][1] + ye
                d.line([mm(xc + ox), yflip(y), mm(xc + ox), yflip(y_up)],
                       fill=color, width=2)
            if row_above + 1 < ROWS:
                nxt = row_above + 1
                sig = [s for s in ("GND", "VDD")
                       if pad_offset(s, nxt)[1] > 0][0]
                ox, ye = pad_edge(nxt, sig, +1)
                y_dn = centers[(nxt, 0)][1] + ye
                d.line([mm(xc + ox), yflip(y), mm(xc + ox), yflip(y_dn)],
                       fill=color, width=2)

    def stitch(y, color, rx):
        """3 Stich-Vias pro Schiene, 2 mm Abstand, mittig um die
        B.Cu-Schiene (passt in 8mm-Schiene: 5.5/7.5/9.5)."""
        for dx_ in (-2.0, 0.0, 2.0):
            vx = rx + dx_
            d.ellipse([mm(vx - 0.35), yflip(y + 0.35), mm(vx + 0.35),
                       yflip(y - 0.35)], fill=(255, 255, 255),
                      outline=color, width=2)

    # schwacher Umriss der B.Cu-Schienen (Zielbezug der Stich-Vias)
    for rect in (gnd_r, vcc_r):
        d.rectangle([mm(rect[0]), yflip(rect[3]), mm(rect[2]), yflip(rect[1])],
                    outline=(150, 180, 230), width=1)

    for r in range(ROWS - 1):
        y_mid = centers[(r, 0)][1] - PITCH / 2.0
        net = gap_net(r)
        rail(y_mid, net, r)
        rx = ((gnd_r[0] + gnd_r[2]) / 2.0 if net == "GND"
              else (vcc_r[0] + vcc_r[2]) / 2.0)
        stitch(y_mid, col_of[net], rx)
    # Randzonen
    net_top = edge_net(0, +1)
    rail(H - 0.35, net_top, -1)
    stitch(H - 0.35, col_of[net_top],
           (gnd_r[0] + gnd_r[2]) / 2.0 if net_top == "GND"
           else (vcc_r[0] + vcc_r[2]) / 2.0)
    net_bot = edge_net(ROWS - 1, -1)
    rail(0.35, net_bot, ROWS - 1)
    stitch(0.35, col_of[net_bot],
           (gnd_r[0] + gnd_r[2]) / 2.0 if net_bot == "GND"
           else (vcc_r[0] + vcc_r[2]) / 2.0)


# ---------------------------------------------------------------------------
def draw_front():
    img, d = new_canvas()
    centers = led_centers()
    body_w, body_h = _FP.body_width, _FP.body_height
    pads = {p_.signal: p_ for p_ in _FP.pads}
    dx, dy = abs(pads["DI"].x), abs(pads["DI"].y)
    pad_w, pad_h = pads["DI"].width, pads["DI"].height

    draw_power_rails(d)          # Schienen zuerst, Pads darueber

    import math
    for row in range(ROWS):
        # Zeilen alternierend gedreht (ROT_MODE): dadurch zeigen in jeder
        # Lücke zwei gleichartige Power-Pads aufeinander -> eine Schiene
        # pro Lücke, abwechselnd GND/VCC.
        rot = row_rot(row)
        bw, bh = (body_h, body_w) if abs(rot) == 90 else (body_w, body_h)
        for col in range(COLS):
            x, y = centers[(row, col)]
            d.rectangle([mm(x - bw / 2), yflip(y + bh / 2),
                         mm(x + bw / 2), yflip(y - bh / 2)],
                        fill=(255, 255, 255), outline=SILK, width=1)
            for sig in ("DO", "VDD", "GND", "DI"):
                ox, oy = pad_offset(sig, row)
                cx, cy = x + ox, y + oy
                pw, ph = (pad_h, pad_w) if abs(rot) == 90 else (pad_w, pad_h)
                d.rectangle([mm(cx - pw / 2), yflip(cy + ph / 2),
                             mm(cx + pw / 2), yflip(cy - ph / 2)],
                            fill=FCU)

    # Datenpfad (zuletzt, gut sichtbar): DO links oben -> DI rechts unten
    order = chain_order()
    pts = []
    for (row, col) in order:
        x, y = centers[(row, col)]
        ox, oy = pad_offset("DO", row)
        pts.append((x + ox, y + oy))
        ox, oy = pad_offset("DI", row)
        pts.append((x + ox, y + oy))
    flat = []
    for i in range(0, len(pts) - 3, 2):
        ox, oy = pts[i]          # DO dieser LED
        ix, iy = pts[i + 3]      # DI der naechsten LED
        if abs(ox - ix) < 0.01:
            seg = [(ox, oy), (ix, iy)]
        else:
            mid_y = (oy + iy) / 2.0
            seg = [(ox, oy), (ox, mid_y), (ix, mid_y), (ix, iy)]
        flat += [(mm(px), yflip(py)) for (px, py) in seg]
    d.line(flat, fill=CHAIN, width=2)

    # DIN/DOUT: je 1 Via vom Front-Datenpfad zum Anschlusspad (B.Cu)
    din_via = (0.95, H - 0.6)
    dout_via = (0.95, 0.6)
    x0, y0 = pts[1]          # DI-Pad der ersten LED
    d.line([(mm(x0), yflip(y0)), (mm(din_via[0]), yflip(din_via[1]))],
           fill=CHAIN, width=2)
    x1, y1 = pts[-2]         # DO-Pad der letzten LED
    d.line([(mm(x1), yflip(y1)), (mm(x1), yflip(dout_via[1])),
            (mm(dout_via[0]), yflip(dout_via[1]))], fill=CHAIN, width=2)
    for (vx, vy) in (din_via, dout_via):
        d.ellipse([mm(vx - 0.35), yflip(vy + 0.35), mm(vx + 0.35),
                   yflip(vy - 0.35)], fill=(255, 255, 255), outline=CHAIN,
                  width=2)
        d.ellipse([mm(vx - 0.1), yflip(vy + 0.1), mm(vx + 0.1),
                   yflip(vy - 0.1)], fill=CHAIN)

    f = font(11)
    for idx, (row, col) in enumerate(order, start=1):
        x, y = centers[(row, col)]
        d.text((mm(x) - 8, yflip(y) - 6), f"L{idx}", fill=SILK, font=f)

    f2 = font(13)
    d.text((mm(din_via[0] + 0.6), yflip(din_via[1]) - 6), "DIN",
           fill=CHAIN, font=f2)
    d.text((mm(dout_via[0] + 0.6), yflip(dout_via[1]) - 6), "DOUT",
           fill=CHAIN, font=f2)
    d.text((mm(0.3), 2), "VORDERSEITE (F.Cu) - EINE Schiene pro Luecke "
           "(altern. GND/VCC), Zeilen altern. %s gedreht, Kreise = "
           "Stich-Vias" % ("-90/+90" if ROT_MODE == "90" else "0/180"),
           fill=SILK, font=font(10))
    return img


# ---------------------------------------------------------------------------
def rail_rects():
    """Beide Schienen mittig, GND links VCC rechts, Abstand GAP."""
    rail_w = W / 3.0
    x0 = (W - (2 * rail_w + GAP)) / 2.0
    gnd = (x0, 0.2, x0 + rail_w, H - 0.2)
    vcc = (x0 + rail_w + GAP, 0.2, x0 + 2 * rail_w + GAP, H - 0.2)
    return gnd, vcc


def draw_back():
    img, d = new_canvas()
    gnd, vcc = rail_rects()
    for rect in (gnd, vcc):
        d.rectangle([mm(rect[0]), yflip(rect[3]), mm(rect[2]), yflip(rect[1])],
                    fill=BCU)

    def pad_rect(rect, label, lf):
        d.rectangle([mm(rect[0]), yflip(rect[3]), mm(rect[2]), yflip(rect[1])],
                    fill=(255, 255, 255), outline=EDGE, width=2)
        d.text((mm(rect[0]) + 2, yflip(rect[3]) + 2), label, fill=EDGE,
               font=lf)

    # GND/VCC-Pads oben und unten (randbuendig auf den Schienen)
    ph = 1.0
    pad_rect((gnd[0], H - 0.2 - ph, gnd[2], H - 0.2), "GND", font(12))
    pad_rect((vcc[0], H - 0.2 - ph, vcc[2], H - 0.2), "VCC", font(12))
    pad_rect((gnd[0], 0.2, gnd[2], 0.2 + ph), "GND", font(12))
    pad_rect((vcc[0], 0.2, vcc[2], 0.2 + ph), "VCC", font(12))

    # DIN oben (zu L1) / DOUT unten (zu L64): Seite folgt der Lage des
    # DO-Pads der letzten Zeile (durch die Rotationen).
    last_row, last_col = chain_order()[-1]
    do_x, _ = pad_offset("DO", last_row)
    din = (0.2, H - 0.2 - 0.8, 1.7, H - 0.2)
    if do_x < 0:
        dout = (0.2, 0.2, 1.7, 1.0)
    else:
        dout = (W - 1.7, 0.2, W - 0.2, 1.0)
    for p in (din, dout):
        d.rectangle([mm(p[0]), yflip(p[3]), mm(p[2]), yflip(p[1])],
                    fill=BCU, outline=EDGE, width=1)
    # Stitch-Vias der Front-Schienen: Lage gespiegelt einzeichnen
    # (3 pro Schiene, 2 mm Abstand, mittig auf der B.Cu-Schiene)
    centers = led_centers()
    for rr in range(ROWS - 1):
        net = gap_net(rr)
        y = centers[(rr, 0)][1] - PITCH / 2.0
        rx = ((gnd[0] + gnd[2]) / 2.0 if net == "GND"
              else (vcc[0] + vcc[2]) / 2.0)
        for dxx in (-2.0, 0.0, 2.0):
            d.ellipse([mm(rx + dxx - 0.3), yflip(y + 0.3),
                       mm(rx + dxx + 0.3), yflip(y - 0.3)],
                      fill=(255, 255, 255), outline=EDGE, width=2)
            d.ellipse([mm(rx + dxx - 0.08), yflip(y + 0.08),
                       mm(rx + dxx + 0.08), yflip(y - 0.08)], fill=EDGE)
    for rr, y in ((0, H - 0.35), (ROWS - 1, 0.35)):
        net = edge_net(rr, +1 if y > H / 2 else -1)
        rx = ((gnd[0] + gnd[2]) / 2.0 if net == "GND"
              else (vcc[0] + vcc[2]) / 2.0)
        for dxx in (-2.0, 0.0, 2.0):
            d.ellipse([mm(rx + dxx - 0.3), yflip(y + 0.3),
                       mm(rx + dxx + 0.3), yflip(y - 0.3)],
                      fill=(255, 255, 255), outline=EDGE, width=2)
            d.ellipse([mm(rx + dxx - 0.08), yflip(y + 0.08),
                       mm(rx + dxx + 0.08), yflip(y - 0.08)], fill=EDGE)

    # Via-Symbol: Datenpad hat je 1 Via zur Vorderseite (Datenkette)
    for p_ in (din, dout):
        vx, vy = (p_[0] + p_[2]) / 2.0, (p_[1] + p_[3]) / 2.0
        d.ellipse([mm(vx - 0.3), yflip(vy + 0.3), mm(vx + 0.3),
                   yflip(vy - 0.3)], fill=(255, 255, 255), outline=EDGE,
                  width=2)
        d.ellipse([mm(vx - 0.08), yflip(vy + 0.08), mm(vx + 0.08),
                   yflip(vy - 0.08)], fill=EDGE)
    d.text((mm(din[0]) + 1, yflip(din[3]) + 1), "DIN", fill=(255, 255, 255),
           font=font(10))
    d.text((mm(dout[0]) + 1, yflip(dout[1]) - 14), "DOUT",
           fill=EDGE, font=font(10))

    f = font(14)
    d.text((mm(gnd[0] + 1.6), yflip(H / 2)),
           "GND-SCHIENE\n(B.Cu)\nBreite = W/3", fill=(255, 255, 255), font=f)
    d.text((mm(vcc[0] + 1.6), yflip(H / 2)),
           "VCC-SCHIENE\n(B.Cu)\nBreite = W/3", fill=(255, 255, 255), font=f)
    # Abstandsmarkierung in der Mitte
    gx = (gnd[2] + vcc[0]) / 2.0
    d.text((mm(gx) - 14, yflip(H / 2) - 30), f"GAP {GAP:.1f}mm",
           fill=SILK, font=font(10))
    d.text((mm(0.3), 2), "RUECKSEITE (B.Cu) - Schienen mittig + 6 Anschlusspads",
           fill=SILK, font=font(12))
    return img


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output"
    ROT_MODE = "90"
    draw_front().save(f"{out}/layout_front.png")
    ROT_MODE = "180"
    draw_front().save(f"{out}/layout_front_180.png")
    ROT_MODE = "90"
    draw_back().save(f"{out}/layout_back.png")
    print("written: layout_front.png (±90), layout_front_180.png, "
          "layout_back.png")
