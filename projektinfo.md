# Projektinfo: LED-Matrix-Gerber-Generator

## Aktueller Stand (2026-06-11)

Das Projekt ist funktionsfähig und erzeugt vollständige JLCPCB-kompatible Fertigungsdaten.

### Erzeugte Ausgabedateien (ZIP)

| Datei | Inhalt |
|---|---|
| `matrix-F_Cu.gtl` | Top Copper: LED-Pads, Daten-Traces (DI/DO, CI/CO), Via-Stichleitungen |
| `matrix-B_Cu.gbl` | Bottom Copper: VDD/GND-Stromschienen + Via-Pads |
| `matrix-F_Mask.gts` | Top Solder Mask: Öffnungen über allen Top-Pads und Vias |
| `matrix-B_Mask.gbs` | Bottom Solder Mask: Öffnungen über Via-Pads |
| `matrix-Edge_Cuts.gko` | Board Outline: Rechteck |
| `matrix.drl` | Excellon Drill: Via-Bohrungen |
| `BOM.csv` | Bill of Materials im JLCPCB-Format |
| `CPL.csv` | Component Placement List im JLCPCB-Format |

### CLI

```bash
python3 src/generate.py --cols 32 --rows 11 --pitch 5.0 --margin 2.5 --output output/matrix.zip
```

Parameter:
- `--cols` / `--rows`: Matrixgröße
- `--pitch`: Abstand LED-Mitte zu LED-Mitte in mm
- `--margin`: Randabstand in mm (`0` = `pitch/2`)
- `--led`: LED-Typ (Standard: `SK9822-EC20`)
- `--output`: Ausgabedatei

### Komponentendaten laden (einmalig pro Bauteil)

```bash
python3 src/fetch_component.py C2909059
```

Speichert unter `data/C2909059/`:
- `component.json` – normalisierte Metadaten für BOM
- `footprint.json` – Pad-Geometrie, Signalnamen, Pin-1-Marker (aus EasyEDA API geparst)
- `raw.json` – vollständige API-Rohdaten

---

## Quelldateien

### `src/fetch_component.py`

Lädt Bauteil-Daten von der EasyEDA-API (`easyeda.com/api/products/{lcsc_id}/components`), kein Login erforderlich.

Parst automatisch:
- Pad-Koordinaten aus `packageDetail.dataStr.shape` (PAD~-Einträge)
- Signalnamen aus Schaltzeichen-Shapes (P~-Einträge), mit Alias-Mapping (`SDO`→`DO`, `CKL`→`CI`, `CKO`→`CO`, `SDI`→`DI`)
- Origin-Koordinaten aus Canvas-String (Index 16/17)
- Pin-1-Marker-Position (Seidendruckkreis auf Layer 3)
- EasyEDA-Einheit: 1 unit = 0.254 mm (= 10 mil)

### `src/component_data.py`

Lädt gecachte Daten aus `data/{lcsc_id}/component.json` als `ComponentInfo`-Dataclass.

### `src/footprint.py`

Footprint-Definitionen. Alle Werte direkt aus `data/C2909059/raw.json` abgeleitet.

**SK9822-EC20 – verifizierte Geometrie:**

Layout: 2 Spalten × 3 Reihen (nicht 3×2!)

```
        links (-0.7070 mm)   rechts (+0.7070 mm)
oben   (-0.8001 mm):  Pad1=DO    Pad6=CO
mitte  (+0.0000 mm):  Pad2=GND   Pad5=VDD
unten  (+0.8001 mm):  Pad3=DI    Pad4=CI
```

Pad-Größe: `0.875 × 0.400 mm`
Gehäuse: `2.0 × 2.0 mm`
Pin-1-Marker: `(-1.680, -0.840) mm` relativ Mittelpunkt (oben-links)

**Via-Positionen** (lokal, vor Rotation):
- VDD-Via: `(+0.707, +0.500)` – 0.5 mm unterhalb VDD-Pad → nach Rotation horizontal zur Schiene
- GND-Via: `(-0.707, -0.500)` – 0.5 mm oberhalb GND-Pad → nach Rotation horizontal zur Schiene

**Rotationslogik:**
- Gerade Reihen (→): 90° CCW → DO rechts, DI links → Trace innerhalb Reihe: horizontal
- Ungerade Reihen (←): 270° CCW → DO links, DI rechts → Trace innerhalb Reihe: horizontal
- Zeilenübergang (D_last → D_first_next): DO und DI liegen auf identischem X → Trace: vertikal

Hilfsfunktionen: `rotate_xy()`, `pad_pos()`, `via_pos()`

### `src/matrix.py`

`LedInstance` – Datenklasse: `index, ref, col, row, x, y, rotation, nets`

`generate_matrix(cols, rows, pitch, fp, margin)` – Serpentinen-Reihenfolge, Netz-Zuordnung, Rotation pro Reihe

`board_size(cols, rows, pitch, margin)` – Platinengröße

`_effective_margin(margin, pitch)` – `margin=0` → `pitch/2`

### `src/gerber_writer.py`

