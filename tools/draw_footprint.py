"""
Werkzeug: grafischer Footprint-Check C41413180 (XL-1615RGBC-WS2812B-S).

Zeichnet aus den Rohtaten (data/C41413180/raw.json, EasyEDA-Package)
massstabsgetreu:
  P1: Footprint Rotation 0 (Gerber-Koordinaten) mit Bemaessung
  P2: Rotation 180 (Grunddrehung, DI oben-links)
  P3: Rotation 90 (ungerade visuelle Reihen)
  P4: Einbettung ins 3.0-mm-Raster: reale Luecken quer/senkrecht

Ausgabe: output/footprint_check.png
"""
import json
import math
from PIL import Image, ImageDraw

S = 0.254  # EasyEDA-Unit -> mm


def load_raw(lcsc="C41413180"):
    raw = json.loads(open(f"data/{lcsc}/raw.json", encoding="utf-8").read())
    ds = raw["result"]["packageDetail"]["dataStr"]
    ox, oy = ds["head"]["x"], ds["head"]["y"]
    pads, body = [], None
    for item in ds["shape"]:
        f = str(item).split("~")
        if f[0] == "PAD":
            cx, cy = float(f[2]) - ox, float(f[3]) - oy
            w, h = float(f[4]), float(f[5])
            pads.append({"num": f[9], "x": cx * S, "y": cy * S,
                         "w": w * S, "h": h * S})
        elif f[0] == "SOLIDREGION" and f[1] == "99":
            nums = [float(t) for t in f[3].replace("M ", " ")
                    .replace(" L ", " ").replace(" Z", " ").split()]
            pts = list(zip(nums[0::2], nums[1::2]))
            xs = [p[0] - ox for p in pts]
            ys = [p[1] - oy for p in pts]
            body = (min(xs) * S, min(ys) * S, max(xs) * S, max(ys) * S)
    # Pin-Namen aus der Symbol-Sicht (footprint.json ist identisch)
    fpj = json.loads(open(f"data/{lcsc}/footprint.json",
                          encoding="utf-8").read())
    sig = {}
    for p in fpj["pads"]:
        key = (round(p["x"], 3), round(p["y"], 3))
        sig[key] = p["signal"]
    for p in pads:
        key = (round(p["x"], 3), round(p["y"], 3))
        p["signal"] = sig.get(key, "?")
    # Y-Flip: EasyEDA-Screen (Y runter) -> Gerber (Y hoch), wie Loader
    for p in pads:
        p["y"] = -p["y"]
    body = (body[0], -body[3], body[2], -body[1])
    return pads, body


