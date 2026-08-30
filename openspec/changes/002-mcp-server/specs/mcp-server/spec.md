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

### Requirement: stdio transport

- **Ablauf:** run `python -m adisweb.mcp_server`; MCP over stdin/stdout (JSON-RPC).
- **Ergebnis:** any MCP client can connect and call the tools.

#### Scenario: Hermes connects
- **Akteure:** Hermes gateway, server.
- **Eingaben:** `hermes mcp add adisweb --command python --args -m adisweb.mcp_server`.
- **Ergebnis:** `mcp_adisweb_search` etc. available in-session.