RS-274X-Writer. Format: `%FSLAX46Y46*%`, 1 mm = 1.000.000 Integer-Einheiten.

API:
```python
g = GerberWriter("Kommentar")
ap = g.add_aperture(ApertureShape.RECT, width, height)
ap_c = g.add_aperture(ApertureShape.CIRCLE, diameter)
g.flash(ap, x, y)
g.draw(ap, x1, y1, x2, y2)
g.rect_outline(ap, x0, y0, x1, y1)
content = g.render()
```

### `src/top_copper.py`

Erzeugt GTL:
1. LED-Pads flashen (rotierte Positionen via `pad_pos()`)
2. Daten-Traces: DO→DI und CO→CI zwischen Ketten-Nachbarn
3. Power-Stichleitungen: Via → VDD-Pad und Via → GND-Pad (horizontal nach Rotation)

### `src/bottom_copper.py`

Erzeugt GBL:
- Pro Reihe: horizontale VDD-Schiene von x_min bis x_max aller Vias dieser Reihe
- Pro Reihe: horizontale GND-Schiene
- Via-Pads flashen

Via-Positionen via `fp_via_pos()` aus `footprint.py`.

### `src/other_layers.py`

- `build_top_soldermask()` – Pad-Öffnungen + Via-Öffnungen (SM_EXP = 0.05 mm pro Seite)
- `build_bottom_soldermask()` – Via-Öffnungen auf Bottom
- `build_board_outline()` – Rechteck aus `board_size()`
- `build_drill()` – Excellon, alle Via-Bohrungen (VIA_DRILL = 0.30 mm)

### `src/bom.py`

Erzeugt `BOM.csv` im JLCPCB-Format:

```
Comment,Designator,Footprint,JLCPCB Part #
SK9822-EC20,"D1,D2,...",LED-SMD_6P-L2.0-W2.0-P0.80-TL,C2909059
```

### `src/cpl.py`

Erzeugt `CPL.csv` im JLCPCB-Format:

```
Designator,Mid X,Mid Y,Layer,Rotation
D1,2.000mm,2.000mm,Top,90
D2,7.000mm,2.000mm,Top,90
...
```

Rotation = interne LED-Rotation (90°/270° CCW), direkt kompatibel mit JLCPCB-CPL-Standard.

### `src/generate.py`

Hauptskript. Assembliert alle Layer, lädt Komponentendaten, erzeugt ZIP.

`JLCPCB_PARTS = {"SK9822-EC20": "C2909059"}` – Mapping LED-Typ → LCSC-Nummer.

---

## Verzeichnisstruktur

```
led_matrix_generator/
├── src/
│   ├── generate.py           # CLI-Einstiegspunkt
│   ├── fetch_component.py    # EasyEDA API + Footprint-Parser
│   ├── component_data.py     # Daten-Loader
│   ├── footprint.py          # Pad-Geometrie, Rotationshelfer
│   ├── matrix.py             # LED-Platzierung, Serpentine
│   ├── gerber_writer.py      # RS-274X Writer
│   ├── top_copper.py         # GTL-Generator
│   ├── bottom_copper.py      # GBL-Generator
│   ├── other_layers.py       # GTS, GBS, GKO, DRL
│   ├── bom.py                # BOM CSV
│   ├── cpl.py                # CPL CSV
│   └── output/               # Ausgabe-ZIPs
├── data/
│   └── C2909059/
│       ├── component.json    # normalisierte Metadaten
│       ├── footprint.json    # Pad-Geometrie aus EasyEDA
│       └── raw.json          # API-Rohdaten
├── example/                  # JLCPCB-Beispieldateien (BOM, CPL)
└── projektinfo.md
```

---

## Bekannte Bauteile

| LED | JLCPCB Part # | Package | Klasse |
|---|---|---|---|
| SK9822-EC20 | C2909059 | LED-SMD_6P-L2.0-W2.0-P0.80-TL | Extended Part |

---

## Design Rules (aktuell verwendet)

| Parameter | Wert |
|---|---|
| Daten-Trace Breite | 0.15 mm |
| Power-Stichleitung | 0.20 mm |
| Stromschiene Bottom | 0.40 mm |
| Via Pad-Ø | 0.50 mm |
| Via Bohrung | 0.30 mm |
| Solder Mask Expansion | 0.05 mm |
| Board Outline Linie | 0.05 mm |

---

## Offene Punkte / Nächste Schritte

- [ ] 32×11-Matrix erzeugen und bei JLCPCB hochladen
- [ ] Anschlusspads (Connector) am Rand für DI/CI/VDD/GND
- [ ] Silkscreen-Lage (Bauteilbeschriftung / Orientierungspfeile)
- [ ] Design-Rule-Check der erzeugten Gerber (z.B. in KiCad-Viewer)
- [ ] Weitere LED-Typen: fetch + footprint.json + JLCPCB_PARTS-Eintrag genügt

## Ziel

Dieses Projekt soll einen Generator bereitstellen, der aus wenigen technischen Eingaben direkt fertige Produktionsdaten fuer LED-Matrizen erzeugt.

Primaeres Ziel:

