# Koordinatensysteme im LED-Matrix-Generator

> **Unser System:** Gerber RS-274X — Ursprung (0,0) links-unten, Y wächst nach oben.


## 1. Unser System: Gerber RS-274X (das Ziel)

```
        Y ↑
          │
    (0,h) ┌──────────┐ (w,h)
          │  Board   │
          │          │
    (0,0) └──────────┘ (w,0)
          └────────────→ X

    Ursprung:  links-unten
    Einheit:   mm
    Auflösung: 1/1.000.000 mm  (%FSLAX46Y46*%)
```

**Edge_Cuts-Beispiel:**
```gerber
X0Y0D02*          → Move nach (0,0)
X30600000Y0D01*   → Draw nach (30.6, 0)
X30600000Y20000000D01* → Draw nach (30.6, 20.0)
X0Y20000000D01*   → Draw nach (0, 20.0)
X0Y0D01*          → Draw zurück nach (0,0)
```


## 2. EasyEDA Footprint-Daten (Quellformat)

```
        Y ↓ (Screen)
    (0,0) ┌──────────┐
          │ Footprint │
          │  (Canvas) │
          └──────────┘
          └────────────→ X

    Ursprung:  links-oben  (Screen-Koordinaten)
    Einheit:   1 unit = 0.254 mm = 10 mil
    Y:          wächst nach UNTEN
```

**Beispiel C41413180 (`footprint.json`):**
```json
{
  "pads": [
    {"number":"1","x":-0.625,"y":-0.475,"signal":"DO"},
    {"number":"2","x": 0.625,"y":-0.475,"signal":"VDD"},
    {"number":"3","x":-0.625,"y": 0.475,"signal":"GND"},
    {"number":"4","x": 0.625,"y": 0.475,"signal":"DI"}
  ]
}
```

**Konvertierung → Gerber:**
- `gerber_y = -easyeda_y`  (Y spiegeln)
- `gerber_x = easyeda_x`   (X bleibt)


## 3. Footprint-Koordinaten (intern, nach Konvertierung)

```
        Y ↑ (Gerber)
          │
    +y  ──┼──
          │  LED-Mitte = (0,0)
    ──────┼──────→ X
          │
    -y    │

    Ursprung:  LED-Mittelpunkt
    Rotation:  CCW (positiv = gegen Uhrzeigersinn)
```

**SK9822-EC20 (6-Pin) nach Y-Flip:**
```
          Y↑
          │
  DO(-0.707, +0.800)   CO(+0.707, +0.800)   ← oben
  GND(-0.707,  0.000)  VDD(+0.707,  0.000)  ← mitte
  DI(-0.707, -0.800)   CI(+0.707, -0.800)   ← unten
          │
          └──────────→ X
```

**XL-1615RGBC (4-Pin) nach Y-Flip:**
```
          Y↑
          │
  DO(-0.625, +0.475)   VDD(+0.625, +0.475)  ← oben  (Pin1, Pin2)
  GND(-0.625, -0.475)  DI(+0.625, -0.475)   ← unten (Pin3, Pin4)
          │
          └──────────→ X
```


## 4. Rotation (CCW, positiv)

| Winkel | Formel | Effekt |
|---|---|---|
| 0° | `x'=x, y'=y` | unverändert |
| 90° CCW | `x'=-y, y'=x` | links oben → links unten |
| 270° CCW | `x'=y, y'=-x` | rechts oben → links oben |
| 180° CCW | `x'=-x, y'=-y` | komplett gedreht |

**Reihen-Muster:**
- Reihe 0 (gerade, →): 270° CCW  → DI links, DO rechts
- Reihe 1 (ungerade, ←): 90° CCW  → DI rechts, DO links


## 5. Absolute Board-Position

```
    led_abs_x = led_x + pad_x·cos(rot) - pad_y·sin(rot)
    led_abs_y = led_y + pad_x·sin(rot) + pad_y·cos(rot)
```

Beispiel D1 (SK9822, Reihe 0, rot=270°):
```
    DO: (8.1 -0.707·0 - 0.800·(-1), 2.5 -0.707·(-1) + 0.800·0)
      = (8.1 + 0.800, 2.5 + 0.707)
      = (8.900, 3.207)
```


## 6. pygerber (Nur im Renderer)

