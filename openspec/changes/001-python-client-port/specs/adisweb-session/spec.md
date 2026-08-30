# aDISWeb Session

## ADDED Requirements

### Requirement: Session bootstrap (`_start`)

- **Eingaben:** library config (baseurl, startparams).
- **Ablauf:** GET start URL; detect session mechanism — legacy `;jsessionid=` in nav links (Adis.java model) or current-gen session token in `<form action="/aDISWeb/_<token>/app">`; discover `service` + `sp` params; capture page form via `updatePageform`.
- **Ausgaben:** session state (`s_app_path`/`s_sid`, `s_pageform`) or `OpacError` on message page.
- **Ergebnis:** subsequent requests POST/GET to the session base URL.

#### Scenario: VÖBB (Berlin) start page
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** baseurl `https://www.voebb.de/aDISWeb/app`, startparams with `sp=SPROD00`.
- **Ergebnis:** `s_app_path` = `/aDISWeb/_<token>/app`, page form holds `identity` + `$Autosuggest` + `$Select` fields.

#### Scenario: Cookie-session instance (Zürich)
- **Akteure:** client, PBZ Zürich OPAC.
- **Eingaben:** baseurl `https://katalog.pbz.ch/aDISWeb/app`, startparams `sp=SOPAC`.
- **Ergebnis:** no URL token; plain form action `/aDISWeb/app` used as `s_app_path`; JSESSIONID cookie drives the session.

### Requirement: Page form capture (`updatePageform`)

- **Ablauf:** collect every `input`/`select` whose name is non-empty, type is not image/submit/checkbox, and value is non-empty.
- **Ausgaben:** list of name/value pairs (`s_pageform`) used as base payload for subsequent POSTs.

#### Scenario: Trefferliste page
- **Akteure:** client.
- **Eingaben:** result list document.
- **Ergebnis:** page form contains `requestCount` and toolbar state so pagination POSTs work.