- Direkte Generierung von Gerber-Dateien fuer LED-Matrizen
- Zusaetzliche Erzeugung aller relevanten Fertigungsdateien
- Ausgabe als ZIP-Datei fuer den direkten Upload bei Fertigern wie JLCPCB

Beispiel-Zielbild:

- LED-Typ: SK9822-EC20, 2 x 2 mm
- Matrix: 32 x 11
- Pitch: 5 mm
- Routing-/Bestueckungsmuster: Serpentin, x dann -x

Anschluesse ueber Pads sind vorgesehen, kommen aber in einer spaeteren Ausbaustufe.

## Projektidee

Das Tool soll aus einer kompakten Beschreibung einer LED-Matrix ein PCB-Layout fuer eine bestueckbare Leiterplatte ableiten. Die LEDs werden in einer Matrix platziert, elektrisch in der gewuenschten Reihenfolge verbunden und anschliessend in standardisierte Produktionsdaten exportiert.

Da Gerber textbasiert ist, ist eine direkte Generierung prinzipiell moeglich. Dadurch kann auf ein volles EDA-Frontend in der ersten Version verzichtet werden.

Alternativ kann geprueft werden, ob eine EasyEDA-API bestimmte Schritte vereinfacht, etwa fuer Footprints, PCB-Objekte oder Exportfunktionen. Diese Option ist technisch interessant, aber von den real verfuegbaren API-Funktionen abhaengig.

## Kernanforderungen

Das Projekt soll mindestens folgende Aufgaben abdecken:

1. Einlesen einer kompakten Projektbeschreibung
2. Platzierung der LEDs in einer Matrix mit definiertem Pitch
3. Erzeugung der elektrischen Verkettung im Serpentinenmuster
4. Ausgabe fertiger Fertigungsdaten
5. Verpackung aller Ausgabedateien in ein ZIP-Archiv

## Beispiel-Eingaben

Eine moegliche Konfiguration fuer die erste Version:

```yaml
led:
  part_number: SK9822-EC20
  body_size_mm: [2.0, 2.0]
matrix:
  width: 32
  height: 11
placement:
  pitch_mm: 5.0
  pattern: serpentine
  row_direction:
    - x
    - -x
output:
  format: gerber_zip
```

## Erwartete Ausgaben

Die erste Zielausgabe ist ein ZIP-Paket mit mindestens folgenden Inhalten:

- Gerber-Dateien fuer alle relevanten Lagen
- Excellon-Bohrdaten, falls benoetigt
- Pick-and-Place-Datei
- BOM
- Fertigungs- oder Projekt-Metadaten
- Vorschau- oder Debug-Ausgabe, falls hilfreich

Typische Dateien fuer den ZIP-Export:

- Top Copper
- Bottom Copper, falls verwendet
- Top Solder Mask
- Bottom Solder Mask, falls verwendet
- Top Silkscreen
- Board Outline
- Drill File
- Pick and Place CSV
- BOM CSV

## Machbarkeit der direkten Gerber-Generierung

### Warum dieser Anwendungsfall besonders geeignet ist

Die direkte Gerber-Generierung ist fuer dieses Projekt nicht nur moeglich, sondern der naheliegendste Weg. Die entscheidenden Gruende:

**Ein Bauteil, n mal wiederholt**

Es gibt genau einen LED-Typ. Sein Footprint wird einmal definiert und dann mathematisch auf alle n x m Positionen angewendet. Es gibt keine variablen Geometrien, keine unregelmaessigen Platziermuster und keine Sonderloesungen fuer einzelne Bauteile.

**Rasterkoordinaten sind reine Arithmetik**

Jede LED-Position ergibt sich direkt aus Zeilenindex, Spaltenindex und Pitch:

```
x = spalte * pitch
y = zeile * pitch
```

Kein freies Placement, kein Constraint-Solver noetig.

**Vorhersagbares Routing**

Das Serpentinenmuster verbindet immer benachbarte LEDs. Die Verbindung zwischen Data-Out einer LED und Data-In der naechsten ist in jeder Zeile eine kurze, gerade Linie. Der Zeilenuebergang ist ebenfalls berechenbar. Das entspricht keinem komplexen Routing-Problem, sondern einer einfachen Schleife ueber die Verkettungsreihenfolge.

**Gerber RS-274X ist textbasiert und gut dokumentiert**

Eine Gerber-Datei besteht aus Apertur-Definitionen und Flash-/Draw-Befehlen. Fuer diesen Anwendungsfall ist die benoetigte Teilmenge des Formats sehr klein.

Grundstruktur einer Lage:

```
%FSLAX46Y46*%         Koordinatenformat
%MOMM*%               Einheit Millimeter
%ADD10C,0.700*%       Apertur 10: Kreis, Durchmesser 0.7 mm
G54D10*               Apertur 10 aktivieren
X1000000Y1000000D03*  Flash bei (1.0, 1.0)
M02*                  Dateiende
```

Koordinaten werden als Ganzzahlen mit definiertem Dezimalfaktor angegeben, also ohne Floating-Point-Probleme in der Datei.

**Keine Bohrungen noetig**

