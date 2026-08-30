# Tasks: 001 — Python client port

## Setup

- [ ] `pyproject.toml` (name `adisweb-client`, deps: requests, beautifulsoup4; dev: pytest)
- [ ] `.gitignore` (__pycache__, .venv, *.egg-info, .pytest_cache)
- [ ] README.md (Kurzvorstellung, Nutzung, Link zu openspec/)
- [ ] LICENSE (GPL-3.0 — abgeleitet von opacapp/opacclient)

## Kern: Session (`adisweb/client.py` Teil 1)

- [ ] `AdisClient.__init__(library, user_agent=...)` — `requests.Session`, Header
- [ ] `html_get(url)` / `html_post(url, data)` — requestCount-Anreicherung, Parse zu BeautifulSoup, `requestCount` aus Links extrahieren
- [ ] `update_pageform(doc)` — input/select (non-image, non-submit, non-checkbox, name nicht leer, value nicht leer) → `s_pageform`
- [ ] `_start()` — GET Startseite; `jsessionid` (Regex `;jsessionid=([0-9A-Fa-f]+)`), `service`, `sp` (SS6/SBK) aus Nav-Links; `.msgpage` → `OpacError`; Fallback `s_exts=["SS6"]`

## Suche (`adisweb/client.py` Teil 2)

- [ ] `get_advanced_search_doc()` — GET `{url};jsessionid={sid}?service={s_service}{sp_params}` (oder POST wenn advancedSearchFormBody)
- [ ] `search(queries)` — Formular füllen (Selects per id, Inputs per id; `SUCH01_x`/`FELD01_x`-Logik inkl. Nürnberg-Hack), Payload aus allen Form-Feldern + `$Toolbar_0.x/y=1`, POST, `parse_search_wrapped`
- [ ] `parse_search(doc, page)` — beide Layout-Varianten (`.rList li` + `table.rTable_table`), Felder: id (htmlOnLink-Regex), Titel, Autoren/Jahr, Medientyp (img title-Map), Status (verfügbar/nicht), Cover (data-src); `#R06` Gesamttreffer; `SingleResultFound`-Behandlung; next/prev-Button-Namen
- [ ] `search_get_page(page)` — Toolbar-Felder strippen, next/prev-POST, Schleife bis Ziel-Seite

## Detail (`adisweb/client.py` Teil 3)

- [ ] `get_result_by_id(id)` — `page!id`-Splitting → erst Seite ansteuern; Payload: pageform minus `$Toolbar_*`/`selected` + `selected=ZTEXT       {id}`; POST **zweimal**
- [ ] `parse_result(id, doc)` — Cover (`#R001 img`, erne.gif-Filter), Metadaten (`#R06 .aDISListe`), Titel-Extraktion, Reservierbarkeit (`input[value*=Reservieren]` etc.), Exemplartabelle (`#R08/#R09`, Spalten-Mapping, Rückgabedatum " am: " dd.MM.yyyy)

## Konfiguration

- [ ] `libraries.py` — `LibraryConfig` dataclass + `from_json`
- [ ] `libraries/voebb.json` — baseurl + startparams für VÖBB
- [ ] `models.py` — Dataclasses: `SearchResult` (nr, id, title/descr, type, status, cover), `DetailedItem`, `Copy` (branch, location, signature, status, return_date), `Detail` (title, content/url), MediaType/Status-Enums
- [ ] `exceptions.py` — `OpacError`, `NoResultsError`, `NotReachableError`

## Tests

- [ ] Fixtures aufzeichnen (reale VÖBB-Seiten): Startseite, Trefferliste (`.rList`), Detailseite, 0-Treffer
- [ ] `test_session.py` — _start extrahiert sid/service/sp; update_pageform
- [ ] `test_search.py` — parse_search Berlin-Variante (Titel, Typ, Status, id)
- [ ] `test_detail.py` — parse_result (Metadaten, Exemplare, Cover)
- [ ] Live-Integrationstest (opt-in, `ADISWEB_LIVE=1`): Suche "Berlin" gegen voebb.de

## Abschluss

- [ ] OpenSpec validieren (`npx @fission-ai/openspec validate …`)
- [ ] README-Beispiel ausführbar
- [ ] Commit + Push
