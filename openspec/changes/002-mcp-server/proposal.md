# Change 002: MCP server wrapper

**Status:** In Progress
**Datum:** 2026-08-30

## Why

The `adisweb` client (change 001) is a reusable library, but agents/LLMs
cannot call it directly. An MCP (Model Context Protocol) server exposes the
client's search/detail/availability capabilities as tools that any MCP
client (Hermes, Claude Desktop, …) can invoke.

## What Changes

A thin stdio MCP server (`adisweb/mcp_server.py`) wrapping `AdisClient`:

- **`list_libraries`** → names of all configured libraries (`libraries/*.json`)
- **`search(query, library, area)`** → first page of hits as JSON (id,
  title, type, status, cover, detail_url)
- **`get_detail(record_id_or_url, library)`** → full `DetailedItem` JSON
  (metadata rows, copies, cover, reservable)
- **`get_availability(record_id_or_url, library)`** → per-copy availability
  (branch, location, signature, status, return_date) — a convenience view of
  get_detail's copies

Behavioral delta: before this change, only Python code could use the client;
after it, any MCP client can search and inspect records across all 46
libraries with no code.

### Specs-Delta

- **ADDED** `mcp-server` (specs/mcp-server/spec.md)

## ADDED Requirements

### mcp-server

#### ADDED Requirements (specs/mcp-server/spec.md)
- **Req 1: Tool `list_libraries`** — returns configured library names.
- **Req 2: Tool `search`** — query + optional library/area → hit list JSON.
- **Req 3: Tool `get_detail`** — record id/URL → DetailedItem JSON.
- **Req 4: Tool `get_availability`** — record id/URL → per-copy availability.
- **Req 5: stdio transport** — MCP over stdin/stdout; each tool call spins a
  fresh client session (stateless, safe for concurrent calls).

## Changes (behavioral delta vs. current state)

Current state: `AdisClient` usable from Python only.

After this change:

- `adisweb/mcp_server.py` runs as an MCP stdio server (`python -m adisweb.mcp_server`).
- A client can call `search(query="Berlin")`, `get_detail(record_id_url=…)`,
  `get_availability(...)` and `list_libraries()` and receive JSON.
- No library config needed at call time — library names resolve to
  `libraries/*.json`; default library is `Berlin`.

## Downgrade

Remove `adisweb/mcp_server.py`, drop the `mcp` extra from `pyproject.toml`,
delete the `mcp-server` spec and this change's `specs/` folder.