Der SK9822-EC20 ist ein reines SMD-Bauteil. Eine Drill-Datei ist fuer das LED-Feld selbst leer oder entfaellt. Falls spaeter Loetpads als Anschluesse ergaenzt werden, kommen ggf. Montageloecher hinzu, aber das ist trivial.

**Ausreichend Platz fuer Leiterbahnen**

Bei 5 mm Pitch und 2 mm Gehaeuse bleiben 3 mm freier Abstand zwischen den Bauteilkanten. Das ist bei typischen PCB-Designregeln (Mindestbreite 0.1-0.2 mm, Mindestabstand 0.1-0.2 mm) sehr komfortabel.

### Benoetigte Gerber-Lagen und ihr Inhalt

| Lage | Dateiendung | Inhalt | Aufwand |
|---|---|---|---|
| Top Copper | .GTL | Pads aller LEDs + Leiterbahnen | mittel, repetitiv |
| Top Solder Mask | .GTS | Pad-Oeffnungen, minimal groesser als Pads | wie GTL, einfach |
| Top Silkscreen | .GTO | Bauteilumrisse, optionale Referenzen | einfach |
| Board Outline | .GKO | Rechteck aus Matrixabmessung + Rand | trivial |
| Drill File | .DRL | Leer oder Montageloecher | minimal |

Fuer eine einfache erste Version reicht eine einlagige Topseite-only Loesung, sofern Power- und GND-Routing in einer Lage machbar ist.

### Routing-Strategie fuer den SK9822-EC20

Der SK9822-EC20 ist ein SPI-adressierbarer LED-Chip mit 6 Pins:

- VDD
- GND
- DI (Data In)
- DO (Data Out)
- CI (Clock In)
- CO (Clock Out)

Fuer das Routing ergeben sich drei Gruppen:

1. **Power-Bus**: VDD und GND laufen als horizontale Stromschienen auf der Unterseite (Bottom Copper). Jede LED wird per Via angebunden (siehe unten).
2. **Datenkette**: DI/DO und CI/CO werden in der Serpentinenreihenfolge von LED zu LED verbunden. Immer DO einer LED zu DI der naechsten, und CO zu CI entsprechend.
3. **Zeilenwechsel**: Am Ende jeder Zeile wird ein kurzes Verbindungsstueck zum Anfang der naechsten Zeile gezogen.

Alle drei Faelle sind geometrisch trivial und lassen sich algorithmisch bestimmen.

### Stromversorgungskonzept: Zweiseitig mit Vias

Das Design ist zweilagig. VDD und GND werden auf der Unterseite (Bottom Copper) als horizontale Stromschienen gefuehrt. Die Anbindung jeder einzelnen LED erfolgt ueber Vias mit einer kurzen Verbindung auf der Oberseite.

**Aufbau pro LED:**

```
Bottom Layer:
  ─────────── VDD-Schiene (horizontal) ───────────
  ─────────── GND-Schiene (horizontal) ───────────

              |          |
            Via+        Via-    (je 0.5 mm neben dem LED-Pad)

Top Layer:
   Via+ ──── VDD-Pad der LED
   Via- ──── GND-Pad der LED
```

**Geometrie:**

- Die Vias sitzen je 0.5 mm neben dem zugehoerigen LED-Pad (horizontal versetzt, gleiche Y-Koordinate wie das Pad)
- Kurze Trace auf Top Copper verbindet Via mit dem Pad
- Alle Vias einer Zeile liegen auf gleicher Hoehe wie die LED-Pads
- Die Stromschienen auf der Unterseite verlaufen horizontal (gleiche Richtung wie die Matrixzeilen)

**Berechnung im Generator:**

Fuer jede LED an Position (cx, cy) gilt:

```
Via_VDD = (cx + pad_vdd_offset_x - 0.5, cy + pad_vdd_offset_y)
Via_GND = (cx + pad_gnd_offset_x - 0.5, cy + pad_gnd_offset_y)
```

Der Versatz (links oder rechts) haengt von der Pad-Lage im Footprint ab und wird einmalig im Footprint-Modell hinterlegt.

Die Stromschienen auf dem Bottom Layer werden pro Zeile als durchgehende Trace von x_min bis x_max gezogen, alle Vias dieser Zeile werden mit `D03` (Flash) auf die Schiene gesetzt.

**Auswirkung auf die Gerber-Lagen:**

| Lage | Zusaetzlicher Inhalt |
|---|---|
| Top Copper (GTL) | Kurze Traces Via -> Pad fuer VDD und GND |
| Bottom Copper (GBL) | Horizontale VDD- und GND-Schienen + Via-Pads |
| Top Solder Mask (GTS) | Pad-Oeffnungen wie bisher |
| Bottom Solder Mask (GBS) | Via-Oeffnungen, falls Vias freigelegt |
| Drill File (DRL) | Via-Bohrungen fuer alle Stromvias |

Durch dieses Konzept bleibt die Oberseite frei fuer die Datenkette (DI/DO/CI/CO) und es gibt keine Kreuzungen zwischen Power- und Daten-Routing.

### Footprint als einzige kritische Vorarbeit

