# Contributing

Danke für dein Interesse an `adisweb-client`! Das Projekt ist ein
KI-unterstützt entwickeltes Community-Projekt (siehe Autorschaft in der
README) — Beiträge aller Art sind willkommen.

## Was wir besonders suchen

**Verifikationen und PRs für die Konto-/Bestell-Funktionen anderer
aDISWeb-Bibliotheken.** Bisher sind Suche/Detail/Verfügbarkeit für alle 46
Bundled-Configs verifiziert, aber die Account-Features (Login, Ausleihen,
Bestellungen, Vormerkungen, Verlängern, Reservieren) wurden **nur gegen die
VÖBB (Berlin)** live getestet. Wenn du eine andere aDISWeb-Bibliothek nutzt
(Stuttgart, München, Zürich, Herne, Dormagen, …), hilf uns, sie auf den
gleichen Stand zu bringen:

1. **Teste** die Account-Funktionen mit deiner Bibliothek:
   ```bash
   .venv/bin/python -m adisweb.mcp_server   # oder direkt via AdisClient
   ```
   bzw. den Live-Scan:
   ```bash
   ADISWEB_LIVE=1 .venv/bin/python -m pytest tests/test_live_scan.py -v
   ```
2. **Dokumentiere** dein Testergebnis (welche Tools funktionieren, welche
   nicht, Fehlermeldungen).
3. **Reiche einen PR ein** mit:
   - Config-Update in `libraries/` (falls der Endpunkt/`startparams` abweicht)
   - Code-Anpassungen für abweichende aDISWeb-Layouts (falls nötig)
   - dem Testergebnis als Abschnitt in der PR-Beschreibung

## Sonstige Beiträge

- **Neue Bibliotheken:** JSON-Config nach `libraries/` legen (Format siehe
  README), dann `scripts/scan_libraries.py` ausführen.
- **Bug-Reports:** Issue mit Reproduktionsschritten, betroffener Bibliothek
  und erwartetem vs. tatsächlichem Verhalten.
- **Docs:** README/COMPATIBILITY.md/OpenSpec-Verbesserungen.

## Hinweise

- Keine Credentials oder persönlichen Daten in Commits/Issues/PRs.
- Tests müssen grün bleiben: `.venv/bin/python -m pytest tests/ -q`
- Commit-Messages: prägnant, englisch.
- Das Projekt folgt OpenSpec (siehe `openspec/`) — größere Änderungen
  bitte als Change Proposal dokumentieren.
