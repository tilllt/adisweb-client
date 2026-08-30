# adisweb-client

Python client for **aDISWeb** OPAC systems (a|S|tec / OCLC BIBLIOTHECAplus) — a port of the `Adis.java` adapter from [opacapp/opacclient](https://github.com/opacapp/opacclient) (GPL-3.0) to Python.

## Purpose

aDISWeb-based library systems (VÖBB Berlin, München, Stuttgart, Tübingen, Zürich, …) expose **no public SRU/DAIA/REST API**. Verified for the VÖBB: no `availableChannel` WebAPI entries in lobid-organisations for DE-609/DE-609-E/DE-109; OCLC RESTv1 endpoints return 404. The only way to query such catalogues programmatically is to drive the stateful aDISWeb web frontend the same way the opacclient does: session bootstrap, form POSTs, HTML parsing.

This repo ports that proven interaction to a generic, reusable Python client library — usable from scripts, CLIs, cron jobs, and later wrapped by an MCP server.

## Capability index

- `adisweb-session` — aDISWeb session bootstrap: `jsessionid`, `service`, `sp` params, page form state
- `catalogue-search` — keyword search (free/advanced form), result list parsing (modern `.rList` variant + legacy `rTable` variant), pagination
- `catalogue-detail` — single-record detail view: metadata table, cover, holdings/availability table

## External systems

- Any aDISWeb OPAC, e.g. VÖBB: `https://www.voebb.de/aDISWeb/app` (stateful, POST forms, `jsessionid` in URL)
- Reference implementation: `opacapp/opacclient` `Adis.java` (GPL-3.0, archived Dec 2024)

## Conventions

- Ported logic keeps the original method names/semantics where possible (`_start`, `parse_search`, `parseResult`, `updatePageform`, `searchGetPage`) so the Java source stays a reference.
- Parsing uses BeautifulSoup (CSS selectors mirror jsoup selectors 1:1).
- Sessions are not shared; each client instance owns its own `requests.Session`.
- All public output types are plain dataclasses (no ORM, no framework).
- Library-specific parameters (baseurl, start params, layout) come from JSON configs under `libraries/` — the core is library-agnostic.