Das einzige, was nicht automatisch ableitbar ist, sind die exakten Pad-Abmessungen und -Positionen des SK9822-EC20. Diese muessen einmalig aus dem Hersteller-Datenblatt oder der JLCPCB/LCSC-Bibliothek uebernommen werden.

Sobald der Footprint einmal sauber in einer internen Struktur hinterlegt ist, wird er nur noch als Vorlage verwendet und n mal platziert.

### Umfang des Generators in Code

Ein funktionierender erster Generator ist mit Python realisierbar und besteht aus ueberschaubaren Teilen:

- Koordinatenberechnung: ~30 Zeilen
- Gerber-Writer fuer eine Lage: ~80-100 Zeilen
- Pick-and-Place-Ausgabe: ~30 Zeilen
- BOM-Ausgabe: ~20 Zeilen
- ZIP-Paketierung: ~20 Zeilen

Die Gesamtkomplexitaet ist niedrig. Keine Abhaengigkeiten von EDA-Tools oder externen Diensten.

### Fazit

Direkte Gerber-Generierung ist fuer diesen Anwendungsfall praktikabel. Die Kombination aus einem einzigen Bauteiltyp, regelmaessigem Array-Layout und vorhersagbarem Routing beseitigt alle klassischen Gruende, warum direkte Gerber-Erzeugung aufwaendig ist. Der Kernaufwand liegt in der einmaligen sauberen Definition des LED-Footprints und einem einfachen Python-Generator ohne externe Abhaengigkeiten.

## Technischer Schwerpunkt

### Entscheidung: Direkter Gerber-Weg

Der Generator erzeugt Gerber-Dateien direkt, ohne Abhaengigkeit von EDA-Tools oder externen APIs.

Begruendung:

- Volle Kontrolle ueber die Ausgabe, keine externen Abhaengigkeiten
- Fuer ein regelmaessiges Array mit einem Bauteiltyp sehr ueberschaubarer Aufwand
- Vollautomatisch ausfuehrbar, kein offener Editor noetig
- Gerber ist ein universelles Format: die erzeugten Dateien koennen direkt bei JLCPCB hochgeladen werden und lassen sich zusaetzlich in EasyEDA Pro oder KiCad importieren und weiterbearbeiten

Nachteile (bekannt und akzeptiert):

- Footprint muss einmalig aus dem Datenblatt uebernommen werden
- Kein eingebauter DRC

### Abgelehnter Weg: KiCad API

KiCad waere technisch interessant gewesen, da es eine Skript-API (Python) hat und freie Software ist. Die API ist jedoch in ihrem Umfang und ihrer Stabilitaet nicht zuverlaessig vorhersagbar, einzelne Versionen haben inkompatible Aenderungen eingefuehrt. Fuer ein Generator-Projekt, das robust und wartbar sein soll, ist das keine belastbare Basis.

### Nachgelagerter Import (optional)

Da Gerber ein universelles Format ist, koennen die erzeugten Dateien jederzeit in EasyEDA Pro oder KiCad importiert werden. Das erlaubt:

- Visuelle Pruefung des Layouts
- Nachbearbeitung falls noetig
- DRC im jeweiligen EDA-Tool
- Export in andere Formate aus dem EDA-Tool heraus

Der Generator selbst bleibt davon unabhaengig.

## Empfehlung fuer die erste Version

Empfohlen wird ein Generator mit direkter textbasierter Ausgabe, der zunaechst nur einen klaren, kleinen Zielbereich abdeckt:

- Ein LED-Typ pro Projekt
- Eine rechteckige Matrix
- Festes Serpentinenmuster
- Zweilagiges Layout: Datenkette auf Top, Power-Schienen auf Bottom mit Vias
- Standardisierte Ausgabedateien fuer JLCPCB-kompatiblen Upload

Das reduziert das Risiko und erlaubt frueh nutzbare Ergebnisse.

## Footprint-Quelle

Der Footprint fuer die LED soll nicht manuell frei geraten werden, sondern aus verifizierbaren Quellen kommen.

### API-Analyse (getestet 2026-06-11)

Es wurden drei Zugaenge untersucht: die JLCPCB-Partdetail-Seite, die jlcparts-Community-Tool-Infrastruktur und die interne JLCPCB-Komponenten-API.

**JLCPCB-Partdetail-Seite** (`jlcpcb.com/partdetail/.../C22371528`)

Die Seite ist HTML-rendered. Sie liefert:

- Package-Bezeichnung: `SMD2121-6P`
- Abmessungen aus den Attributfeldern: 2,2 mm x 2,2 mm, Hoehe 1,05 mm
- Link auf das Datenblatt-PDF (zeitlich begrenzte Signed URL)
- Verweis auf EasyEDA-Bibliotheksdaten (nur per Browser, Login-pflichtig)

Keine maschinenlesbare Pad-Geometrie direkt auf der Seite.

**JLCPCB interne Komponenten-API** (ohne Credentials nutzbar)

Endpunkt: `POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`

Vorher einmalig XSRF-Token holen:

