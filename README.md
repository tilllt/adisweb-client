# adisweb-client

Python client for **aDISWeb** OPAC systems (a|S|tec / OCLC BIBLIOTHECAplus) —
a port of the `Adis.java` adapter from
[opacapp/opacclient](https://github.com/opacapp/opacclient) (GPL-3.0) to Python.

> **Authorship:** this repository was written by an **AI agent** (Hermes Agent,
> by [Nous Research](https://nousresearch.com)) on behalf of its user, with
> human review of every change. It builds on prior art in two places:
>
> - [**opacapp/opacclient**](https://github.com/opacapp/opacclient) — the
>   Android OPAC client whose `Adis.java` adapter this project ports to Python.
>   The session/state handling, search flow and detail parsing follow its
>   design (GPL-3.0).
> - [**noestreich/voebbar**](https://github.com/noestreich/voebbar) — a Swift
>   macOS menu-bar + iOS app for VÖBB account operations. Its login flow
>   (OIDC via `oidcp/logincheck` with the `Referer: oidcp/authorize` header,
>   bypassing the F5 WAF) and its `requestCount`/`scriptEnabled` POST
>   conventions were verified against and incorporated here.

aDISWeb-based library systems (VÖBB Berlin, München, Stuttgart, Zürich, and
the whole Baden-Württemberg BSZ consortium, …) expose **no public
SRU/DAIA/REST API**. The only way to query their catalogues programmatically
is to drive the stateful aDISWeb web frontend: session bootstrap, form POSTs,
HTML parsing. This library does exactly that — generically, across all
aDISWeb generations and layouts.

## Features

- **Session bootstrap** — auto-detects both aDISWeb generations:
  URL-embedded session tokens (`/aDISWeb/_<token>/app`, VÖBB) and
  cookie-session instances (`/aDISWeb/app` + JSESSIONID, Zürich/Stuttgart/…)
- **Search** — free-text search (`search_simple`) and advanced-form search (`search`),
  with pagination (`search_get_page`)
- **Result parsing** — both hit-list layouts: modern `ul.rList` (Berlin) and
  legacy `table.rTable_table`; ids from `data-ajax`, `sp=SAK…` or `htmlOnLink`
- **Detail view** — metadata table, cover, per-branch holdings/availability
  (status + return date), reservable flag
- **Account (cookie-session or OIDC login)** — account overview (validity,
  fees, loans, reservations), renewal, reservation placement
  (`get_account`, `prolong`, `reserve`, …)
- **Availability-by-query** — `get_availability_by_query()` searches and
  fetches every hit's holdings in a single session and filters copies by
  branch (e.g. "which One Piece volumes are available at ZLB tomorrow?")
- **Library-agnostic** — 46 aDISWeb library configs included, all verified
  working (see [COMPATIBILITY.md](COMPATIBILITY.md))

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

```python
from adisweb import AdisClient, load_library

client = AdisClient(load_library("Berlin"))

# search the catalogue
results = client.search_simple("Berlin", area="Bibliotheksbestand")
print(results.total_result_count)   # 1190992
for hit in results.results[:5]:
    print(hit.id, hit.type.name, hit.status.name, hit.innerhtml)

# page 2
page2 = client.search_get_page(2)

# detail view
detail = client.get_result_by_id(results.results[0].detail_url)
print(detail.title)
for copy in detail.copies:
    print(copy.branch, copy.location, copy.status, copy.return_date)

# availability of a query's hits, filtered by branch (single session)
avail = client.get_availability_by_query("One Piece 86", branch_filter="ZLB")
for record in avail:
    print(record["title"], [(c["branch"], c["status"]) for c in record["copies"]])
```

CLI scan over all configured libraries:

```bash
.venv/bin/python scripts/scan_libraries.py --json
```

## MCP server

The client ships as an MCP (Model Context Protocol) stdio server — usable
from any MCP client (Hermes, Claude Desktop, …):

```bash
.venv/bin/pip install -e ".[mcp]"
.venv/bin/python -m adisweb.mcp_server
```

Tools (12):

- `list_libraries` — all configured libraries
- `search(query, library="Berlin", area="Bibliotheksbestand")` — hit list as JSON
- `search_availability(query, branch_filter=None, library="Berlin", area="Bibliotheksbestand")` — hit list with per-copy availability (branch, location, signature, status, return date), optionally filtered by branch substring (e.g. "ZLB", "Else Ury", "Namik Kemal"). Runs search + all detail fetches in ONE session (aDISWeb form state is session-bound)
- `get_detail(record_id_or_url, library="Berlin")` — full record detail as JSON
- `get_availability(record_id_or_url, library="Berlin")` — per-copy availability
- `get_account(ausweis, password, library="Berlin")` — account overview: pending fees, card validity, loans, reservations
- `get_loans(ausweis, password, library="Berlin")` — currently borrowed items: title, author, media_type, return_date, prolongable
- `get_orders(ausweis, password, library="Berlin")` — pending orders: `{"orders": [...], "magazine_orders": [...]}` (Bestellwünsche via *SZW, Magazin-Bestellungen via *SZB, each with branch/title/order timestamp)
- `reserve(record_id_or_url, ausweis, password, pickup_branch=None, express=False, notify=True, confirm=False, max_fee=None)` — place an order / Vormerkung
  - `pickup_branch`: delivery branch as shown in the order form, e.g. `"Friedrichshain-Kreuzberg: Familienbibliothek Else Ury"`
  - `express`: check Expressbestellung (fast delivery, may incur transport fees)
  - `notify`: notify on availability (default True)
  - `confirm`: must be True to submit the cost-bearing final button ("kostenpflichtig bestellen / vormerken"); otherwise the quoted cost is returned and nothing is ordered
  - `max_fee`: refuse the order when the quoted cost exceeds this amount (even with confirm=True). Cost detection covers both live phrasings: "Gebühren in Höhe von 2.00 Euro" (order fee) and "Transport kostet bei Bereitstellung 1.00 Euro" (magazine transport)
- `prolong(media_key, ausweis, password)` — renew a single loan (key from get_loans/get_account)
- `prolong_all(ausweis, password)` — renew all prolongable loans
- `cancel_reservation(media_key, ausweis, password)` — cancel a reservation

Each tool call creates a fresh client session (stateless, safe for concurrent
calls). Account/order tools need the credentials of the patron.

> **⚠️ Teststatus:** Die kompletten Konto-/Bestell-Funktionen (get_account,
> get_loans, get_orders, reserve, prolong, cancel_reservation) sind **nur
> für die VÖBB (Berlin) live getestet** — alle anderen Bibliotheken sind
> nur für Suche/Detail/Verfügbarkeit verifiziert. Handshake + tools verified
> via `scripts/mcp_handshake_test.py`.
>
> **🤝 Mitwirken:** Wir freuen uns über **Pull Requests und Verifikationen
> der Konto-/Bestell-Funktionen für andere Bibliotheken**! Wenn du eine
> aDISWeb-Bibliothek nutzt (z.B. Stuttgart, München, Zürich, Herne, …) und
> die Account-Funktionen dort testest, reiche gerne einen PR ein — mit
> Config-Update (falls nötig), Testergebnis und ggf. Code-Anpassungen für
> abweichende Layouts. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

Register in Hermes:

```bash
hermes mcp add adisweb --command /abs/path/to/.venv/bin/python --args -m adisweb.mcp_server
```

### MCP example workflow

A full order cycle over the MCP tools (verified live on VÖBB):

1. **Search** a title: `search(query="One Piece 86")` → hits with `id`
   (e.g. `AK34063780`)
2. **Check availability** per branch: `search_availability(query="One
   Piece 86", branch_filter="Else Ury")` → copies with branch/location/
   signature/status/return date
3. **Place an order** (costs shown first, nothing ordered without
   `confirm=True`):
   `reserve(record_id_or_url="AK34063780", ausweis=…, password=…,
   pickup_branch="Friedrichshain-Kreuzberg: Familienbibliothek Else Ury",
   express=True, confirm=False)` → returns the quoted fee (e.g.
   "Kostenpflichtige Bestellung (2.00 EUR)"); re-run with `confirm=True`
   (+ optional `max_fee=5.0`) to actually order
4. **Verify** in the account: `get_orders(ausweis=…, password=…)` →
   `{"orders": [...], "magazine_orders": [...]}`; `get_loans(…)` for
   borrowed items; `get_account(…)` for fees/validity

## Library configs

Each library is a JSON file under `libraries/`:

```json
{
  "name": "Berlin",
  "baseurl": "https://www.voebb.de/aDISWeb/app",
  "startparams": "service=direct/0/Home/$DirectLink&sp=SPROD00",
  "encoding": "UTF-8"
}
```

Configs were imported from
[opacapp/opacapp-config-files](https://github.com/opacapp/opacapp-config-files)
(MIT) and updated with current endpoints discovered via web search
(BSZ symbolic `sp=SOPACxx` names, itk-rheinland, …). Add your own library by
dropping a JSON file into `libraries/`.

## Library compatibility

All **46** bundled library configs were live-verified against the real OPACs
(see [COMPATIBILITY.md](COMPATIBILITY.md) and `libraries-scan.json` for the
full report):

**BSZ consortium (Baden-Württemberg, ~24):** Aalen_HS, Esslingen_HS,
Freiburg_UB, Furtwangen_HS, Heidelberg_PH, Heilbronn_HS, Karlsruhe_BLB,
Karlsruhe_Muho, Konstanz_HTWG, Loerrach_DHBW, Ludwigsburg_PH,
Mannheim_Duale_Hochschule, Mannheim_HS, Mannheim_Muho, Mosbach_DHBW,
Nuertingen_HfWU, Offenburg_HS, Pforzheim_HS, Ravensburg_DHBW,
Reutlingen_Hochschulbibliothek, Schwaebisch_Gmuend_Paedagogische_Hochschule,
Stuttgart, Stuttgart_Duale_Hochschule, Stuttgart_HdM, Stuttgart_HfT,
Stuttgart_Muho, Stuttgart_Rathaus, Stuttgart_Uni, Stuttgart_WLB,
Trossingen_Muho, Tuebingen_Uni, Ulm_Uni, Weingarten_HS

**itk-rheinland:** Dormagen, Dortmund, Duesseldorf, Grevenbroich, Meerbusch,
Neuss

**Other:** Berlin (VÖBB), Herne, Muenchen, Nuernberg,
Nuremberg_Bibliothek_des_Germanischen_Nationalmuseums, Regensburg, Zuerich

**Feature coverage:**

- **Search / detail / availability** — verified on all 46 libraries.
- **Account (login, loans, orders, reservations, renewal) und Bestellungen
  (Express/Magazin/Ausgabeort)** — **nur für die VÖBB (Berlin) live
  getestet und verifiziert**; für alle anderen Bibliotheken sind diese
  Funktionen **nicht getestet** (die aDISWeb-Layouts können abweichen).
  Andere Bibliotheken nutzen Cookie-Session oder klassischen Login.

## Tests

```bash
# offline tests (recorded VÖBB fixtures)
.venv/bin/python -m pytest tests/ -q

# live scan of all 46 libraries (opt-in, hits the real OPACs)
ADISWEB_LIVE=1 .venv/bin/python -m pytest tests/test_live_scan.py -v
```

## OpenSpec

Capability specs and the change proposal live in [`openspec/`](openspec/).

## License

GPL-3.0 (derived from opacapp/opacclient). Library configs under `libraries/`
are MIT (from opacapp/opacapp-config-files).
