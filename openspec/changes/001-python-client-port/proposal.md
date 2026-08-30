# Change 001: Python client port of Adis.java

**Status:** In Progress
**Datum:** 2026-08-30

## Why

The VÖBB (and other aDISWeb libraries) expose no machine-readable API. The only proven programmatic access is the aDISWeb web-frontend interaction implemented in `opacapp/opacclient`'s `Adis.java` (GPL-3.0). We port that interaction to Python so the catalogue can be searched from scripts, cron jobs, and — in a later change — an MCP server.

## What Changes

A generic Python client library `adisweb` that can talk to any aDISWeb OPAC:

- **Session bootstrap** (`_start`): GET start URL, extract `jsessionid` from nav links, discover `service` + `sp` parameters (advanced search, account), capture page form state (`updatePageform`).
- **Search** (`search`): fetch the advanced-search form, fill query fields (free-text `FELD01_x` + index select `SUCH01_x`, dropdowns), POST all form fields + toolbar button to `{opac_url};jsessionid={sid}`, parse hit list.
- **Result list parsing** (`parse_search`): both layout variants — modern `.rList li.rList_li_even/.odd` (Berlin) and legacy `table.rTable_table tbody tr`; extract id (from `javascript:htmlOnLink('…')`), title (`.rList_titel a`, images stripped), author/year (`.rList_name`), media type (image `title` → Buch/DVD/E-Book/…), availability status (green/red from image title or `verfu_ja`/`verfu_nein`), cover (`data-src`).
- **Pagination** (`searchGetPage`): page form minus toolbar fields + next/previous toolbar button `.x/.y` POSTs.
- **Detail view** (`getResultById`/`parseResult`): id → POST `selected=ZTEXT       {id}` twice (aDISWeb quirk), parse metadata table (`#R06 .aDISListe`), holdings table (`#R08/#R09 table.rTable_table` with header mapping Bibliothek/Standort/Signatur/Status), cover (`#R001 img`), reservable flag.

### Specs-Delta

- **ADDED** `adisweb-session` (specs/adisweb-session/spec.md)
- **ADDED** `catalogue-search` (specs/catalogue-search/spec.md)
- **ADDED** `catalogue-detail` (specs/catalogue-detail/spec.md)

## ADDED Requirements

### adisweb-session

#### ADDED Requirements (specs/adisweb-session/spec.md)
- **Req 1: Session bootstrap (`_start`)** — extract `jsessionid` (legacy) or form-action session token (current gen), discover `service`/`sp`, capture page form.
- **Req 2: Page form capture (`updatePageform`)** — collect non-empty input/select state for POST payloads.

### catalogue-search

#### ADDED Requirements (specs/catalogue-search/spec.md)
- **Req 1: Search (`search`)** — advanced-search form POST, both `search` (SS6) and `search_simple` (start-page `$Autosuggest` form) paths.
- **Req 2: Result list parsing (`parse_search`)** — legacy `rTable` + modern `.rList` (Berlin) variants; id from `data-ajax`/`sp=SAK`/`htmlOnLink`; type/status/cover extraction.
- **Req 3: Pagination (`searchGetPage`)** — toolbar next/previous POSTs to arbitrary page.

### catalogue-detail

#### ADDED Requirements (specs/catalogue-detail/spec.md)
- **Req 1: Detail by id (`getResultById`/`parseResult`)** — direct detail URL (current gen) or double-POST `selected=ZTEXT` (legacy).
- **Req 2: Metadata table parsing** — `#R06 .aDISListe` title/value rows, title extraction.
- **Req 3: Holdings/availability table parsing** — `#R08/#R09` header-mapped copies with status + return date.

## Changes (behavioral delta vs. current state)

Current state: no client exists; catalogue search requires manual browser use.

After this change, a Python caller can:

- `AdisClient(library=LibraryConfig.from_json("libraries/voebb.json")).search([...])` → first page of structured `SearchResult`s with title, author/year, media type, availability status, cover URL, id.
- `.search_get_page(n)` → page n of the same result set.
- `.get_result_by_id(id)` → `DetailedItem` with metadata details, per-branch copies (location, signature, status, return date), cover.
- Errors surface as typed exceptions (`OpacError` for "nicht gefunden"/message pages) instead of raw HTML.

## Downgrade

Remove the `adisweb/` package and the `libraries/` configs; the OpenSpec specs stay as documentation of the (removed) capability.
