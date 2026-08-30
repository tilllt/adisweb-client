# MCP Server

## ADDED Requirements

### Requirement: Tool `list_libraries`

- **Eingaben:** none.
- **Ablauf:** enumerate `libraries/*.json`.
- **Ausgaben:** list of library names (e.g. `["Aalen_HS", "Berlin", …]`).

#### Scenario: Client asks for available libraries
- **Akteure:** MCP client, server.
- **Ergebnis:** names of all configured libraries returned; caller can pick one for search.

### Requirement: Tool `search`

- **Eingaben:** `query` (string), optional `library` (default `Berlin`), optional `area` (default `Bibliotheksbestand`).
- **Ablauf:** instantiate `AdisClient` for the library, run `search_simple(query, area)`.
- **Ausgaben:** JSON list of hits (id, type, status, cover, detail_url, innerhtml) + total count.
- **Ergebnis:** first page of structured hits returned to the client.

#### Scenario: Search "Berlin" in VÖBB
- **Akteure:** MCP client.
- **Eingaben:** `search(query="Berlin")`.
- **Ergebnis:** 22 hits with ids (`AK…`), type `BOOK`, status `GREEN`, total ~1.19M.

#### Scenario: Unknown library
- **Akteure:** MCP client.
- **Eingaben:** `search(query="Berlin", library="NichtDa")`.
- **Ergebnis:** tool error naming the library and listing available names.

### Requirement: Tool `get_detail`

- **Eingaben:** `record_id_or_url` (detail URL or record id), optional `library`.
- **Ablauf:** `AdisClient.get_result_by_id(...)`.
- **Ausgaben:** JSON `DetailedItem` (title, cover, details rows, copies, reservable).
- **Ergebnis:** full record metadata + holdings.

#### Scenario: Detail of a search hit
- **Akteure:** MCP client.
- **Eingaben:** detail_url from a search result.
- **Ergebnis:** title, 19 detail rows, 1 copy (ZLB, "Verfügbar"), reservable true.

### Requirement: Tool `get_availability`

- **Eingaben:** `record_id_or_url`, optional `library`.
- **Ablauf:** `AdisClient.get_result_by_id(...)`; return only copies.
- **Ausgaben:** JSON list of copies (branch, location, signature, status, return_date).

#### Scenario: Availability of a hit
- **Akteure:** MCP client.
- **Eingaben:** detail_url from a search result.
- **Ergebnis:** per-copy availability rows without the full metadata.

### Requirement: Tool `search_availability`

- **Eingaben:** `query`, optional `branch_filter` (substring of branch name),
  optional `library`, optional `area`.
- **Ablauf:** `AdisClient.get_availability_by_query(query, branch_filter)` —
  search + detail fetches in ONE session (aDISWeb form state is
  session-bound; separate tool calls would break the identity/requestCount
  chain).
- **Ausgaben:** JSON list of `{id, title, copies:[{branch, location,
  signature, status, return_date}]}`.

#### Scenario: Which One Piece volumes are available at ZLB
- **Akteure:** MCP client.
- **Eingaben:** `search_availability(query="One Piece 86", branch_filter="ZLB")`.
- **Ergebnis:** every hit with its ZLB copies incl. signature (e.g. "Ju 600
  OnePie 1:86") and status ("Verfügbar"/"Ausgeliehen"/"Reserviert").

### Requirement: Tool `get_loans`

- **Eingaben:** `ausweis`, `password`, optional `library`.
- **Ablauf:** `AdisClient.get_loans(account)`.
- **Ausgaben:** JSON array of currently borrowed items (title, author,
  media_type, return_date, prolongable).

#### Scenario: What have we borrowed
- **Akteure:** MCP client.
- **Eingaben:** `get_loans(ausweis=…, password=…)`.
- **Ergebnis:** 14 loans incl. One Piece volumes with due dates.

### Requirement: Tool `get_orders`

- **Eingaben:** `ausweis`, `password`, optional `library`.
- **Ablauf:** `AdisClient.get_orders(account)` — opens the order areas via
  `selected=ZTEXT *SZW` (Bestellwünsche) and `*SZB` (Magazin-Bestellungen),
  reloading the overview between areas (identity/requestCount rotate).
- **Ausgaben:** JSON `{"orders": [{branch, title, note}],
  "magazine_orders": [{branch, title, note}]}`.

#### Scenario: Pending orders overview
- **Akteure:** MCP client.
- **Eingaben:** `get_orders(ausweis=…, password=…)`.
- **Ergebnis:** 3 Bestellwünsche (Else Ury) + 8 Magazin-Bestellungen (ZLB)
  with order timestamps.

### Requirement: Tool `reserve` (extended)

- **Eingaben:** `record_id_or_url`, `ausweis`, `password`, optional
  `pickup_branch`, `express`, `notify`, `confirm`, `max_fee`, `library`.
- **Ablauf:** login → search by bare id → detail (`selected=ZTEXT AK<id>`)
  → "Bestellen/Vormerken" → order form (pickup branch `$Select`,
  Expressbestellung `$Checkbox`, notification `$Select$0`) → "Weiter" →
  cost page → final "kostenpflichtig bestellen / vormerken" submit.
- **Ausgaben:** JSON `{ok, message, details}`.
- **Sicherheit:** `confirm=False` (default) returns the quoted cost without
  ordering; `max_fee` refuses orders exceeding the cap even with
  `confirm=True`. Cost parsing handles "Gebühren in Höhe von 2.00 Euro"
  (order fee) and "Transport kostet bei Bereitstellung 1.00 Euro"
  (magazine transport).

#### Scenario: Express order to Else Ury
- **Akteure:** MCP client.
- **Eingaben:** `reserve("AK34063780", ausweis=…, password=…,
  pickup_branch="Friedrichshain-Kreuzberg: Familienbibliothek Else Ury",
  express=True, confirm=False)`.
- **Ergebnis:** "Kostenpflichtige Bestellung (2.00 EUR) — mit confirm=True
  bestätigen"; nothing ordered.

### Requirement: stdio transport

- **Ablauf:** run `python -m adisweb.mcp_server`; MCP over stdin/stdout (JSON-RPC).
- **Ergebnis:** any MCP client can connect and call the tools.

#### Scenario: Hermes connects
- **Akteure:** Hermes gateway, server.
- **Eingaben:** `hermes mcp add adisweb --command python --args -m adisweb.mcp_server`.
- **Ergebnis:** `mcp_adisweb_search` etc. available in-session.
