# Tasks: 002 — MCP server wrapper

## Spec

- [x] `proposal.md` + `design.md` erstellt
- [ ] `specs/mcp-server/spec.md` (ADDED, mit Scenarios)
- [ ] OpenSpec validieren (`npx @fission-ai/openspec validate 002-mcp-server`)

## Implementierung

- [ ] `adisweb/models.py`: `to_dict()`-Helper für SearchResult/DetailedItem/Copy/Detail
- [ ] `adisweb/mcp_server.py` (FastMCP, stdio):
  - [ ] `list_libraries()` — Namen aus `libraries/*.json`
  - [ ] `search(query, library="Berlin", area="Bibliotheksbestand")` — Treffer als JSON
  - [ ] `get_detail(record_id_or_url, library="Berlin")` — DetailedItem-JSON
  - [ ] `get_availability(record_id_or_url, library="Berlin")` — Copies-JSON
  - [ ] Fehlerbehandlung (unbekannte Library, OpacError → MCP-Fehler)
- [ ] `pyproject.toml`: optional extra `mcp = ["mcp>=1.0"]`

## Tests

- [ ] MCP-Handshake (initialize → tools/list) per `npx @modelcontextprotocol/inspector` oder direktem JSON-RPC
- [ ] Tool-Call `search` live gegen Berlin (ADISWEB_LIVE)
- [ ] Tool-Call `get_detail` live gegen Berlin
- [ ] Tool-Call mit unbekannter Library → saubere Fehlermeldung

## Abschluss

- [ ] README: MCP-Nutzung dokumentieren
- [ ] Commit + Push
