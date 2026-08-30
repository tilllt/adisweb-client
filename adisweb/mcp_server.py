"""MCP server for the aDISWeb OPAC client.

Exposes the `adisweb` library as MCP tools over stdio:

    python -m adisweb.mcp_server

Tools:
    list_libraries()                 -> library names
    search(query, library, area)     -> first page of hits as JSON
    get_detail(record_id_or_url, library) -> full record detail as JSON
    get_availability(record_id_or_url, library) -> per-copy availability

Each tool call creates a fresh client session (AdisClient is stateful and
not thread-safe; a fresh session per call is correct and simple).
"""

from __future__ import annotations

from pathlib import Path

from .client import AdisClient
from .exceptions import OpacError
from .libraries import load_library
from .models import copies_to_dict, detail_to_dict, search_result_to_dict

DEFAULT_LIBRARY = "Berlin"
DEFAULT_AREA = "Bibliotheksbestand"

LIBRARIES_DIR = Path(__file__).resolve().parent.parent / "libraries"


def _library_names() -> list[str]:
    return sorted(p.stem for p in LIBRARIES_DIR.glob("*.json"))


def _client_for(library: str) -> AdisClient:
    if library not in _library_names():
        available = ", ".join(_library_names())
        raise ValueError(
            f"Unknown library '{library}'. Available: {available}"
        )
    return AdisClient(load_library(library))


def _make_server():
    import json

    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("adisweb", version="0.1.0")

    @mcp.tool()
    def list_libraries() -> str:
        """List all configured aDISWeb libraries (e.g. Berlin, Zuerich, ...).

        Returns a JSON array of library names.
        """
        return json.dumps(_library_names())

    @mcp.tool()
    def search(
        query: str,
        library: str = DEFAULT_LIBRARY,
        area: str = DEFAULT_AREA,
    ) -> str:
        """Search the catalogue of a library.

        Args:
            query: search term (free text).
            library: library config name (see list_libraries).
            area: search scope ($Select option text), default Bibliotheksbestand.
        Returns:
            JSON: {"total": int, "page": int, "results": [hit, ...]}
        """
        client = _client_for(library)
        try:
            res = client.search_simple(query, area=area)
        except OpacError as e:
            raise ValueError(f"Search failed: {e}") from e
        return json.dumps({
            "total": res.total_result_count,
            "page": res.page,
            "results": [search_result_to_dict(r) for r in res.results],
        }, ensure_ascii=False)

    @mcp.tool()
    def get_detail(
        record_id_or_url: str,
        library: str = DEFAULT_LIBRARY,
    ) -> str:
        """Fetch the full detail view of a catalogue record.

        Args:
            record_id_or_url: detail URL (from search results) or record id.
            library: library config name.
        Returns:
            JSON DetailedItem (title, cover, details rows, copies, reservable).
        """
        client = _client_for(library)
        try:
            detail = client.get_result_by_id(record_id_or_url)
        except OpacError as e:
            raise ValueError(f"Detail fetch failed: {e}") from e
        return json.dumps(detail_to_dict(detail), ensure_ascii=False)

    @mcp.tool()
    def get_availability(
        record_id_or_url: str,
        library: str = DEFAULT_LIBRARY,
    ) -> str:
        """Per-copy availability of a catalogue record.

        Args:
            record_id_or_url: detail URL (from search results) or record id.
            library: library config name.
        Returns:
            JSON array of copies (branch, location, signature, status, return_date).
        """
        client = _client_for(library)
        try:
            detail = client.get_result_by_id(record_id_or_url)
        except OpacError as e:
            raise ValueError(f"Availability fetch failed: {e}") from e
        return json.dumps(copies_to_dict(detail.copies), ensure_ascii=False)

    return mcp


def main() -> None:
    _make_server().run()


if __name__ == "__main__":
    main()
