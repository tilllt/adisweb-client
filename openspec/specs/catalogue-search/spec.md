# Catalogue Search

## Purpose

Search the VÖBB catalogue through the aDISWeb advanced-search form and parse the resulting hit list into structured records, with pagination support.

## Requirements

### Req 1: Search (`search`)

- **Eingaben:** list of search queries (field key, value, type). Supported fields follow the aDISWeb advanced form: free-text fields (`FELD01_x` + `SUCH01_x` select), dropdown fields, text fields.
- **Ablauf:** bootstrap session; fetch advanced-search document (`service` + `sp=SS6`); fill form values into the parsed document (selects by id, inputs by id); serialize all non-image/submit inputs into a POST payload; append `$Toolbar_0.x=1&$Toolbar_0.y=1`; POST to `{opac_url};jsessionid={sid}`.
- **Ausgaben:** `SearchRequestResult` with hit list, total result count, current page — or a no-results/error signal when the page says "nicht gefunden".
- **Ergebnis:** first page of results is parsed and session state advanced (page form updated, `requestCount` captured).

#### Scenario: Free-text search "Berlin"
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** query key `FELD01_1`, value `Berlin`, search index `SUCH01_1` (Freie Suche).
- **Ergebnis:** hit list parsed, total count ~1.19M, each hit carries id, title, author/year text, media type, availability status, cover URL.

### Req 2: Result list parsing (`parse_search`)

- **Eingaben:** result document.
- **Ablauf:** detect layout variant — legacy `table.rTable_table tbody tr` or modern `.rList li.rList_li_even/.rList_li_odd` (Berlin); for each row extract: id from `javascript:htmlOnLink('ID')` href, title from `.rList_titel a` (images stripped), author/year from `.rList_name` (joined with `<br />`), media type from image `title` (Buch, DVD, E-Book, …), availability status (green: "ist verfügbar"/"verfu_ja", red: "nicht verfügbar"/"verfu_nein"), cover from `.rList_cover img[data-src]`.
- **Ausgaben:** list of `SearchResult` + total count parsed from `#R06` ("Treffer: … von N") + next/previous toolbar button names.
- **Ergebnis:** structured hit list ready for consumers; page form updated for pagination.

#### Scenario: Berlin layout variant
- **Akteure:** client.
- **Eingaben:** modern `.rList` result document from voebb.de.
- **Ergebnis:** each `.rList_li_*` item yields one `SearchResult` with correct id, title, type, status.

### Req 3: Pagination (`searchGetPage`)

- **Eingaben:** target page number.
- **Ablauf:** while target != current page: clone page form, strip toolbar fields, POST with next (`$Toolbar_5`/"nächster") or previous (`$Toolbar_4`) button + `.x/.y`, parse resulting page.
- **Ausgaben:** `SearchRequestResult` for the target page.
- **Ergebnis:** paging through results works without re-running the search.

#### Scenario: Page 2 of results
- **Akteure:** client.
- **Eingaben:** page 2, current page 1.
- **Ergebnis:** second page parsed, `requestCount` advanced.