def rot(p, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return p[0] * c - p[1] * s, p[0] * s + p[1] * c


def main():
    pads, body = load_raw()
    PX = 46  # px/mm
    M = 60   # Rand im Panel
    PW = PH = 300
    CW, CH = 2 * (PW + M), 2 * (PH + M)
    img = Image.new("RGB", (CW, CH), "white")
    d = ImageDraw.Draw(img)

    def panel(ox, oy, title, deg, grid=False):
        d.rectangle([ox, oy, ox + PW, oy + PH], outline="black")
        d.text((ox + 8, oy + 6), title, fill="black")
        cx, cy = ox + M + PW // 2 - 30, oy + M + PH // 2 - 30

        def X(x):
            return cx + x * PX

        def Y(y):
            return cy - y * PX   # Gerber: Y nach oben

        if grid:
            for gx in (-1.5, 1.5):
                d.rectangle([X(gx - 1.5), Y(1.5), X(gx + 1.5), Y(-1.5)],
                            outline=(200, 200, 200))
        # Body (Gehaeuse) rot, 2 px
        bx0, by0, bx1, by1 = body
        if int(deg) % 180 == 90:
            bx0, by0, bx1, by1 = -by1, -bx1, -by0, -bx0
        for seg in _rect_segs(bx0, by0, bx1, by1):
            d.line([seg[0], seg[1]], fill=(255, 0, 0), width=2)
        # Kupfer-Aussenkontur
        ex = max(abs(p["x"]) + p["w"] / 2 for p in pads)
        ey = max(abs(p["y"]) + p["h"] / 2 for p in pads)
        if int(deg) % 180 == 90:
            ex, ey = ey, ex
        d.rectangle([X(-ex), Y(ey), X(ex), Y(-ey)],
                    outline=(0, 0, 255), width=1)
        # Pads
        for p in pads:
            px, py = rot((p["x"], p["y"]), deg)
            w, h = (p["h"], p["w"]) if int(deg) % 180 == 90 \
                else (p["w"], p["h"])
            d.rectangle([X(px - w / 2), Y(py + h / 2),
                         X(px + w / 2), Y(py - h / 2)],
                        fill=(120, 120, 120), outline="black")
            d.text((X(px) - 8, Y(py) - 5), p["signal"], fill="white")
        return cx, cy, X, Y

    def _rect_segs(x0, y0, x1, y1):
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        return [(pts[i], pts[i + 1]) for i in range(4)]

    # P1: Rotation 0
    cx, cy, X, Y = panel(M, M, "P1  Rotation 0 (Gerber)", 0)
    ex = max(abs(p["x"]) + p["w"] / 2 for p in pads)
    ey = max(abs(p["y"]) + p["h"] / 2 for p in pads)
    d.text((M + 8, M + 22), f"Kupfer-Aussenkontur: {2*ex:.2f} x {2*ey:.2f} mm",
           fill="blue")
    d.text((M + 8, M + 36),
           f"Gehaeuse (rot): {body[2]-body[0]:.2f} x {body[3]-body[1]:.2f} mm",
           fill="red")
    d.text((M + 8, M + PH - 30), "Pad 0.45 x 0.65 mm", fill="black")
    d.text((M + 8, M + PH - 16), "Pad-Mitten: +/-0.625 x +/-0.475 mm",
           fill="black")

    # P2: Rotation 180
    panel(M + PW + M, M, "P2  Rotation 180 (Grunddrehung, DI oben-links)",
          180)

    # P3: Rotation 90
    cx, cy, X, Y = panel(M, M + PH + M,
                         "P3  Rotation 90 (ungerade Reihen)", 90)
    d.text((M + 8, M + PH + 22),
           "Kupfer rotiert mit: 1.60 x 1.70 mm (Hoehe!)", fill="blue")

    # P4: Raster 3.0 mm
    cx, cy, X, Y = panel(M + PW + M, M + PH + M,
                         "P4  Raster 3.0 mm: reale Luecken", 0, grid=True)
    # zwei LEDs nebeneinander (rot 180) + eine darunter (rot 90)
    for (gx, gy, deg) in ((-1.5, 1.5, 180), (1.5, 1.5, 180),
                          (-1.5, -1.5, 90)):
        for p in pads:
            px, py = rot((p["x"], p["y"]), deg)
            w, h = (p["h"], p["w"]) if int(deg) % 180 == 90 \
                else (p["w"], p["h"])
            d.rectangle([X(gx + px - w / 2), Y(gy + py + h / 2),
                         X(gx + px + w / 2), Y(gy + py - h / 2)],
                        fill=(120, 120, 120))
    d.text((M + PW + M + 8, M + PH + M + 22),
           "quer:   3.0 - 0.85 - 0.85 = 1.30 mm", fill="black")
    d.text((M + PW + M + 8, M + PH + M + 36),
           "senkrecht (180/90 gemischt): "
           "3.0 - 0.80 - 0.85 = 1.35 mm", fill="black")

    img.save("output/footprint_check.png")
    print("geschrieben: output/footprint_check.png")
    print(f"Pads: {[(p['signal'], p['w'], p['h'], p['x'], p['y']) for p in pads]}")
    print(f"Body: {body}")
    print(f"Kupfer: {2*ex:.3f} x {2*ey:.3f} mm")


if __name__ == "__main__":
    main()
