# Library Compatibility Scan

Stand: 2026-08-30 — Ergebnis des Live-Scans aller 46 importierten aDIS-Bibliotheken
(Suchbegriff "Berlin", Bereich "Bibliotheksbestand"). Vollständiger Bericht:
`libraries-scan.json` (per `scripts/scan_libraries.py --json` erzeugt).

## Zusammenfassung

- **OK: 46/46** — alle Bibliotheken liefern geparste Treffer mit dem aktuellen Client
- ZERO: 0 · NOFORM: 0 · ERROR: 0

## Was repariert wurde (Brave-API-Suche nach neuen Endpunkten)

Die 46 Bibliotheken teilen sich auf **drei Hosting-Gruppen** mit je eigener
aDISWeb-Konfiguration:

### 1. BSZ-Verbund (baden-württembergische Hochschulen, ~24 Bibs)

**Problem:** Die alten opacapp-Configs nutzten `sp=S127.0.0.1:<port>` (interne
IP-Referenzen). Der BSZ hat auf **symbolische Namen** umgestellt — die alten
Parameter liefern HTTP 410 Gone bzw. `connect parameter format not allowed`.

**Lösung:** Via Brave API die aktuellen symbolischen Namen gefunden und in die
Configs geschrieben (`sp=SOPACxx`). Beispiele: Aalen=SOPAC15, Furtwangen=SOPAC29,
Tübingen=SOPAC02, Stuttgart_WLB=SOPAC49, Freiburg_UB=SOPAC42, …

### 2. itk-rheinland (Dormagen, Meerbusch, Neuss, Dortmund)

**Problem:** 404 auf `webopac.itk-rheinland.de` mit alten IP-Parametern.
**Lösung:** `sp=SOPAC02` auf `webopac.itk-rheinland.de` (Neuss, Dormagen,
Meerbusch) bzw. `katalog.dortmund.de` (Dortmund).

### 3. Einzel-Instanzen (Herne, Nürnberg GNM, Zürich, München, …)

Herne und Germanisches Nationalmuseum Nürnberg: `sp=SOPAC` auf den jeweiligen
Host. Zürich/München/Stuttgart etc. funktionierten bereits mit Cookie-Sessions.

## Werkzeuge (in `scripts/`)

- `scan_libraries.py` — Live-Scan aller 46 Bibs, Report als JSON
- `find_new_endpoints.py` — Brave-Suche nach Kandidaten-URLs für tote Bibs
- `bsz_symbolic_names.py` — Extraktion der symbolischen `sp=`-Namen (BSZ-Gruppe)
- `apply_endpoints.py` — Configs mit gefundenen Endpunkten aktualisieren + verifizieren
- `find_remaining_endpoints.py` — gezielte Suche für Rest-Fälle

## Ausführen

```bash
# Einzelner Library-Check als pytest (Live, opt-in):
ADISWEB_LIVE=1 .venv/bin/python -m pytest tests/test_live_scan.py -v

# Vollständiger Scan mit Report:
.venv/bin/python scripts/scan_libraries.py --json
# Nur bestimmte Bibliotheken:
.venv/bin/python scripts/scan_libraries.py --only Berlin Zuerich Stuttgart
```
