# Catalogue Search

## ADDED Requirements

### Requirement: Search (`search` / `search_simple`)

- **Eingaben:** search query (string) + search area (`$Select` option text); or list of field key/value pairs for the advanced form.
- **Ablauf:** bootstrap session; set values in the start-page form DOM (`$Autosuggest`/`$Select`), serialize payload, append `$Button=Suchen`, POST to session base URL.
- **Ausgaben:** `SearchRequestResult` with hit list, total count, page — or `NoResultsError` on "nicht gefunden".
- **Ergebnis:** first page of results parsed; session state advanced.

#### Scenario: Free-text search "Berlin" (VÖBB)
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** query `Berlin`, area `Bibliotheksbestand`.
- **Ergebnis:** 22 hits parsed, total ~1.19M; each hit carries id, title, author/year, media type, availability, cover.

#### Scenario: BSZ library (Aalen) with symbolic sp=
- **Akteure:** client, BSZ OPAC.
- **Eingaben:** config with `startparams` `service=direct/0/Home/$DirectLink&sp=SOPAC15`.
- **Ergebnis:** search works (old `S127.0.0.1:<port>` params return 410).

### Requirement: Result list parsing (`parse_search`)

- **Eingaben:** result document.
- **Ablauf:** detect layout — legacy `table.rTable_table tbody tr` or modern `ul.rList li.rList_li`; per row extract: id from `data-ajax`/`sp=SAK…`/`htmlOnLink('…')`, title from `.rList_titel a` (images stripped), author/year from `.rList_name`/`.rList_jahr`, media type from image `title`, availability (green/red, `availability-green/red.svg`), cover from `.rList_cover img[data-src]`; total count from `#R06` ("Treffer: N" or "Treffer: N von M").
- **Ausgaben:** list of `SearchResult` + total + next/prev toolbar names.

#### Scenario: Berlin layout variant
- **Akteure:** client.
- **Eingaben:** modern `.rList` document from voebb.de.
- **Ergebnis:** each `.rList_li` yields one `SearchResult` with correct id (`AK…`), type, status, detail_url.

#### Scenario: Legacy layout (Stuttgart)
- **Akteure:** client.
- **Eingaben:** document with `javascript:htmlOnLink('AK…')` hrefs.
- **Ergebnis:** ids extracted via `htmlOnLink` regex.

### Requirement: Pagination (`searchGetPage`)

- **Ablauf:** while target != current page: clone page form, strip toolbar fields, POST next/previous button `.x/.y`, parse resulting page.
- **Ausgaben:** `SearchRequestResult` for the target page.

#### Scenario: Page 2 of results
- **Akteure:** client.
- **Eingaben:** page 2, current page 1.
- **Ergebnis:** second page parsed, `requestCount` advanced.
