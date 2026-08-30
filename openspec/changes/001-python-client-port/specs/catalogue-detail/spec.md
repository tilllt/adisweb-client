# Catalogue Detail

## ADDED Requirements

### Requirement: Detail by id (`getResultById` / `parseResult`)

- **Eingaben:** record id or detail URL from a search result.
- **Ablauf:** if id is an http URL, GET it directly (current-gen); else if `page!id`, navigate to that page first, then POST `selected=ZTEXT {id}` twice (legacy aDISWeb quirk); parse detail document.
- **Ausgaben:** `DetailedItem` with title, metadata details, cover, copies, reservable flag.

#### Scenario: Detail via direct URL (VÖBB)
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** `detail_url` from a search hit (`…?sp=SPROD00&sp=SAK15065844`).
- **Ergebnis:** `DetailedItem` with title "Berlin", 19 detail rows, 1 copy (ZLB branch, status "Verfügbar").

#### Scenario: Detail via legacy double-POST
- **Akteure:** client, legacy aDISWeb OPAC.
- **Eingaben:** `page!id` result id.
- **Ergebnis:** detail fetched after two identical POSTs.

### Requirement: Metadata table parsing

- **Eingaben:** detail document.
- **Ablauf:** parse `#R06 .aDISListe table tbody tr` rows as title/value pairs; links become URL details; title = value of row whose title contains "Titel" (split on `[:/;]`); fall back to "Gesamtwerk"/"Zeitschrift".
- **Ausgaben:** ordered `Detail` list + `title`.

#### Scenario: Standard record
- **Akteure:** client.
- **Eingaben:** record with Titel/Autor/Verlag rows.
- **Ergebnis:** title extracted, details list contains author and publisher.

### Requirement: Holdings/availability table parsing

- **Eingaben:** detail document.
- **Ablauf:** find `#R08`/`#R09 table.rTable_table`; map header columns (Bibliothek→branch, Standort→location, Signatur→signature, Status/Hinweis/Leihfrist→status); parse " am: " pattern for return date (dd.MM.yyyy).
- **Ausgaben:** list of `Copy` objects with branch, location, signature, status, return date.

#### Scenario: Copy with return date
- **Akteure:** client.
- **Eingaben:** holdings row "ausgeliehen am: 15.09.2026".
- **Ergebnis:** copy status "ausgeliehen", return date 2026-09-15.