```
GET https://jlcpcb.com/api/overseas-pcb-order/v1/getAll
-> Cookie XSRF-TOKEN extrahieren
-> Als Header X-XSRF-TOKEN mitsenden
```

Liefert fuer `C22371528`:

- `componentCode`, `componentSpecificationEn` (SMD2121-6P)
- `describe` mit Volltext-Beschreibung
- `attributes[]` mit Einzelwerten (Laenge, Breite, Hoehe, Spannung, ...)
- `dataManualUrl` (direkter PDF-Link, stabil)
- Preis, Lagerbestand, Kategorie

Liefert **nicht**: Pad-Koordinaten, Pad-Groessen, Kupfergeometrie.

**jlcparts** (`yaqwsx.github.io/jlcparts`)

Community-Tool (Open Source, MIT), kein offizielles JLCPCB-Produkt. Funktionsweise:

- Laedt Teildaten ueber LCSC-API (`https://ips.lcsc.com/rest/wmsc2agent/product/info/{lcscNumber}`)
- LCSC-API erfordert `LCSC_KEY` + `LCSC_SECRET` mit HMAC-SHA1-Signatur
- Diese Credentials sind privat, nicht oeffentlich verfuegbar
- Eine vorgebaute SQLite-Datenbank (`cache.zip`) liegt auf GitHub Pages und enthaelt Metadaten, aber keine Pad-Geometrie

**LCSC-API** direkt

Endpunkt `https://ips.lcsc.com/rest/wmsc2agent/product/info/C22371528` liefert ohne Credentials `424 Key Is Required`. Mit Credentials wuerden Bauteil-Attribute und Preise zurueckkommen, aber ebenfalls keine Footprint-Koordinaten.

### Fazit: Pad-Geometrie nicht per API verfuegbar

Keine der getesteten APIs liefert Pad-Koordinaten oder Kupfergeometrie. Die Footprint-Daten muessen aus dem Hersteller-Datenblatt gewonnen werden.

Die JLCPCB-API kann jedoch sinnvoll fuer folgendes verwendet werden:

- Bauteilsuche per JLCPCB-Nummer oder Stichwort
- Abruf des stabilen Datenblatt-PDF-Links (`dataManualUrl`)
- Verifikation ob ein Bauteil noch lagernd und assemblierbar ist (`stockCount`, `assemblyComponentFlag`)

### Praktische Strategie fuer den Generator

1. Footprint einmalig aus dem Datenblatt-PDF oder der EasyEDA-Weboberflaecheextrahieren und als verifizierten JSON-Eintrag im Projekt ablegen
2. JLCPCB-API optional verwenden, um den aktuellen Datenblatt-Link automatisch zu laden
3. Footprint-JSON wird versioniert und dokumentiert, Quelle und Datum werden festgehalten

Anforderung:

- Mechanische Abmessungen muessen nachvollziehbar sein
- Pad-Geometrie muss aus belastbaren Quelldaten stammen
- Orientierung, Pin-1-Markierung und Bestueckungsrotation muessen eindeutig sein

## Logische Teilsysteme

### 1. Eingabemodell

Beschreibung der Matrix, des LED-Typs, des Pitchs und des Verbindungsmusters.

### 2. Bibliotheksteil

Import oder Definition von:

- Footprint
- Pad-Geometrie
- elektrischen Pins
- Bauteil-Metadaten fuer BOM und Pick-and-Place

### 3. Platzierungsengine

Berechnung der absoluten Koordinaten jeder LED anhand von Matrixgroesse und Pitch.

### 4. Verbindungslogik

Ableitung der logischen Reihenfolge fuer Data-In/Data-Out im Serpentinenmuster.

### 5. PCB-Ausgabe

Erzeugung der eigentlichen PCB- und Fertigungsdaten.

### 6. Exportpaket

Sammlung aller erzeugten Dateien und Verpackung in eine ZIP-Datei.

## Serpentinenmuster

Das im Beispiel genannte Muster x, -x bedeutet:

- Erste Zeile von links nach rechts
- Naechste Zeile von rechts nach links
- Danach wieder alternierend

Damit ergibt sich eine fortlaufende Kette der adressierbaren LEDs mit kurzen Uebergaengen zwischen benachbarten Zeilen.

## Relevante Zusatzdateien

Fuer eine praktisch nutzbare Fertigungsausgabe sollten neben den Gerbern mindestens diese Daten mit erzeugt werden:

- BOM fuer Bauteilzuordnung
- Pick-and-Place mit Referenz, X/Y, Rotation, Layer
- Maschinenlesbare Projektbeschreibung oder Manifest
- Optional eine Netzlisten- oder Debug-Ausgabe zur Pruefung

## Upload-Ziel

Das ZIP soll moeglichst direkt auf Plattformen wie JLCPCB hochladbar sein.

Das bedeutet praktisch:

- konsistente Dateibenennung
- standardkonforme Gerber-Ausgabe
- korrekte Koordinaten und Rotation fuer Pick-and-Place
- verwertbare BOM mit Hersteller- oder Bestellreferenzen, sofern vorhanden

## Offene Punkte

Vor einer technischen Umsetzung sollten diese Punkte festgelegt oder spaeter geklaert werden:

