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
    def search_availability(
        query: str,
        branch_filter: str | None = None,
        library: str = DEFAULT_LIBRARY,
        area: str = DEFAULT_AREA,
    ) -> str:
        """Search the catalogue and return per-copy availability.

        Runs the search and all detail fetches in ONE session (aDISWeb form
        state is session-bound — separate calls would break it).

        Args:
            query: search term (free text).
            branch_filter: optional substring of the library/branch name to
                filter copies (e.g. "ZLB", "Else Ury", "Namik Kemal");
                None returns all branches.
            library: library config name (see list_libraries).
            area: search scope ($Select option text).
        Returns:
            JSON: [{"id", "title", "copies": [{"branch", "location",
                   "signature", "status", "return_date"}]}, ...]
        """
        client = _client_for(library)
        try:
            out = client.get_availability_by_query(query, branch_filter=branch_filter, area=area)
        except OpacError as e:
            raise ValueError(f"Availability search failed: {e}") from e
        return json.dumps(out, ensure_ascii=False)

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

    # ---- account tools ---------------------------------------------------

    def _account_for(ausweis: str, password: str):
        from .account import Account

        return Account(ausweis, password)

    @mcp.tool()
    def get_account(ausweis: str, password: str, library: str = DEFAULT_LIBRARY) -> str:
        """Patron account overview: pending fees, card validity, borrowed
        items (with due dates), active reservations.

        Args:
            ausweis: library card / user number (Benutzernummer).
            password: account password.
            library: library config name.
        Returns:
            JSON AccountData (pending_fees, valid_until, lent[], reservations[]).
        """
        client = _client_for(library)
        try:
            data = client.get_account(_account_for(ausweis, password))
        except OpacError as e:
            raise ValueError(f"Account fetch failed: {e}") from e
        return json.dumps(data.to_dict(), ensure_ascii=False)

    @mcp.tool()
    def reserve(record_id_or_url: str, ausweis: str, password: str,
                library: str = DEFAULT_LIBRARY,
                pickup_branch: str | None = None,
                express: bool = False,
                notify: bool = True,
                confirm: bool = False) -> str:
        """Place a reservation / order (Vormerkung / Bestellung).

        Args:
            record_id_or_url: detail URL (from search results) or record id
                (e.g. "AK34063780" or "34063780").
            ausweis: library card / user number.
            password: account password.
            library: library config name.
            pickup_branch: Abholort / delivery branch as shown in the order
                form, e.g. "Friedrichshain-Kreuzberg: Familienbibliothek
                Else Ury"; None keeps the form default.
            express: check "Expressbestellung" (fast delivery, may incur
                transport fees).
            notify: notify on availability (Benachrichtigung bei
                Bereitstellung), default True.
            confirm: set True to submit the cost-bearing final button
                ("kostenpflichtig bestellen / vormerken"). Without it the
                fee warning is returned and nothing is ordered.
        Returns:
            JSON {"ok": bool, "message": str, "details": [...]}
        """
        client = _client_for(library)
        try:
            res = client.reserve(record_id_or_url, _account_for(ausweis, password),
                                 pickup_branch=pickup_branch, express=express,
                                 notify=notify, confirm=confirm)
        except OpacError as e:
            raise ValueError(f"Reserve failed: {e}") from e
        return json.dumps(res.to_dict(), ensure_ascii=False)

    @mcp.tool()
    def prolong(media_key: str, ausweis: str, password: str,
                library: str = DEFAULT_LIBRARY) -> str:
        """Renew a single borrowed item.

        Args:
            media_key: the lent item's key (input name) from get_account.
            ausweis: library card / user number.
            password: account password.
            library: library config name.
        Returns:
            JSON {"ok": bool, "message": str, "details": [...]}
        """
        client = _client_for(library)
        try:
            res = client.prolong(media_key, _account_for(ausweis, password))
        except OpacError as e:
            raise ValueError(f"Prolong failed: {e}") from e
        return json.dumps(res.to_dict(), ensure_ascii=False)

    @mcp.tool()
    def prolong_all(ausweis: str, password: str,
                    library: str = DEFAULT_LIBRARY) -> str:
        """Renew all prolongable borrowed items.

        Args:
            ausweis: library card / user number.
            password: account password.
            library: library config name.
        Returns:
            JSON {"ok": bool, "message": str, "details": [per-item lines]}
        """
        client = _client_for(library)
        try:
            res = client.prolong_all(_account_for(ausweis, password))
        except OpacError as e:
            raise ValueError(f"Prolong all failed: {e}") from e
        return json.dumps(res.to_dict(), ensure_ascii=False)

    @mcp.tool()
    def cancel_reservation(media_key: str, ausweis: str, password: str,
                           library: str = DEFAULT_LIBRARY) -> str:
        """Cancel an active reservation.

        Args:
            media_key: the reservation's media_id ("inputname|url") from
                get_account reservations.
            ausweis: library card / user number.
            password: account password.
            library: library config name.
        Returns:
            JSON {"ok": bool, "message": str, "details": [...]}
        """
        client = _client_for(library)
        try:
            res = client.cancel(media_key, _account_for(ausweis, password))
        except OpacError as e:
            raise ValueError(f"Cancel failed: {e}") from e
        return json.dumps(res.to_dict(), ensure_ascii=False)

    return mcp


def main() -> None:
    _make_server().run()


if __name__ == "__main__":
    main()
