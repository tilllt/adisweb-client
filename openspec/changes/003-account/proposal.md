# Change 003: Account features (login, fees, lending, reservations)

**Status:** In Progress
**Datum:** 2026-08-30

## Why

The MCP server currently exposes only catalogue features (search, detail,
availability). The aDIS adapter in opacapp/opacclient supports the full
patron-account flow — login, fees ("Kostenabfrage"), borrowed items,
reservations, prolongation, reservation and cancellation. Without it the
server cannot answer "what do I owe", "what is due when", or place
reservations. This change ports the account methods of `Adis.java`
(lines 810–1975) to Python and exposes them as MCP tools.

## What Changes

New client methods on `AdisClient` (mirroring `Adis.java`):

- `login(account)` — POST the login form (Benutzernummer + Passwort),
  detect VÖBB-specific layout, handle login errors.
- `get_account(account)` — account overview: pending fees ("Fällige
  Gebühren"), card validity ("Ausweis gültig bis"), borrowed items
  (with due dates, prolongable flag), reservations.
- `reserve(record_id_or_url, account)` — place a reservation on a record
  (uses `reservation()` flow: detail → reservation form → confirm).
- `prolong(media_id, account)` / `prolong_all(account)` — renew borrowed
  items (single or all).
- `cancel(media_id, account)` — cancel a reservation.

New MCP tools (same names, JSON out):

- `login(ausweis, password)` — validate credentials, return session state
- `get_account(ausweis, password)` — fees, validity, borrowed, reservations
- `reserve(record_id_or_url, ausweis, password)`
- `prolong(media_id, ausweis, password)`
- `prolong_all(ausweis, password)`
- `cancel_reservation(reservation_id, ausweis, password)`

Behavioral delta: before, an agent could only search and inspect; after, it
can manage the patron account end-to-end (pay nothing — fees are read-only
here; Vormerkungen und Verlängerungen werden ausgelöst).

### Specs-Delta

- **ADDED** `account` (specs/account/spec.md)

## ADDED Requirements

### account

#### ADDED Requirements (specs/account/spec.md)
- **Req 1: Login** — POST login form with Ausweisnummer/Passwort; error on wrong credentials; session state reused for subsequent account calls.
- **Req 2: Account overview (`get_account`)** — pending fees, card validity, borrowed items with due dates + prolongable flag, active reservations.
- **Req 3: Reserve** — place a reservation on a catalogue record.
- **Req 4: Prolong** — renew a single item or all borrowed items.
- **Req 5: Cancel reservation** — cancel an active reservation.

## Changes (behavioral delta vs. current state)

Current state: MCP tools `list_libraries`, `search`, `get_detail`,
`get_availability` only.

After this change, additionally:

- `get_account(ausweis, password)` returns fees/validity/borrowed/reservations as JSON.
- `reserve(record_id_or_url, ausweis, password)` places a reservation and returns the result.
- `prolong(...)`/`prolong_all(...)` renew items.
- `cancel_reservation(...)` cancels.
- Wrong credentials → tool error, never a raw HTML page.

## Downgrade

Remove the account methods + tools and the `account` spec; MCP server reverts
to catalogue-only (change 002 state).
