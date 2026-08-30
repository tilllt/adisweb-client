# aDISWeb Session

## Purpose

Bootstrap and maintain the stateful aDISWeb session that every catalogue operation depends on. aDISWeb embeds the session id in the URL (`;jsessionid=...`) and keeps page state in hidden form fields; without a correctly initialized session, all catalogue requests fail (404/redirect/WAF).

## Requirements

### Req 1: Session bootstrap (`_start`)

- **Eingaben:** base URL (e.g. `https://www.voebb.de/aDISWeb/app`), start params from library config (e.g. `?service=direct/0/Home/$DirectLink&sp=...`).
- **Ablauf:** GET the start URL; extract `jsessionid` from navigation links (regex `;jsessionid=([0-9A-Fa-f]+)`); extract `service` and `sp` (advanced-search / account) parameters from nav links; capture the page form (all hidden inputs/selects with non-empty values) via `updatePageform`.
- **Ausgaben:** initialized session state (`s_sid`, `s_service`, `s_exts`, `s_pageform`) or a descriptive error if the start page contains a message page (`.msgpage`).
- **Ergebnis:** subsequent catalogue calls can be issued as POST/GET to `{opac_url};jsessionid={sid}`.

#### Scenario: VÖBB start page
- **Akteure:** client, VÖBB OPAC.
- **Eingaben:** `https://www.voebb.de/` start params.
- **Ergebnis:** session id captured, `s_exts` contains `SS6` (advanced search), page form holds `identity` + `$Autosuggest` + `$Select` fields.

### Req 2: Page form capture (`updatePageform`)

- **Eingaben:** parsed HTML document.
- **Ablauf:** collect every `input`/`select` whose name is non-empty, type is not image/submit/checkbox, and value is non-empty.
- **Ausgaben:** list of name/value pairs (`s_pageform`) used as base payload for subsequent POSTs.
- **Ergebnis:** POST payloads carry the full hidden state aDISWeb requires.

#### Scenario: Trefferliste page
- **Akteure:** client.
- **Eingaben:** result list document.
- **Ergebnis:** page form contains the `requestCount` and toolbar state so pagination POSTs work.
