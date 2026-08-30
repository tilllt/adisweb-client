# Design: Python port of Adis.java

## Ziel

`opacapp/opacclient`'s `Adis.java` (1986 Zeilen, GPL-3.0) nach Python übertragen — als generische, bibliotheksunabhängige Client-Library. Die Java-Quelle bleibt die Referenz; Methodennamen und Semantik werden übernommen.

## Architektur

```
adisweb/
  __init__.py          # öffentliche API: AdisClient, Dataclasses, Exceptions
  client.py            # AdisClient: Session-State, _start, search, search_get_page,
                       #   get_result_by_id, parse_search, parse_result, update_pageform
  models.py            # SearchResult, DetailedItem, Copy, Detail, MediaType, Status
  exceptions.py        # OpacError, NoResultsError, NotReachableError
  libraries.py         # LibraryConfig (dataclass) + JSON-Loader
libraries/
  voebb.json           # VÖBB-Konfiguration (baseurl, startparams)
tests/
  fixtures/            # aufgezeichnete aDISWeb-HTML-Seiten (real, anonymisiert)
  test_*.py            # Parsing-Tests gegen Fixtures + Integrationstest (optional, live)
```

## Entscheidungen

### 1. HTTP-Client: `requests` (statt httpx)
- `requests.Session` mit Cookie-Jar; aDISWeb nutzt URL-embedded `jsessionid` (keine Cookies für die Session) — trotzdem Session für HTTP-Keepalive/Header.
- User-Agent: realer Browser-UA nötig, sonst WAF-Block („Request Rejected") — konfigurierbar.
- Alternativen verworfen: `httpx` (kein Vorteil hier), `urllib` (zu low-level).

### 2. HTML-Parsing: BeautifulSoup4 (statt lxml direkt)
- CSS-Selektoren von jsoup sind 1:1 auf bs4-Selektoren übertragbar (`.rList li.rList_li_even`, `#R06 table.aDISListe`, …).
- `html.parser` als Backend (keine C-Abhängigkeit); `lxml` optional als Beschleuniger.

### 3. Session-State als Instanzattribute (wie Java)
- `s_sid`, `s_service`, `s_exts`, `s_pageform`, `s_request_count`, `s_last_page`, `s_next_button`, `s_previous_button` — gleiche Namen wie in `Adis.java` für Nachvollziehbarkeit.
- Kein Thread-Safety; ein Client = eine Session.

### 4. Bibliotheks-Konfiguration als JSON
- `libraries/<name>.json`: `baseurl`, `startparams`, optional `encoding`.
- VÖBB: `baseurl=https://www.voebb.de/aDISWeb/app`, `startparams=service=direct/0/Home/$DirectLink&sp=...` (aus opacclient Issue #13: `sp=Svb.srz.lit.verwalt-berlin.de%3A4103`; aktuell liefert die Startseite die Parameter, daher reicht `startparams` leer + Auto-Discovery).
- Weitere Bibliotheken später ergänzbar (München, Stuttgart, …) ohne Codeänderung.

### 5. Fehlerbehandlung
- `OpacError` (Basis): Meldung von `.msgpage`/`.message h1` (Wartung, Sperre).
- `NoResultsError`: `#OPACLI` enthält „nicht gefunden".
- `NotReachableError`: Netzwerkfehler/WAF.
- „Single result found" (Trefferliste mit genau 1 Treffer): Client gibt automatisch die Detailseite zurück — wie Java `parse_search_wrapped` via Zurück-nach-Trefferliste.

### 6. Detail-Aufruf: POST zweimal (aDISWeb-Quirk)
- Java macht `htmlPost` zweimal mit identischem Payload — übernehmen, kommentieren.

### 7. Kein Konto/Fernleihe in diesem Change
- `prolong`/`reserve`/Account-Login (Java-Zeilen ~1135+) sind **nicht** Teil von 001 — eigener Change, weil sie Login + Formular-Flows mit anderem Risiko brauchen.

## Offene Fragen

- Start-Parameter der VÖBB: Auto-Discovery aus der Startseite reicht (verifiziert via Browser), aber für andere Bibliotheken evtl. `startparams` in JSON nötig — Design deckt beides ab.
- WAF-Verhalten bei `requests` ohne Browser-Fingerprint: muss live getestet werden; Fallback = Playwright-gesteuerter Browser (dann als eigener Change).

## Alternativen verworfen

- **Playwright als Basis** (statt requests): robust gegen WAF, aber schwere Dependency, keine reine Library mehr, CI-Komplexität. Nur Fallback.
- **Selenium**: veraltet, gleiche Nachteile.
- **Direktes MCP-Server-Bauen zuerst**: verklebt Scraping mit Agenten-Protokoll; Client zuerst = testbar + wiederverwendbar (CLI, Cron, MCP später).