```
        Y ↓ (PIL Image)
    (0,0) ┌──────────┐
          │  Image   │
          │          │
          └──────────┘
          └────────────→ X

    Ursprung:  links-oben  (Grafik-Konvention)
    Y:          wächst nach UNTEN
```

**Konvertierung Gerber → pygerber-Pixel (automatisch):**
```
    px = (gerber_x - info.min_x) * dpmm
    py = (gerber_y - info.min_y) * dpmm   ← pygerber intern: min_y → row 0
```

**⚠️ Für manuell gezeichnete Elemente (Drills, Pin-1-Marker):**
pygerber hat das Bild bereits Y-geflippt gerendert. Daher müssen
manuell auf das Bild gezeichnete Koordinaten ebenfalls Y-geflippt werden:

```python
# Drills (in _draw_drill_on_image):
cy = round((info.max_y_mm - hy) * dpmm)

# Pin-1-Marker (in _draw_pin1_markers):
iy = img.size[1] - 1 - round((py - global_min_y) * dpmm)
```

> **Merke:** pygerber flipped NUR beim Rendern. Die Gerber-Dateien selbst
> sind korrekt (Gerber-Konvention, Y nach oben). Der Flip ist ein
> reines Anzeige-Thema im PNG-Preview.


## 7. Übersicht: Konvertierungskette

```
  EasyEDA (Y↓)            Gerber (Y↑)            pygerber (Y↓)
  ─────────────           ───────────            ─────────────
  footprint.json    →    interner Footprint    →    PNG-Bild
  y = raw.y               y = -raw.y               px = (x-min_x)·dpmm
                                                   py = (y-min_y)·dpmm
                                                   [pygerber flipped Y
                                                    automatisch]
```


## 8. Checkliste bei neuen LED-Typen

1. ✅ `fetch_component.py` lädt Daten von EasyEDA (Y↓)
2. ✅ `footprint_from_data()` negiert Y: `y = -raw.y` → Gerber-System (Y↑)
3. ✅ `pad_pos()` rotiert und addiert LED-Position → absolute Board-Koordinaten
4. ✅ Gerber-Writer schreibt RS-274X (Y↑)
5. ✅ Renderer zeichnet Drills + Marker Y-geflippt ins pygerber-Bild


## 9. Beispiel: 6×4 Matrix (Serpentine)

**Parameter:** cols=6, rows=4, pitch=5.0mm, margin=0

```
  Y ↑  (Gerber-Koordinaten)
      │
 20.0 ┌────┬────┬────┬────┬────┬────┐
      │ D1 │ D2 │ D3 │ D4 │ D5 │ D6 │  ← Reihe 0 (→)  rot=270°
 17.5 │ •→ │ •→ │ •→ │ •→ │ •→ │ •← │
      ├────┼────┼────┼────┼────┼────┤
      │D12 │D11 │D10 │ D9 │ D8 │ D7 │  ← Reihe 1 (←)  rot=90°
 12.5 │ •← │ •← │ •← │ •← │ •← │ •→ │
      ├────┼────┼────┼────┼────┼────┤
      │D13 │D14 │D15 │D16 │D17 │D18 │  ← Reihe 2 (→)  rot=270°
  7.5 │ •→ │ •→ │ •→ │ •→ │ •→ │ •← │
      ├────┼────┼────┼────┼────┼────┤
      │D24 │D23 │D22 │D21 │D20 │D19 │  ← Reihe 3 (←)  rot=90°
  2.5 │ •← │ •← │ •← │ •← │ •← │ •→ │
      └────┴────┴────┴────┴────┴────┘
    0 │    │    │    │    │    │    │
      └────┴────┴────┴────┴────┴────→ X
    0    2.5  7.5 12.5 17.5 22.5 27.5 30.0
```

**Datenkette (Serpentine):**
```
  D1 → D2 → D3 → D4 → D5 → D6
                            ↓
  D12 ← D11 ← D10 ← D9 ← D8 ← D7
   ↓
  D13 → D14 → D15 → D16 → D17 → D18
                                  ↓
  D24 ← D23 ← D22 ← D21 ← D20 ← D19
```

**LED-Positionen (Referenz):**