1. Soll die erste Version echte Leiterbahnen routen oder nur Platzierung plus Datenstruktur vorbereiten?
2. ~~Wird einlagig oder zweilagig gestartet?~~ Entschieden: zweilagig. Power auf Bottom, Daten auf Top.
3. Welche Design Rules gelten fuer Mindestabstaende, Leiterbahnbreiten und Via-Groessen?
4. Welche Informationen sollen fuer BOM und Pick-and-Place verpflichtend sein?
5. Soll die Board-Kontur automatisch aus Matrixgroesse und Randabstand abgeleitet werden?
6. Welche Referenzdaten fuer den Footprint gelten als autoritativ?

## EasyEDA Pro API: Analyse und Einsatzmoeglichkeiten

### Was ist die EasyEDA Pro Extension API?

Das offizielle SDK (Apache 2.0, von JLCEDA/EasyEDA) ist unter `github.com/easyeda/pro-api-sdk` verfuegbar. Es handelt sich um ein TypeScript-basiertes Plugin-System, das innerhalb des EasyEDA Pro Editors laeuft. Das Plugin wird als ZIP-Paket in EasyEDA Pro installiert und kann dann per JavaScript/TypeScript auf das aktive Dokument zugreifen.

npm-Paket mit TypeScript-Typen: `@jlceda/pro-api-types` (aktuell v0.2.58, gut dokumentiert)

Dokumentation: `https://prodocs.easyeda.com/en/api/guide/`

### Was die API kann (getestet anhand der Typdefinitionen)

**Komponenten platzieren**

```typescript
// Bauteil aus JLCPCB-Bibliothek per UUID platzieren
const comp = await eda.pcb_PrimitiveComponent.create(
    { libraryType: ELIB_LibraryType.FOOTPRINT, libraryUuid: "...", uuid: "C22371528" },
    "TopLayer",
    x,      // in mm
    y,      // in mm
    0       // Rotation in Grad
);
```

Bauteil wird direkt aus der JLCPCB-Bibliothek per Teilenummer geladen. Kein manueller Footprint noetig.

**Netze anlegen und Pads verbinden**

Net-Namen koennen direkt beim Erstellen von Pads oder Leiterbahnen vergeben werden. Es gibt kein separates "Net erstellen" - das Netz entsteht implizit beim ersten Verwenden des Namens.

Fuer unsere Matrix bedeutet das:

```typescript
// Netze pro Matrix (global)
const NET_VCC = "+5V";
const NET_GND = "GND";

// Netze pro LED (Datenkette, Serpentinenmuster)
// LED 1
const NET_CLK1 = "CLK1";   // CLK-In von LED 1
const NET_DAT1 = "DAT1";   // DAT-In von LED 1

// LED 2 haengt am Ausgang von LED 1
const NET_CLK2 = "CLK2";   // = CLK-Out von LED 1 = CLK-In von LED 2
const NET_DAT2 = "DAT2";

// Leiterbahn mit Netz erzeugen (Top Copper)
await eda.pcb_PrimitiveLine.create(
    NET_DAT1,           // Netz-Name
    "TopLayer",         // Lage
    x1, y1, x2, y2,    // Start/End-Koordinaten
    0.2                 // Leiterbahnbreite in mm
);

// Via mit Netz (fuer Power-Durchkontaktierung)
await eda.pcb_PrimitiveVia.create(
    NET_VCC,            // Netz-Name
    x, y,               // Position
    0.6,                // Aussenduchmesser
    0.3                 // Bohrung
);
```

**Gerber-Export als ZIP**

```typescript
const gerberFile = await eda.pcb_ManufactureData.getGerberFile(
    "matrix_gerber",
    false,
    ESYS_Unit.MILLIMETER
);
await eda.sys_FileSystem.saveFile(gerberFile, "gerber.zip");
```

**Pick & Place Export**

```typescript
const pnpFile = await eda.pcb_ManufactureData.getPickAndPlaceFile(
    "matrix_pnp",
    "csv",
    ESYS_Unit.MILLIMETER
);
```

**BOM Export**

```typescript
const bomFile = await eda.pcb_ManufactureData.getBomFile("matrix_bom", "csv");
```

### Vollstaendige API-Abdeckung fuer unser Projekt

| Aufgabe | API-Methode | Status |
|---|---|---|
| PCB erzeugen | `eda.dmt_Pcb.createPcb()` | verfuegbar |
| Bauteil platzieren (per JLCPCB UUID) | `eda.pcb_PrimitiveComponent.create()` | verfuegbar (beta) |
| Leiterbahn mit Netz | `eda.pcb_PrimitiveLine.create(net, layer, x1,y1, x2,y2)` | verfuegbar |
| Via mit Netz | `eda.pcb_PrimitiveVia.create()` | verfuegbar |
| Board-Outline | `eda.pcb_PrimitiveLine.create("", "BoardOutline", ...)` | verfuegbar |
| Gerber-ZIP exportieren | `eda.pcb_ManufactureData.getGerberFile()` | verfuegbar |
| Pick & Place CSV | `eda.pcb_ManufactureData.getPickAndPlaceFile()` | verfuegbar |
| BOM CSV | `eda.pcb_ManufactureData.getBomFile()` | verfuegbar |
| Netz-Netlist lesen/schreiben | `eda.pcb_Net.setNetlist()` | verfuegbar |

