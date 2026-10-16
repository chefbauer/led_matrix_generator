# PLAN: Neue Anforderungen LED-Matrix-Generator
Stand: 2026-10-16 · Abarbeitbar durch Agent selbstständig. Nach JEDEM Generier-Lauf: beide PNG-Seiten mit Vision prüfen (fester Schritt, kein Überspringen).

## Festgelegte Design-Entscheidungen (mit User geklärt)
1. **Board:** immer exakt `cols*pitch × rows*pitch`, Rand = pitch/2 (margin-Option entfällt) → nahtloses Anreihen.
2. **Rückseite (B.Cu):** NUR zwei vertikale Stromschienen GND+VCC, **MITTIG nebeneinander** (treffen sich in der Mitte, Mindestabstand GAP untereinander, Schema 1.0mm), je Breite ≥ 1/3 Boardbreite, durchgehend = keine Risse/Stubs. Sonst nichts auf B.Cu außer den 6 Anschlusspads: GND+VCC je oben UND unten (Module aneinander löten), DIN oben (zu L1), DOUT unten (zu L64; Seite folgt der DO-Pad-Lage der letzten Zeile durch die Rotationen). **DIN und DOUT erhalten je 1 Via** vom B.Cu-Anschlusspad zur F.Cu-Datenkette (User 2026-10-16).
3. **Vorderseite (F.Cu):** **EINE** horizontale Schiene pro Reihenlücke, **abwechselnd GND/VCC** (User 2026-10-16, korrigiert: nicht zwei pro Lücke). Voraussetzung: **LED-Zeilen alternierend um 180° gedreht** (matrix.py umstellen!) — dadurch zeigen in jeder Lücke zwei gleichartige Pads aufeinander (GND↔GND, VDD↔VDD) und die Schiene berührt beide direkt; Lücke unter Zeile r = GND für r gerade, VCC für r ungerade. Randzonen = Net der aussen zeigenden Power-Pads der Randzeilen (180°-Modus: oben+unten VCC; ±90°-Modus: oben+unten GND).
   3b. **Rotation ±90° statt 180° (User-Variante, Schema layout_front.png):** Zeilen alternierend −90/+90 gedreht. Vorteile: DIN/DOUT fallen beide unten-links zusammen (Datenanschluss an einer Kante). Fit: Pad-Ausdehnung vertikal 0,85mm → Lücke 1,30mm bei pitch 3.0, Schiene+Clearance 0,427mm passt (0,87mm Rest); horizontal 1,40mm zwischen Spalten. Schema-Skript: ROT_MODE = "90"|"180", beide Bilder werden generiert. **Stichleitungen**: 3 Vias pro Schiene, 2 mm Abstand, mittig auf der B.Cu-Schiene (5 mm ging nicht in 8-mm-Schiene, User 2026-10-16). Datenkette kreuzt die Schienen (DO/DI-Pads liegen in verschiedenen Lücken) → Schienen brauchen Schlitze/Notchen an den Kreuzungen; Minimalabstand der Schiene zu artfremden Pads = DR.CLEARANCE. Fit (echte Footprintmasse 0.45×0.65, ±0.625/±0.475): Lückenhöhe = pitch − 1.6 mm = 1.4 mm bei pitch 3.0 → Schiene 0.127 + 2×0.15 Clearance = 0.427 mm passt deutlich; Pad-Stubs an Power-Pads (x−dx zur oberen Zeile, x+dx zur unteren).