| Ref | idx | col | row | x (mm) | y (mm) | rot | Richtung |
|-----|-----|-----|-----|--------|--------|-----|----------|
| D1  | 0   | 0   | 0   | 2.5    | 17.5   | 270° | → |
| D2  | 1   | 1   | 0   | 7.5    | 17.5   | 270° | → |
| D3  | 2   | 2   | 0   | 12.5   | 17.5   | 270° | → |
| D4  | 3   | 3   | 0   | 17.5   | 17.5   | 270° | → |
| D5  | 4   | 4   | 0   | 22.5   | 17.5   | 270° | → |
| D6  | 5   | 5   | 0   | 27.5   | 17.5   | 270° | → |
| D7  | 6   | 5   | 1   | 27.5   | 12.5   | 90°  | ← |
| D8  | 7   | 4   | 1   | 22.5   | 12.5   | 90°  | ← |
| D9  | 8   | 3   | 1   | 17.5   | 12.5   | 90°  | ← |
| D10 | 9   | 2   | 1   | 12.5   | 12.5   | 90°  | ← |
| D11 | 10  | 1   | 1   | 7.5    | 12.5   | 90°  | ← |
| D12 | 11  | 0   | 1   | 2.5    | 12.5   | 90°  | ← |
| D13 | 12  | 0   | 2   | 2.5    | 7.5    | 270° | → |
| D14 | 13  | 1   | 2   | 7.5    | 7.5    | 270° | → |
| D15 | 14  | 2   | 2   | 12.5   | 7.5    | 270° | → |
| D16 | 15  | 3   | 2   | 17.5   | 7.5    | 270° | → |
| D17 | 16  | 4   | 2   | 22.5   | 7.5    | 270° | → |
| D18 | 17  | 5   | 2   | 27.5   | 7.5    | 270° | → |
| D19 | 18  | 5   | 3   | 27.5   | 2.5    | 90°  | ← |
| D20 | 19  | 4   | 3   | 22.5   | 2.5    | 90°  | ← |
| D21 | 20  | 3   | 3   | 17.5   | 2.5    | 90°  | ← |
| D22 | 21  | 2   | 3   | 12.5   | 2.5    | 90°  | ← |
| D23 | 22  | 1   | 3   | 7.5    | 2.5    | 90°  | ← |
| D24 | 23  | 0   | 3   | 2.5    | 2.5    | 90°  | ← |

**Board-Größe:** 30.0 × 20.0 mm (cols·pitch × rows·pitch)

**Formeln:**
```
  eff_margin = pitch/2                    = 2.5 mm
  total_h    = (rows-1)·pitch + 2·eff_margin = 20.0 mm
  x          = eff_margin + col·pitch
  y          = total_h - eff_margin - row·pitch = 17.5 - row·5
```


### Gitter-Übersicht (Serpentine)

```
col:       0      1      2      3      4      5
       ┌──────┬──────┬──────┬──────┬──────┬──────┐
row 0  │  D1   │  D2   │  D3   │  D4   │  D5   │  D6   │   →  rot=270°
       │ (2.5) │ (7.5) │(12.5) │(17.5) │(22.5) │(27.5) │   Y=17.5
       ├──────┼──────┼──────┼──────┼──────┼──────┤
row 1  │  D12  │  D11  │  D10  │  D9   │  D8   │  D7   │   ←  rot=90°
       │ (2.5) │ (7.5) │(12.5) │(17.5) │(22.5) │(27.5) │   Y=12.5
       ├──────┼──────┼──────┼──────┼──────┼──────┤
row 2  │  D13  │  D14  │  D15  │  D16  │  D17  │  D18  │   →  rot=270°
       │ (2.5) │ (7.5) │(12.5) │(17.5) │(22.5) │(27.5) │   Y=7.5
       ├──────┼──────┼──────┼──────┼──────┼──────┤
row 3  │  D24  │  D23  │  D22  │  D21  │  D20  │  D19  │   ←  rot=90°
       │ (2.5) │ (7.5) │(12.5) │(17.5) │(22.5) │(27.5) │   Y=2.5
       └──────┴──────┴──────┴──────┴──────┴──────┘
```

```
col: 0     1     2     3     4     5
   ┌─────┬─────┬─────┬─────┬─────┬─────┐
r0 │ D1  │ D2  │ D3  │ D4  │ D5  │ D6  │  →
r1 │ D12 │ D11 │ D10 │ D9  │ D8  │ D7  │  ←
r2 │ D13 │ D14 │ D15 │ D16 │ D17 │ D18 │  →
r3 │ D24 │ D23 │ D22 │ D21 │ D20 │ D19 │  ←
   └─────┴─────┴─────┴─────┴─────┴─────┘
```