### Netz-Schema fuer die LED-Matrix

Fuer eine 32x11 Matrix mit Serpentinenmuster ergibt sich folgendes Netz-Konzept:

**Globale Netze (pro Board, 2 Stueck):**
- `+5V` — VDD aller LEDs, Power-Bus auf Bottom Layer
- `GND` — GND aller LEDs, Power-Bus auf Bottom Layer

**Datenketten-Netze (pro LED-Segment, 2 Stueck pro Uebergangspunkt):**

Das Netz eines Signal-Pins wird nach dem Eingang der empfangenden LED benannt. LED N hat am DI-Pin das Netz `DAT_N`, am CI-Pin `CLK_N`. Der DO-Pin von LED N und der DI-Pin von LED N+1 teilen sich denselben Net-Namen `DAT_{N+1}`.

```
LED 1:  VDD=+5V  GND=GND  DI=DAT_1  CI=CLK_1  DO=DAT_2  CO=CLK_2
LED 2:  VDD=+5V  GND=GND  DI=DAT_2  CI=CLK_2  DO=DAT_3  CO=CLK_3
LED 3:  VDD=+5V  GND=GND  DI=DAT_3  CI=CLK_3  DO=DAT_4  CO=CLK_4
...
```

Gesamtzahl Netze bei 32x11 = 352 LEDs:
- 2 Power-Netze
- 352 DAT-Netze (DAT_1 bis DAT_352, wobei DAT_353 der Matrix-Ausgang ist)
- 352 CLK-Netze
- Gesamt: 706 Netze

### Einschraenkung: Plugin laeuft im EasyEDA Pro Editor

Die API ist kein REST-Service sondern ein Browser-Plugin. Das bedeutet:

- EasyEDA Pro muss geoeffnet sein (Web oder Desktop-App)
- Das Plugin wird im Editor-Kontext ausgefuehrt, nicht als CLI-Tool
- Keine vollautomatische Ausfuehrung ohne Nutzerinteraktion moeglich, ausser per internem Plugin-Trigger

Fuer den Generator bedeutet das: Das Python-Skript erzeugt entweder die Eingabedaten und ein begleitendes EasyEDA-Plugin-Skript, das der Nutzer dann in EasyEDA Pro startet, oder der direkte Gerber-Weg wird bevorzugt.

### Entscheidung

Der direkte Gerber-Weg wird umgesetzt. Die EasyEDA Pro Extension API ist dokumentiert (Typdefinitionen geprueft, Methoden bekannt) und kann als optionaler zweiter Ausgabepfad ergaenzt werden, ist aber nicht der primaere Weg.

Die erzeugte Gerber-ZIP kann ohne Umwege bei JLCPCB hochgeladen und bei Bedarf in EasyEDA Pro oder KiCad zur Sichtpruefung importiert werden.

## Phasenplan

### Phase 1: Datenmodell und Footprint

- Eingabeformat definieren
- LED-Footprint aus Datenblatt oder Bibliothek uebernehmen
- interne Repraesentation fuer Pads, Pins und Bauteile aufbauen

### Phase 2: Matrixgenerator

- LED-Positionen berechnen
- Referenzbezeichner erzeugen
- Serpentinenreihenfolge aufbauen

### Phase 3: Ausgabe der Fertigungsdaten

- Gerber-Ausgabe implementieren
- Pick-and-Place und BOM erzeugen
- ZIP-Export bauen

### Phase 4: Fertiger-kompatible Ausgabe

- Dateinamen und Formate an JLCPCB-Workflow anpassen
- Test mit realen Uploads und Importdialogen

### Phase 5: Erweiterungen

- Anschlusspads
- mehrere LED-Typen
- alternative Routingmuster
- Import externer Bibliotheksdaten
- optionale EasyEDA-Anbindung

## Architekturvorschlag

Eine pragmatische Struktur fuer das Projekt:

- Konfigurationsparser
- Footprint-Loader
- Matrix- und Platzierungsengine
- Netlist-/Verkettungslogik
- Gerber-Writer
- Pick-and-Place-Writer
- BOM-Writer
- ZIP-Exporter

## Zusammenfassung

Das Projekt soll ein fokussierter Generator fuer LED-Matrix-PCBs werden, der direkt Fertigungsdaten erzeugt. Die technisch sinnvollste erste Ausbaustufe ist ein klar begrenzter Direkt-Generator fuer Gerber, Pick-and-Place, BOM und ZIP-Export. Eine EasyEDA-Integration kann spaeter geprueft werden, sollte aber nicht die Grundlage der ersten Version sein.

Wichtig fuer den Projekterfolg sind vor allem drei Dinge:

- ein belastbarer LED-Footprint
- ein sauberes internes Modell fuer Platzierung und Verkettung
- eine standardkonforme Ausgabe fuer reale Fertigungsworkflows