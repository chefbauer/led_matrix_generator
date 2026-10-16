# Beispiel: 8×8-Matrix (XL-1615RGBC-WS2812B-S)

> [!WARNING]
> Noch nicht bei JLCPCB bestellt / physisch ungetestet – alle Prüfungen sind
> simuliert (DRC, Konnektivität, Masken).

Durchgetestetes (simuliert) Referenzbeispiel des Generators: **8 Spalten × 8 Zeilen,
Pitch 3.0 mm**, LED **XL-1615RGBC-WS2812B-S** (LCSC **C41413180**,
WS2812B-kompatibel). Ergebnis: **24 × 24 mm** Platinen, nahtlos kachelbar.

## Generieren

```bash
python src/fetch_component.py C41413180        # Footprint laden (einmalig)
python src/generate.py --cols 8 --rows 8 --pitch 3.0 --lcsc C41413180 \
    --output output/XL-1615_8x8_v14.zip
```

oder mit dieser Config: [`cfg/XL-1615_8x8.cfg`](../../cfg/XL-1615_8x8.cfg)

## Verifikation (alles bestanden)

| Prüfung | Kommando | Ergebnis |
|---|---|---|
| Machbarkeit | `python src/feasibility.py C41413180 8 8` | ✅ Pitch 3.0 = Minimum (gerade Zeilenzahl) |
| Geometrie-DRC | `python src/drc_geometry.py 3.0 8 8` | ✅ 573 Kupferobjekte, 27 Bohrungen, 67 Netze, 0 Verstöße |
| Netz-Zusammenhang | `python tools/check_connectivity.py` | ✅ GND/VCC/Datenkette durchgängig |
| Masken | ZIP-Parse GTS/GBS | ✅ alle Via-Bohrungen beidseitig offen |
| Footprint | LCSC-API + Datenblatt | ✅ Pads 0.45×0.65 mm, 1.70×1.60 mm Kupfer |

## Inhalt

| Datei | Beschreibung |
|---|---|
| [`XL-1615_8x8_v14.zip`](XL-1615_8x8_v14.zip) | Fertigungsdaten (Gerber + Drill + BOM + CPL), direkt bei JLCPCB hochladbar |
| [`render_front.png`](render_front.png) | Eigener PNG-Render, Vorderseite (LED-Pads, Datenkette, Reihenschienen) |
| [`render_back.png`](render_back.png) | Eigener PNG-Render, Rückseite (mittige GND/VCC-Rails, Anschlusspads, Beschriftung) |
| [`jlcpcb_preview_top.png`](jlcpcb_preview_top.png) | 2D-Preview aus dem JLCPCB-Viewer, Oberseite |
| [`jlcpcb_preview_bottom.png`](jlcpcb_preview_bottom.png) | 2D-Preview aus dem JLCPCB-Viewer, Unterseite |

> [!NOTE]
> Die JLCPCB-Viewer-Bilder stammen noch von Revision v13 (damals volle
> Schienenbreite, andere Rand-Via-Position). Der ZIP und die eigenen Renders
> zeigen die aktuelle Revision v14 (strombasierte Schienen, Strom-basierte
> Stitch-Vias).

## Was man sieht

- **Rückseite (B.Cu):** zwei vertikale Haupt-Rails GND/VCC mittig, randbündige
  Anschlusspads (VCC/GND 5×5 mm, DIN/DOUT 2.5×5 mm), große Beschriftung
  GND/VCC je 2× auf den Rails, DIN/DOUT 90° gedreht an den Pads.
- **Vorderseite (F.Cu):** LED-Pads (gerade Reihen um 90° relativ gedreht),
  Datenkette mit 45°-Diagonalen, eine horizontale Stromschiene je Reihenlücke
  (alternierend GND/VCC) mit je 3 Stitch-Vias auf 2 mm Abstand, kleine
  Labels +V/G zur Orientierung.
- **Anschluss:** DIN oben links, DOUT unten links (bei 8 Zeilen; bei ungerader
  Zeilenzahl wäre DOUT unten rechts). Platinen sind kantig an kantig kachelbar,
  DIN kommt immer oben links herein.

## Bestellung bei JLCPCB

- PCB: 2-lagig, 1.6 mm, schwarze Maske, Economy
- SMT-Assembly: BOM.csv + CPL.csv aus dem ZIP separat hochladen
- Bauteil: C41413180 (Top-Side, Economy Bestückung)
