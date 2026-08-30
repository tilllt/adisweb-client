# adisweb-client

Python client for **aDISWeb** OPAC systems (a|S|tec / OCLC BIBLIOTHECAplus) —
a port of the `Adis.java` adapter from [opacapp/opacclient](https://github.com/opacapp/opacclient)
(GPL-3.0) to Python.

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
```

CLI scan over all configured libraries:

```bash
.venv/bin/python scripts/scan_libraries.py --json
```

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
