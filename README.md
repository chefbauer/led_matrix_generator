# LED Matrix Generator

> Direkt-Generator für JLCPCB-Fertigungsdaten aus Config-Dateien.  
> Keine EDA-Software nötig.

## Quickstart

```bash
# In einem Rutsch: Gerber + PNGs + Netz-Traces
python3 src/generate.py --config cfg/SK9822_5x4.cfg

# Nur Gerber
python3 src/generate.py --config cfg/SK9822_5x4.cfg --no-preview

# Neue LED laden (einmalig)
python3 src/fetch_component.py C41413180
```

## Features

| Feature | Status |
|---|---|
| **6-Pin SPI-LED** (SK9822, 2x2mm) | ✅ inkl. CLK-Routing, Busbar |
| **4-Pin WS2812-LED** (XL-1615RGBC) | ✅ mit H-45-H Datenrouting |
| **Busbar** (links, Top/Bottom) | ✅ GND/VDD Kupferflächen, Connector-Pads |
| **Edge-Connector** (Halb-Löcher) | ✅ für 4-Pin busbar=0: GND/DI/VCC + GND/DO/VCC |
| **Serpentinen-Matrix** | ✅ 270°/90° Rotation, H/V/45° Router |
| **Drill (3 Werkzeuge)** | ✅ T1=0.30 Vias, T2=0.80 DAT/CLK, T3=1.00 +5V/GND |
| **Auto-Preview** | ✅ PNG Vorder-/Rückseite bei jedem `generate` |
| **Netz-Tracer** | ✅ `trace_net.py`: VCC/GND Kupferflächen visualisieren |
| **Pin-1-Marker** | ✅ roter Punkt am DO-Pad im Render |
| **Solder Mask** | ✅ 0.05 mm Expansion (JLCPCB-Standard) |
| **Design Rules** | ✅ TRACE_DATA 0.20 mm, TRACE_POWER 0.30 mm, CLEARANCE 0.15 mm |

## Ausgabe (ZIP)

| Datei | Inhalt |
|---|---|
| `matrix-F_Cu.gtl` | Top Copper: Pads, Datenkette, Power-Stichleitungen, Edge-Connector |
| `matrix-B_Cu.gbl` | Bottom Copper: VDD/GND-Schienen, Via-Pads, Edge-Connector-Stubs |
| `matrix-F_Mask.gts` | Top Solder Mask |
| `matrix-B_Mask.gbs` | Bottom Solder Mask |
| `matrix-F_SilkS.gto` | Top Silkscreen |
| `matrix-Edge_Cuts.gko` | Board Outline |
| `matrix.drl` | Excellon Drill |
| `BOM.csv` | Bill of Materials |
| `CPL.csv` | Component Placement List |

## Config-Parameter (`cfg/*.cfg`)

| Parameter | Bedeutung |
|---|---|
| `cols` / `rows` | Matrixgröße |
| `pitch` | Abstand Mitte-zu-Mitte in mm |
| `margin` | Rand (`0` = `pitch/2`) |
| `busbar` | `0` = keine, `1` = links |
| `led_current_ma` | mA pro LED |
| `copper_oz` | Kupfergewicht (1 oder 2) |
| `jlcpcb_part` | LCSC-Teilenummer |

## Unterstützte LEDs

| LED | LCSC # | Pads | CLK |
|---|---|---|---|
| SK9822-EC20 | C2909059 | 6 | ✅ |
| XL-1615RGBC-2812B-S | C41413180 | 4 | ❌ |

## Weitere Tools

```bash
# Netz-Tracer (Kurzschluss-Prüfung)
python3 src/trace_net.py output/SK9822_5x4.zip --dpmm 100
# → *_vcc.png + *_gnd.png

# PNG-Vorschau (manuell)
python3 src/render_preview.py output/SK9822_5x4.zip --dpmm 100
```

## Koordinatensystem

Siehe [`koordinatensysteme.md`](koordinatensysteme.md) — vollständige Dokumentation aller verwendeten Koordinatensysteme (Gerber RS-274X, EasyEDA, pygerber, Footprint).

Es gibt viele fertige LED-Matrizen zu kaufen – aber irgendwas ist immer:
zu gross, zu klein, falsches Seitenverhaeltnis, nicht kuerzbar, nicht erweiterbar.
Wer eine Matrix in genau der richtigen Groesse braucht, hat meist keine gute Option.

Dieser Generator loest das Problem: Spalten, Zeilen und Pitch eingeben –
fertige Produktionsdaten fuer die eigene, massgeschneiderte LED-Matrix kommen raus.
Die Platine wird direkt bei JLCPCB bestellt und bestueckt, kein Loeten, kein Basteln.

Unterstuetzt werden SPI-adressierbare LEDs wie der SK9822-EC20 (APA102-kompatibel).
Das Routing, die Stromversorgung und alle Fertigungsdateien werden automatisch generiert (WIP).

---

