# Catalogue Detail

## Purpose

Fetch and parse the single-record detail view of a catalogue entry: metadata table, cover, and the holdings/availability table per branch.

## Requirements

### Req 1: Detail by id (`getResultById` / `parseResult`)

- **Eingaben:** record id (as returned in search results, optionally `page!id`), session state.
- **Ablauf:** if id contains `!`, navigate to that result page first; build POST payload from page form, strip `$Toolbar_*`/`selected` fields, add `selected=ZTEXT       {id}`; POST twice (aDISWeb quirk: two identical POSTs required); parse detail document.
- **Ausgaben:** `DetailedItem` with title, metadata details list, cover URL, availability copies, reservable flag + reservation id.
- **Ergebnis:** full record detail including per-branch holdings.

#### Scenario: Detail of a search hit
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** id from a previous search result.
- **Ergebnis:** `DetailedItem` with title, details (Autor, Verlag, ISBN, …), holdings rows (Bibliothek, Standort, Signatur, Status), cover if present.

### Req 2: Metadata table parsing

- **Eingaben:** detail document.
- **Ablauf:** parse `#R06 .aDISListe table tbody tr` rows as title/value pairs; links become URL details; title = first value of a row whose title contains "Titel" (split on `[:/;]`); fall back to "Gesamtwerk"/"Zeitschrift" detail rows.
- **Ausgaben:** ordered list of `Detail` (title, content-or-URL) + `title`.
- **Ergebnis:** structured metadata.

#### Scenario: Standard record
- **Akteure:** client.
- **Eingaben:** record with Titel/Autor/Verlag rows.
- **Ergebnis:** title "Berlin", details list containing author and publisher.

### Req 3: Holdings/availability table parsing

- **Eingaben:** detail document.
- **Ablauf:** find `#R08`/`#R09 table.rTable_table`; map header columns (Bibliothek/Library → branch, Standort/Location → location, Signatur/Call number → signature, Status/Hinweis/Leihfrist/Verfügbarkeit → status); parse status text for return date pattern " am: " (dd.MM.yyyy).
- **Ausgaben:** list of `Copy` objects with branch, location, signature, status, return date.
- **Ergebnis:** per-copy availability known.

#### Scenario: Copy with return date
- **Akteure:** client.
- **Eingaben:** holdings row with status "ausgeliehen am: 15.09.2026".
- **Ergebnis:** copy status "ausgeliehen", return date 2026-09-15.
