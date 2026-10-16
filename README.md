# LED Matrix Generator

> Direkt-Generator für JLCPCB-Fertigungsdaten (Gerber + Drill + BOM + CPL)
> aus einer Zeile Kommandozeile oder einer Config-Datei. Keine EDA-Software nötig.

Es gibt viele fertige LED-Matrizen zu kaufen – aber irgendwas ist immer:
zu gross, zu klein, falsches Seitenverhältnis, nicht kürzbar, nicht erweiterbar.
Dieser Generator löst das: Spalten, Zeilen, Pitch eingeben – fertige
Produktionsdaten für die eigene, massgeschneiderte LED-Matrix kommen raus.
Die Platinen sind **nahtlos kachelbar** (Boardgröße = cols×pitch × rows×pitch),
mehrere Platinen lassen sich kantig an kantig zu einer großen Fläche reihen.

## Was ist getestet?

Ausdrücklich generiert, geprüft und verifiziert (Stand Okt 2026):

| Was | Ergebnis |
|---|---|
| **LED:** XL-1615RGBC-WS2812B-S, LCSC **C41413180** (WS2812B-kompatibel, 1.6×1.7 mm) | ✅ |
| **8×8-Matrix, Pitch 3.0 mm** → Board 24×24 mm (ZIP `XL-1615_8x8_v12`) | ✅ |
| Geometrie-DRC (`src/drc_geometry.py`): Clearance, Randabstand, Bohrungsabstand, Netz-Zusammenhang | ✅ 573 Kupferobjekte, 67 Netze, 0 Probleme |
| Verbindungscheck (`tools/check_connectivity.py`): GND-, VCC- und Datenketten-Zusammenhang über alle Lagen | ✅ alle Netze zusammenhängend |
| Machbarkeit (`src/feasibility.py`): kleinster machbarer Pitch für C41413180 = **2.95 mm** | ✅ (getestet mit 3.0) |
| Footprint gegen LCSC-API und Datenblatt verifiziert (Pads 0.45×0.65 mm) | ✅ |
| JLCPCB **Economy**-Bestückung: keine Castellations, Bohrung ≥ 0.3 mm, Standard-Limits ohne Aufpreis | ✅ eingehalten |
| Masken: alle 27 Bohrungen beidseitig maskenfrei (kein tenting → in 2D- und 3D-Ansicht sichtbar) | ✅ |

**Nicht (mehr) getestet:** SK9822-EC20 / SPI-LEDs. Die aktuelle Pipeline (v2) ist
auf die 4-Pin-WS2812-Topologie (C41413180) ausgelegt. Die v1-Module
(`bottom_copper`, `top_copper`, `edge_connector`, `router`, `trace_net`) sind
Legacy und werden von `generate.py` nicht mehr verwendet.

## Schnellstart

```bash
# Bauteil-Daten laden (einmalig, wird nach data/ gecacht)
python src/fetch_component.py C41413180

# Matrix generieren; --pitch weglassen = kleinster machbarer Pitch
python src/generate.py --cols 8 --rows 8 --pitch 3.0 --lcsc C41413180 \
    --output output/XL-1615_8x8.zip

# oder per Config (Dateiname = Ausgabename)
python src/generate.py --config cfg/XL-1615_8x8.cfg
```

Zum ZIP gibt es immer PNG-Render von Vorder-/Rückseite (`--no-preview` zum
Abschalten). BOM.csv und CPL.csv liegen im ZIP und werden bei JLCPCB separat
hochgeladen.

## Layout-Topologie (v2)