Generiert fertige Produktionsdaten (Gerber + BOM + CPL) fuer addressierbare LED-Matrizen
direkt aus einer Konfigurationsdatei – ohne EDA-Tool, ohne externe Abhaengigkeiten.

**Ausgabe:** Ein ZIP-Paket, das direkt bei JLCPCB hochgeladen werden kann (SMT Assembly).
BOM und CPL sind in der Zip, müssen aber extra hochgeladen werden.


## Voraussetzungen

- Python 3.10+
- Internetzugang (einmalig fuer Bauteil-Download)

---

## Schnellstart

### 1. Bauteil-Daten laden (einmalig, wird gecacht)

```bash
python3 src/fetch_component.py C2909059
```

Laedt Pad-Geometrie und Metadaten von der EasyEDA-API.
Gecachte Daten werden automatisch wiederverwendet.
Mit `--force-download` neu laden:

```bash
python3 src/fetch_component.py C2909059 --force-download
```

### 2. Config-Datei erstellen

Configs liegen im Ordner `cfg/`. Dateiname = Ausgabename des ZIP.

**Beispiel: `cfg/SK9822_5x4.cfg`**

```ini
# LED-Matrix Konfiguration
# Ausgabe: output/SK9822_5x4.zip

[matrix]
cols   = 5        # Anzahl Spalten
rows   = 4        # Anzahl Zeilen
pitch  = 5.0      # Abstand LED-Mitte zu LED-Mitte in mm
margin = 0        # Zusaetzlicher Rand in mm (0 = nur pitch/2)

[led]
jlcpcb_part = C2909059   # JLCPCB/LCSC Teilenummer
```

**Board-Groesse:** `(cols-1)*pitch + 2*(pitch/2 + margin)` × `(rows-1)*pitch + 2*(pitch/2 + margin)`

Bei `margin=0` liegt die Platinenkante genau `pitch/2` vom aeussersten LED-Mittelpunkt entfernt.

Beispiele:
| Config | Board |
|---|---|
| cols=5, rows=4, pitch=5, margin=0 | 25 × 20 mm |
| cols=32, rows=11, pitch=5, margin=0 | 165 × 60 mm |
| cols=32, rows=11, pitch=5, margin=2 | 169 × 64 mm |

### 3. Generieren

```bash
python3 src/generate.py --config cfg/SK9822_5x4.cfg
```

Ausgabe: `output/SK9822_5x4.zip`

Einzelne Parameter koennen per CLI ueberschrieben werden:

```bash
python3 src/generate.py --config cfg/SK9822_5x4.cfg --rows 6
```

---

## Ausgabedateien (ZIP)

| Datei | Inhalt |
|---|---|
| `matrix-F_Cu.gtl` | Top Copper: LED-Pads, Datenleitungen (DI/DO, CI/CO), Via-Stichleitungen |
| `matrix-B_Cu.gbl` | Bottom Copper: VDD/GND-Stromschienen pro Reihe |
| `matrix-F_Mask.gts` | Top Solder Mask |
| `matrix-B_Mask.gbs` | Bottom Solder Mask |
| `matrix-Edge_Cuts.gko` | Board Outline |
| `matrix.drl` | Excellon Drill (Vias) |
| `BOM.csv` | Bill of Materials (JLCPCB SMT Format) |
| `CPL.csv` | Component Placement List (JLCPCB SMT Format) |

---

## Layout-Konzept

```
Oberseite (Top):   LED-Pads + Datenleitungen (DI/DO, CI/CO) im Serpentinenmuster
Unterseite (Bottom): Stromschienen VDD und GND pro Reihe, je pitch/2 breit
Vias:              Senkrecht vom Pad zur Stromschiene
```

Jede LED-Reihe hat einen eigenen VDD-Bus und GND-Bus auf gegenueberliegenden Seiten.
Bei geraden Reihen (→) liegt VDD unten, GND oben. Bei ungeraden (←) umgekehrt.

**Design Rules:** Mindestabstand 0.30 mm (= 2 × 0.15 mm Clearance), Bus-Breite bei p=5mm: 2.20 mm.

---

## Unterstuetzte LEDs

| LED | JLCPCB # | Package | Klasse |
|---|---|---|---|
| SK9822-EC20 | C2909059 | LED-SMD_6P-L2.0-W2.0-P0.80-TL | Extended Part |

Weitere LEDs: `python3 src/fetch_component.py <JLCPCB-Nr>` laden, dann in Config eintragen.

---

## Verzeichnisstruktur

```
led_matrix_generator/
├── cfg/                  # Konfigurationsdateien
│   ├── SK9822_5x4.cfg
│   └── SK9822_32x11.cfg
├── src/                  # Python-Quellcode
│   ├── generate.py       # Hauptskript
│   ├── fetch_component.py
│   └── ...
├── data/                 # Gecachte Bauteil-Daten (EasyEDA API)
│   └── C2909059/
│       ├── component.json
│       ├── footprint.json
│       └── raw.json
└── output/               # Generierte ZIPs
```

---

Idee von Mir :)
Programmiert mit Hilfe von Claude Sonnet 4.6

