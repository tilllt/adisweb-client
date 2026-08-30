# Design: MCP server wrapper

## Ziel

Den `adisweb`-Client als MCP-stdio-Server exponiert, damit Agenten (Hermes,
Claude Desktop, …) ohne eigenen Code suchen und Details abrufen können.

## Architektur

```
adisweb/
  mcp_server.py     # FastMCP-Server: list_libraries, search, get_detail, get_availability
pyproject.toml      # optional extra: [project.optional-dependencies] mcp = ["mcp"]
```

## Entscheidungen

### 1. Framework: offizielles `mcp`-Paket (FastMCP)
- `from mcp.server.fastmcp import FastMCP` — minimaler Boilerplate, stdio out of the box.
- Alternativen verworfen: eigene JSON-RPC-Implementierung (Fehlerquelle),
  `fastmcp`-Separatorpaket (das `mcp`-Paket reicht).

### 2. Statefulness: jede Tool-Call-Session frisch
- `AdisClient` ist zustandsbehaftet (eine Session pro Instanz) und nicht
  thread-safe. Ein MCP-Server kann parallele Aufrufe bekommen.
- Lösung: pro Tool-Call `AdisClient(load_library(...))` neu instanziieren —
  kostet ~1 Request (Session-Bootstrap), ist aber korrekt und einfach.
- Kein globaler Session-Pool in Change 002 (wäre Optimierung für später).

### 3. JSON-Serialisierung
- Dataclasses (`SearchResult`, `DetailedItem`, `Copy`, `Detail`) sind nicht
  direkt JSON-serialisierbar. Helper `to_dict()` in `models.py` (oder inline
  im Server) wandeln sie in dicts um; Enums (`MediaType`, `Status`) → `.name`.
- MCP-Tools geben dicts/Listen zurück, FastMCP serialisiert sie.

### 4. Parameter-Design
- `search(query: str, library: str = "Berlin", area: str = "Bibliotheksbestand")`
- `get_detail(record_id_or_url: str, library: str = "Berlin")`
- `get_availability(record_id_or_url: str, library: str = "Berlin")`
- `list_libraries() -> list[str]` (aus `libraries/*.json`)

### 5. Fehlerbehandlung
- `OpacError`/`NotReachableError`/`NoResultsError` → MCP-Tool-Fehler
  (FastMCP: Exception im Tool → Fehlerantwort an den Client).
- Unbekannte Bibliothek → klare Fehlermeldung mit verfügbaren Namen.

## Alternativen verworfen

- **HTTP/SSE-Server**: für lokale Agenten unnötig; stdio ist einfacher und
  in Hermes nativ unterstützt (`hermes mcp add`).
- **Session-Pool/Caching**: korrekt, aber Over-Engineering für 002; kommt
  erst wenn nötig.
- **Tools pro Bibliothek** (`search_berlin`, `search_zuerich`): bläht die
  Tool-Oberfläche auf; `library`-Parameter ist sauberer.

## Offene Fragen

- Soll `search` auch Pagination exponieren (`page`-Parameter)? Erstmal nein —
  `search_get_page` existiert im Client, kann in 003 ergänzt werden.