```
Vorderseite (F.Cu):  LED-Pads; Datenkette auf F.Cu (45°-Diagonalen innerhalb
                     der Reihe, direkte Vertikale zwischen den Reihen);
                     EINE horizontale Stromschiene je Reihenluecke,
                     alternierend GND/VCC; je 3 Stitch-Vias (2 mm Abstand);
                     kleine Netzlabels (+V / G) mittig auf den Schienen
Rückseite  (B.Cu):   ZWEI vertikale Haupt-Rails GND/VCC, mittig, je >= 1/3
                     der Boardbreite; Anschlusspads DIN/DOUT (2.5×5 mm) und
                     VCC/GND-Flaechen (5×5 mm) randbuendig; Beschriftung
                     GND/VCC je 2× mittig auf den Rails, DIN/DOUT 90° gestapelt
Rotation:            Basis 180° (DI links oben), gerade Reihen relativ -90°,
                     damit VDD↔VDD und GND↔GND sich über den Lücken gegenueberliegen
Daten-Einstieg:      DIN oben links, DOUT unten links; je 1 Via von den
                     B.Cu-Anschlusspads auf die F.Cu-Kette
```

Stromführung: Board-Rails (B.Cu) → Stitch-Vias → Reihenschienen (F.Cu) →
Stichleitungen zu den Power-Pads. Jede LED-Reihe wird über genau eine
Schiene versorgt; die Schienen enden bündig mit der letzten Stichleitung.

## Design-Regeln (JLCPCB Economy)

| Regel | Wert |
|---|---|
| Bohrungs-Ø Vias | 0.30 mm (Pad 0.60 mm) |
| Clearance Leitung↔Leitung | 0.15 mm je Seite |
| Randabstand Kupfer | 0.20 mm (randbündige Anschlusspads: bewusst ausgenommen) |
| Datenleitung | 0.15 mm |
| Schienen F.Cu / B.Cu | 0.40 mm / ≥ 1/3 Boardbreite |

## Prüfwerkzeuge

```bash
python src/feasibility.py C41413180 8 8    # Machbarkeit + kleinster Pitch
python src/drc_geometry.py 3.0 8 8         # DRC auf der Generator-Geometrie
python tools/check_connectivity.py         # Netz-Zusammenhang GND/VCC/Daten
python tools/layout_schema.py output       # parametrisches Layout-Schema (PNG)
python src/render_preview.py output/x.zip  # PNG-Render aus einem bestehenden ZIP
```

## Ausgabe (ZIP, JLCPCB-Namenskonvention)

| Datei | Inhalt |
|---|---|
| `matrix-F_Cu.gtl` | LED-Pads, Datenkette, Reihen-Schienen, Via-Pads, Labels |
| `matrix-B_Cu.gbl` | mittige GND/VCC-Rails, Anschlusspads, Via-Pads |
| `matrix-F_Mask.gts` / `matrix-B_Mask.gbs` | Masken: LED-Pads, Anschlusspads, alle Via-Öffnungen |
| `matrix-F_SilkS.gto` / `matrix-B_SilkS.gbo` | Netz-Labels (Vorderseite klein, Rückseite groß) |
| `matrix-Edge_Cuts.gko` | Board Outline |
| `matrix.drl` | Excellon-Drill |
| `BOM.csv` / `CPL.csv` | JLCPCB SMT-Assembly |

## Voraussetzungen

Python 3.10+, Pakete: `pygerber`, `pillow` (nur für den PNG-Render).
Internet nur einmalig für `fetch_component.py`.

## Weiteres

- [`koordinatensysteme.md`](koordinatensysteme.md) – Dokumentation der verwendeten
  Koordinatensysteme (Gerber RS-274X, EasyEDA-API, pygerber, Footprint)
- [`PLAN.md`](PLAN.md) – Architekturentscheidungen der v2-Umstellung
- `data/<LCSC-Nr>/` – gecachte Footprint-Daten der EasyEDA-API

---

Idee von Mir :)
Programmiert mit Hilfe von [Hermes](https://hermes-agent.nousresearch.com) und lokalem
[Qwen3.8 Flash Next IQ3-S](https://huggingface.co/ISTA-DASLab).
Danke an [Alibaba](https://huggingface.co/Qwen), [Strata](https://github.com/Niko1221/Strata)
und [ISTA-DAS Labs](https://huggingface.co/ISTA-DASLab) für die Quantisierung.