4. **Keine Castellations** (Economy-PCBA unterstützt sie nicht): DIN/DOUT = **bohrungslose SMD-Kantenpads** an der Unterkante (flush, 0.75×0.3mm, x=0.2..0.95 bzw. W−0.95..W−0.2). Power-Anschluss = **freigelegte Rail-Enden** (Mask-Opening) am unteren Rand der Schienen.
5. **Unterleisten-Budget (Feasibility C5):** DIN-Pad (0.95) + Daten-Eintrittskanal (bis x≈2.3) + GND-Lötzone ≥1mm → rail_w ≥ ~3.3mm → W ≥ ~10mm. Spiegelsymmetrisch rechts für DOUT.
6. **Datenkette: Rückseite (B.Cu), Via-am-Pad.** Begründung (verifiziert an Pad-Geometrie): XL-1615 Pads = DO(−.625,+.475) VDD(+.625,+.475) GND(−.625,−.475) DI(+.625,−.475); die Reihen-Schienen-Detours blockieren vorne jeden Weg vom DO/DI-Pad weg → Kette vorne nicht routbar bei 2.5mm. Deshalb: Via-in-Pad (0.3-Bohrung in 0.45×0.65-Pad, Annular 0.075mm — JLCPCB-toleriert, Signalstrom klein) an DO/DI, L-Jogs in den Reihenkorridoren hinten, Gräben in den Rückseiten-Schienen an den Kreuzungen. Kettenführung: **horizontale Serpentine, L1 oben-links, L8 oben-rechts, zeilenweise abwärts** (matrix.py umzustellen). Randzonen: DIN oben (L1-Seite), DOUT unten (L64-Seite, Parität).
7. **Machbarkeitsprüfung vor allem anderen** (`feasibility.py` ✓): C1 Pad-Geometrie, C2 Reihenlücke, C3 Detour-Band, C4 Schienenbreite ≥W/3, C5 Unterleisten-Budget/Min-Board 10×10.
8. **Testmatrix:** XL-1615RGBC (C41413180), 8×8, pitch 2.5 mm → Geometrie-Rechnung geht auf (Rail 6.67mm, Detour-Band 0.025mm innerhalb, Lötzone 5.77mm).

## Phasen
- [x] P0 Umgebung: Hermes-Python 3.14 + pygerber 2.4.3 + Pillow installiert, 5×5 läuft.
- [x] P1 `src/feasibility.py`: `check_matrix(...)` mit C1..C5, in `generate.py` als erster Schritt eingebaut. 8×8@2.5 ✓.
- [x] P2 `matrix.py`: Spalten-Serpentine ab unten-links, Rotation 0°, `board_size` = exakt cols×rows×pitch.
- [x] P2b `src/power_grid.py` (NEU, Geometrie zentral für alle Layer): Schienen, Detours, Stitching-Vias, Exposed-Ends, Eckenpads. Test 8×8@2.5: 32 Vias, Detours korrekt (aussen 0.3 / innen 0.15).
- [ ] P3 `bottom_copper.py`: zwei vertikale Schienen als Rechtecke MINUS Datendurchtritts-Gräben; DIN/DOUT-Kantenpads; alte per-Reihe-Schienen/right_cap/Regex-Hacks entfernen.
- [ ] P4 `top_copper.py`: Reihen-Schienen aus `power_grid.row_rails` (Segmentbreiten beachten!), Stitching-Vias, LED-Pads; Datenkette auf B.Cu mit Via-in-Pad + L-Jogs (Router H/V anpassen), Gräben mit dem Router abstimmen.
- [ ] P5 Mask/Silkscreen: Mask-Openings für Exposed-Ends + Kantenpads; Labels DIN/DOUT/GND/VCC.
- [ ] P6 Test: `cfg/XL-1615RGBC_8x8.cfg` pitch 2.5 → generieren, **beide PNG-Seiten mit Vision prüfen**, trace_net-DRC, iterieren bis sauber.
- [ ] P7 Regression: SK9822-Configs (6-Pin) mit neuem Schema; README aktualisieren.

## Bekannte Altfehler (müssen mit P3/P4 verschwinden)
- Unterste Rückseiten-Schiene schwimmend, rechts funktionslose Stubs (`right_cap`, Regex `X150000→X1500000`).
- Überlappende Vias unten links, Silkscreen auf Kupfer, Pads an Kontur angeschnitten.

## Verifikations-Loop (jede Iteration)
1. `python src/generate.py --config cfg/XL-1615RGBC_8x8.cfg`
2. Vision: `output/*_front.png` + `*_back.png` gegen Requirements prüfen (Anschlüsse unten, Schienen ≥1/3, keine Kurzschlüsse, keine angeschnittenen Pads, Kettenverlauf korrekt).
3. `python src/trace_net.py output/XL-1615RGBC_8x8.zip` → VCC/GND-Flächen ansehen.
4. Erst wenn Vision + trace_net sauber: Phase abschließen.
