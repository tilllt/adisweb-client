"""Patron-account features: login, account overview (fees, lending,
reservations), reserve, prolong, cancel.

Port of the account methods from opacapp/opacclient's Adis.java
(lines ~810-1975). Credentials are passed per call (not stored).
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup

from .exceptions import NotReachableError, OpacError
from .libraries import LibraryConfig
from .models import DetailedItem, MediaType

if TYPE_CHECKING:
    from .client import AdisClient

_DATE_FMT = "%d.%m.%Y"


class Account:
    """Patron credentials for one library."""

    def __init__(self, name: str, password: str, id: str = ""):
        self.name = name  # Ausweisnummer / Benutzernummer
        self.password = password
        self.id = id or name


class LentItem:
    """A borrowed item."""

    def __init__(self, title: str = "", author: str = "", media_type=None,
                 return_date=None, prolongable: bool = True):
        self.title = title
        self.author = author
        self.media_type = media_type or MediaType.UNKNOWN
        self.return_date = return_date
        self.prolongable = prolongable

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "media_type": self.media_type.name,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "prolongable": self.prolongable,
        }


class ReservedItem:
    """An active reservation."""

    def __init__(self, title: str = "", branch: str = "", expiry: _dt.date | None = None,
                 media_type=None, media_id: str = ""):
        self.title = title
        self.branch = branch
        self.expiry = expiry
        self.media_type = media_type or MediaType.UNKNOWN
        self.media_id = media_id  # key for cancel()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "branch": self.branch,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "media_type": self.media_type.name,
            "media_id": self.media_id,
        }


class AccountData:
    """Full account overview."""

    def __init__(self, account_id: str = ""):
        self.account_id = account_id
        self.pending_fees = ""
        self.valid_until = ""
        self.lent: list[LentItem] = []
        self.reservations: list[ReservedItem] = []
        self.warning = ""

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "pending_fees": self.pending_fees,
            "valid_until": self.valid_until,
            "lent": [l.to_dict() for l in self.lent],
            "reservations": [r.to_dict() for r in self.reservations],
            "warning": self.warning,
        }


class AccountResult:
    """Result of a mutating account action (reserve/prolong/cancel)."""

    def __init__(self, ok: bool, message: str = "", details: list | None = None):
        self.ok = ok
        self.message = message
        self.details = details or []

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "details": self.details}


# ---------------------------------------------------------------- helpers


def _parse_date(text: str) -> _dt.date | None:
    m = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group(0), _DATE_FMT).date()
    except ValueError:
        return None


def _media_type_from_title(title: str) -> MediaType:
    return MediaType.from_title(title)


def _all_form_inputs(doc: BeautifulSoup, include_submit_values: tuple[str, ...] = (),
                     skip_checkbox: bool = True) -> list[tuple[str, str]]:
    """Serialize form inputs like the Java loop (non-image, non-submit unless
    value matches include_submit_values, non-empty name). Submit buttons are
    matched by substring (e.g. "Bestellen/Vormerken" matches "Vormerken")."""
    out: list[tuple[str, str]] = []
    for el in doc.select("input, select"):
        etype = el.get("type", "")
        name = el.get("name", "")
        value = el.get("value", "")
        if etype == "image" or name == "":
            continue
        if etype == "submit":
            if not any(v and v in str(value) for v in include_submit_values):
                continue
        if etype == "checkbox" and skip_checkbox:
            continue
        out.append((name, str(value)))
    return out


# ---------------------------------------------------------------- client mixin


class AccountMixin:
    """Account methods for AdisClient (mixed into the client class)."""

    if TYPE_CHECKING:
        _account_form_oldstyle: bool
        _account_form_body: list[tuple[str, str]] | None
        _cookie_session: bool
        _session_sid: str
        _last_doc: BeautifulSoup | None
        _start_doc: BeautifulSoup | None
        library: "LibraryConfig"
        timeout: float
        s_service: str | None
        s_exts: list[str] | None
        s_pageform: list[tuple[str, str]]
        s_reusedoc: BeautifulSoup | None
        _session: "requests.Session"

        def _opac_url(self) -> str: ...
        def _netloc(self) -> str: ...
        def _parse(self, html: str) -> BeautifulSoup: ...
        def _sp_params(self, override_second: str | None = None) -> str: ...
        def _form_payload(self, doc: BeautifulSoup) -> list[tuple[str, str]]: ...
        def html_get(self, url: str) -> BeautifulSoup: ...
        def html_post(self, url: str, data: list[tuple[str, str]],
                      referer: str | None = None) -> BeautifulSoup: ...
        def _start(self) -> None: ...
        def get_result_by_id(self, id: str) -> "DetailedItem": ...

    def _account_overview_doc(self) -> BeautifulSoup:
        """Load the authenticated account overview from the cookie session.

        The browser session cookie `_sid` carries the aDISWeb session token;
        the overview lives at /aDISWeb/_<sid>/app/prod00/1.
        """
        sid = ""
        for c in self._session.cookies:
            if c.name == "_sid":
                sid = c.value
                break
        if not sid:
            raise OpacError("Keine _sid-Session-Cookie gefunden — bitte im Browser einloggen "
                            "und Cookies exportieren")
        doc = self.html_get(f"https://{self._netloc}/aDISWeb/_{sid}/app/prod00/1")
        self._last_doc = doc
        return doc

    # -- login --------------------------------------------------------------

    def login(self, account: Account) -> BeautifulSoup:
        """Log in and return the account overview document.

        Modern VÖBB uses OIDC, but the whole flow works without a browser
        (verified against voebbar/noestreich, Swift): the account POST with
        selected=*SBK triggers the OIDC authorize server-side; the subsequent
        logincheck POST returns the overview directly (no manual callback).
        """
        if self._cookie_session:
            return self._account_overview_doc()

        # 1. start page (prod00 like voebbar) -> session token from form action
        doc = self.html_get(f"{self.library.baseurl}/prod00?sp=SPROD00")
        self._last_doc = doc
        sid = self._sid_from_doc(doc)
        if not sid:
            raise OpacError("Session-ID nicht gefunden")
        app_url = f"https://{self._netloc}/aDISWeb/_{sid}/app"

        # 2. POST navigation to the account section -> triggers OIDC authorize
        nav = self._form_payload(doc)
        nav = self._set_form(nav, {
            "scriptEnabled": "true",
            "overrideScrollPos": "0",
            "selected": "ZTEXT       *SBK",
            "$Select": "Überall suchen",
        })
        self.html_post(app_url, nav)

        # 3. POST credentials to logincheck (referer = authorize, like voebbar)
        login_data = [
            ("L#AUSW", account.name),
            ("LPASSW", account.password),
            ("LLOGIN", "Login"),
        ]
        after = self._post_with_referer(
            "https://www.voebb.de/oidcp/logincheck", login_data,
            referer="https://www.voebb.de/oidcp/authorize")
        doc = self._parse(after)

        text = doc.get_text()
        if "schiefgegangen" in text or "ausgeschalteten Cookies" in text:
            raise OpacError("Login fehlgeschlagen: Cookie-Problem")
        if "Ungültig" in text or "ungültig" in text or "nicht korrekt" in text:
            raise OpacError("Login fehlgeschlagen: Ausweisnummer oder Passwort falsch")

        # 4. extract the NEW session id from the overview HTML
        new_sid = self._sid_from_doc(doc)
        if not new_sid:
            raise OpacError("Session nach Login nicht gefunden")
        self._session_sid = new_sid
        # sync requestCount from the overview's form state (post-login session)
        rc = doc.select_one('input[name="requestCount"]')
        if rc is not None:
            try:
                self.s_request_count = int(str(rc.get("value", "-1")))
            except ValueError:
                self.s_request_count = -1
        self._last_doc = doc
        return doc

    def _sid_from_doc(self, doc: BeautifulSoup) -> str:
        """Return the session token WITHOUT leading underscore ('' if absent)."""
        for pattern in (r"/aDISWeb/(_[a-z0-9]+)/app", r"/(_[a-z0-9]+)/timeout"):
            m = re.search(pattern, str(doc))
            if m:
                return m.group(1).lstrip("_")
        return ""

    def _set_form(self, form: list[tuple[str, str]], overrides: dict) -> list[tuple[str, str]]:
        """Apply overrides to a form payload (replace matching keys)."""
        keys = set(overrides)
        out = [(n, overrides[n] if n in keys else v) for n, v in form]
        for k, v in overrides.items():
            if k not in dict(form):
                out.append((k, v))
        return out

    def _post_with_referer(self, url: str, data: list[tuple[str, str]],
                           referer: str) -> str:
        """POST and return the raw HTML (no requestCount enrichment)."""
        try:
            resp = self._session.post(
                url, data=data, timeout=self.timeout,
                headers={"Referer": referer,
                         "Content-Type": "application/x-www-form-urlencoded"})
            resp.raise_for_status()
        except requests.RequestException as e:
            raise NotReachableError(f"POST failed: {url}: {e}") from e
        self._session._last_response = resp  # type: ignore[attr-defined]
        return resp.text

    def _handle_login_form(self, doc: BeautifulSoup, account: Account) -> BeautifulSoup:
        if doc.select_one("#LPASSW_1") is None:
            return doc  # already logged in / no form

        pwd = doc.select_one("#LPASSW_1")
        assert pwd is not None
        pwd["value"] = account.password

        # set the Ausweisnummer on the matching login input
        for el in doc.select("input"):
            el_id = str(el.get("id", ""))
            el_fld = str(el.get("fld", ""))
            if el_id in ("L#AUSW_1", "IDENT_1", "LMATNR_1") or el_fld == "L#AUSW_1":
                el["value"] = account.name
                break

        form = _all_form_inputs(doc)
        send = doc.select_one(
            'input[type=submit][value=Anmelden], '
            'input[type=submit][value="Anmeldung abschicken"]'
        )
        if send is None:
            send = doc.select_one("input[type=submit]")
        if send is not None:
            form.append((str(send.get("name", "")), str(send.get("value", ""))))

        doc = self.html_post(self._opac_url(), form)

        msg_el = doc.select_one(".message h1, .alert, .msgpage h1")
        if msg_el is not None:
            msg = msg_el.get_text().strip()
            if "Sie sind angemeldet" not in msg and "jetzt angemeldet" not in msg:
                raise OpacError(f"Login fehlgeschlagen: {msg}")
        if doc.select_one("input.errstate") is not None:
            raise OpacError("Login fehlgeschlagen: falsche Zugangsdaten")
        return doc

    # -- account overview ----------------------------------------------------

    def get_account(self, account: Account) -> AccountData:
        """Full account overview: fees, card validity, borrowed, reservations.

        With a browser-cookie session (VÖBB OIDC is WAF-protected), the
        session is already authenticated — the overview page is loaded
        directly from the session URL.
        """
        if self._cookie_session:
            doc = self._account_overview_doc()
        else:
            self._start()
            doc = self.login(account)
        # VÖBB splits title/author differently (no split marker)
        split_title_author = "VOEBB" not in str(doc.head) if doc.head else True

        data = AccountData(account.id or account.name)

        # modern VÖBB layout: <dl> with dt.adis-term / dd.adis-value
        for dt, dd in zip(doc.select("dt.adis-term"), doc.select("dd.adis-value")):
            label = dt.get_text().strip()
            value = dd.get_text().strip()
            if re.search(r".*Ausweis g.+ltig bis.*", label):
                data.valid_until = value
            if re.search(r".*Kontostand.*", label):
                # Kontostand vom: Datum: … Uhrzeit: … — the actual fee amount
                # lives in the "Gebührenkonto" section
                data.pending_fees = value
        # legacy layout: .aDISListe rows
        for tr in doc.select(".aDISListe tr"):
            cells = tr.find_all(recursive=False)
            if len(cells) < 2:
                continue
            label = cells[0].get_text().strip()
            value = cells[1].get_text().strip()
            if re.search(r".*F.+llige Geb.+hren.*", label):
                data.pending_fees = value
            if re.search(r".*Ausweis g.+ltig bis.*", label):
                data.valid_until = value

        # borrowed items: area link "N Ausleihen" → click → list
        area_links = self._account_area_links(doc)
        overview_form = self._form_payload(doc)
        if area_links.get("lent"):
            adoc = self._open_account_area(area_links["lent"], "lent", overview_form)
            data.lent = self._parse_lent_list(adoc, split_title_author)
            # the area page carries the SZA sub-link; if not found, try again
            if not data.lent:
                alink = self._account_links(adoc, "SZA")
                if alink is not None:
                    adoc = self.html_get(alink)
                    data.lent = self._parse_lent_list(adoc, split_title_author)
        else:
            # legacy: sp=SZA link directly on the overview
            alink = self._account_links(doc, "SZA")
            if alink is not None:
                adoc = self.html_get(alink)
                data.lent = self._parse_lent_list(adoc, split_title_author)

        # reservations: area links for reservations
        if area_links.get("reservations"):
            rdoc = self._open_account_area(area_links["reservations"], "reservations", overview_form)
            try:
                data.reservations = self._parse_reservation_list(rdoc, split_title_author)
            except Exception:  # noqa: BLE001
                data.warning = "Beim Abrufen der Reservationen ist ein Problem aufgetreten"
        else:
            rlinks: list[tuple[str, str]] = []
            for tr in doc.select(".rTable_div tr"):
                a = tr.select_one("a")
                if a is None:
                    continue
                text = tr.get_text()
                if any(k in text for k in ("Reservationen", "Vormerkung", "Fernleihbestellung",
                                           "Bereitstellung", "Bestellw", "Magazin")):
                    first = tr.find_all(recursive=False)
                    if first and first[0].get_text().strip() != "":
                        rlinks.append((a.get_text(), str(a.get("href", ""))))
            for _, rlink in rlinks:
                rdoc = self.html_get(rlink)
                try:
                    data.reservations.extend(self._parse_reservation_list(rdoc, split_title_author))
                except Exception:  # noqa: BLE001
                    data.warning = "Beim Abrufen der Reservationen ist ein Problem aufgetreten"

        # fees: open the Gebührenkonto area and parse the fee summary
        if area_links.get("fees"):
            try:
                fdoc = self._open_account_area(area_links["fees"], "fees", overview_form)
                fee_text = fdoc.get_text()
                m = re.search(r"F.llige Geb.hren\s*([\d.,]+\s*(?:EUR|€|Euro)?)", fee_text)
                if m and m.group(1).strip():
                    data.pending_fees = m.group(1).strip()
                else:
                    m2 = re.search(r"F.llige Geb.hren\s*([^\n]{0,40})", fee_text)
                    if m2 and "0,00" not in m2.group(1):
                        data.pending_fees = m2.group(1).strip()
            except Exception:  # noqa: BLE001
                pass

        return data

    def get_loans(self, account: Account) -> list[dict]:
        """Return the patron's currently borrowed items as a list of dicts
        (title, author, return_date, prolongable). Cheap variant of
        get_account() that skips fees/reservations parsing."""
        data = self.get_account(account)
        return [l.to_dict() for l in data.lent]

    def get_orders(self, account: Account) -> dict:
        """Return the patron's pending orders (Bestellwünsche, Magazin-
        Bestellungen) as parsed dicts.

        Verifies the account overview first, then opens the order areas via
        the selected=ZTEXT *SZW / *SZB POST targets (modern VÖBB).
        """
        if not self._cookie_session and not self._session_sid:
            self.login(account)
        doc = self._last_doc or self._start_doc
        assert doc is not None
        result: dict = {"orders": [], "magazine_orders": []}

        def _parse_table(adoc: BeautifulSoup) -> list[dict]:
            rows = []
            for tr in adoc.select(".rTable_div tbody tr, table.rTable_table tbody tr"):
                tds = tr.find_all(recursive=False)
                if len(tds) < 3:
                    continue
                texts = [td.get_text(" ", strip=True) for td in tds]
                # column layout (VÖBB): 0=Markieren checkbox, 1=Zeile(n)
                # je nach Bereich: Ausgabeort/Titel/Hinweis — skip "Markieren"
                if texts[0].strip() == "Markieren":
                    texts = texts[1:]
                rows.append({
                    "branch": texts[0],
                    "title": texts[1] if len(texts) > 1 else "",
                    "note": texts[2] if len(texts) > 2 else "",
                })
            return rows

        # area POSTs: each request rotates identity/requestCount AND the
        # order-area pages don't accept a different selected= code. Mirror
        # the browser: reload the overview before each area click.
        current = doc
        for area, key in (("orders", "orders"), ("magazine_orders", "magazine_orders")):
            # reload the overview fresh (new identity/requestCount) unless
            # this is the first area and we already sit on the overview
            if current is not doc:
                current = self._reload_overview()
            code = self._AREA_SELECTED[area]
            form = [(n, v) for n, v in self._form_payload(current)]
            form = [(n, code if n == "selected" else v) for n, v in form]
            try:
                adoc = self.html_post(self._opac_url(), form)
            except OpacError:
                continue
            current = adoc
            result[key] = _parse_table(adoc)
        return result

    def _reload_overview(self) -> BeautifulSoup:
        """Reload the account overview (fresh identity/requestCount) for
        post-login (OIDC) sessions; falls back to the cookie-session path."""
        if self._session_sid:
            doc = self.html_get(f"https://{self._netloc}/aDISWeb/_{self._session_sid}/app/prod00/1")
        else:
            doc = self._account_overview_doc()
        self._last_doc = doc
        return doc

    def _account_area_links(self, doc: BeautifulSoup) -> dict[str, str]:
        """Map account area names to their JS-button elements (modern VÖBB)."""
        areas: dict[str, str] = {}
        for a in doc.select("a[href]"):
            text = a.get_text().strip()
            if re.search(r"\d+\s*Ausleihen?", text):
                areas["lent"] = str(a.get("id", ""))
            elif re.search(r"(Vormerkung|Reservation)", text):
                areas["reservations"] = str(a.get("id", ""))
            elif re.search(r"Geb.hrenkonto", text):
                areas["fees"] = str(a.get("id", ""))
        return areas

    # area POST targets: modern VÖBB uses selected=ZTEXT *<CODE>
    _AREA_SELECTED = {
        "lent": "ZTEXT       *SZA",
        "reservations": "ZTEXT       *SZM",
        "fees": "ZTEXT       *SGG",
        "orders": "ZTEXT       *SZW",        # Bestellwünsche
        "magazine_orders": "ZTEXT       *SZB",  # Bestellungen (Magazin)
    }

    def _open_account_area(self, element_id: str, area_name: str | None = None,
                           overview_form: list[tuple[str, str]] | None = None) -> BeautifulSoup:
        """Open an account area by submitting the form with the area's
        selected= code (modern VÖBB, verified: "10 Ausleihen" → *SZA).

        The POST always uses the form state of the MOST RECENT page
        (identity/requestCount rotate per page; reusing an older overview
        form makes the server reject the request). ``overview_form`` is
        accepted for call compatibility but not used.
        """
        assert self._last_doc is not None
        # resolve the area name from the element id if not given
        if area_name is None:
            for name, aid in self._account_area_links(self._last_doc).items():
                if aid == element_id:
                    area_name = name
                    break
        code = self._AREA_SELECTED.get(area_name or "")
        if code is None:
            # fallback: try data-fld button like the old layout
            btn = self._last_doc.select_one(f'input[data-fld="{element_id}"]')
            if btn is None:
                raise OpacError(f"Account-Bereich '{element_id}' nicht gefunden")
            form = self._form_payload(self._last_doc)
            form.append((str(btn.get("name", "")), str(btn.get("value", ""))))
            doc = self.html_post(self._opac_url(), form)
            self._last_doc = doc
            return doc
        form = [(n, v) for n, v in self._form_payload(self._last_doc)]
        form = [(n, code if n == "selected" else v) for n, v in form]
        doc = self.html_post(self._opac_url(), form)
        self._last_doc = doc
        return doc

    def _parse_lent_list(self, doc: BeautifulSoup, split_title_author: bool) -> list[LentItem]:
        items: list[LentItem] = []
        for tr in doc.select(".rTable_div tbody tr"):
            cells = tr.find_all(recursive=False)
            if len(cells) < 5:
                continue
            item = LentItem()
            title_html = str(cells[3])
            title_text = re.sub(r"(?i)<br[^>]*>", ";", title_html)
            # strip tags
            title_text = re.sub(r"<[^>]+>", "", title_text)
            parts = [p.strip() for p in title_text.split(";")]
            if parts and parts[0].startswith("[") and parts[0].endswith("]"):
                item.media_type = _media_type_from_title(parts[0][1:-1])
                parts = parts[1:]
            if split_title_author and parts:
                m = re.split(r"[:/] ", parts[0], maxsplit=1)
                item.title = m[0].strip()
                if len(m) > 1:
                    item.author = m[1].strip()
            elif parts:
                item.title = parts[0]
            item.return_date = _parse_date(cells[1].get_text())
            status = cells[4].get_text() if len(cells) > 4 else ""
            item.prolongable = not re.search(r".*nicht verl.+ngerbar.*", status)
            items.append(item)
        return items

    def _parse_reservation_list(self, doc: BeautifulSoup, split_title_author: bool) -> list[ReservedItem]:
        items: list[ReservedItem] = []
        colmap = {"title": 2, "branch": 1, "expirationdate": 0}
        thead = doc.select_one(".rTable_div thead")
        if thead is not None:
            for i, th in enumerate(thead.select("tr th")):
                text = th.get_text()
                if "Bis" in text:
                    colmap["expirationdate"] = i
                if "Ausgabeort" in text:
                    colmap["branch"] = i
                if "Titel" in text:
                    colmap["title"] = i
        for tr in doc.select(".rTable_div tbody tr"):
            cells = tr.find_all(recursive=False)
            if len(cells) < len(colmap):
                continue
            item = ReservedItem()
            title_html = str(cells[colmap["title"]])
            title_text = re.sub(r"(?i)<br[^>]*>", ";", title_html)
            title_text = re.sub(r"<[^>]+>", "", title_text)
            parts = [p.strip() for p in title_text.split(";")]
            if parts and parts[0].startswith("[") and parts[0].endswith("]"):
                item.media_type = _media_type_from_title(parts[0][1:-1])
                parts = parts[1:]
            item.title = parts[0] if parts else ""
            item.branch = cells[colmap["branch"]].get_text().strip() \
                if colmap["branch"] < len(cells) else ""
            item.expiry = _parse_date(cells[colmap["expirationdate"]].get_text()) \
                if colmap["expirationdate"] < len(cells) else None
            items.append(item)
        return items

    # -- reserve ---------------------------------------------------------------

    def reserve(self, record_id_or_url: str, account: Account,
                pickup_branch: str | None = None,
                express: bool = False,
                notify: bool = True,
                confirm: bool = False,
                max_fee: float | None = None) -> AccountResult:
        """Place a reservation / order (modern VÖBB flow, verified live).

        Flow (mirrors the browser exactly):
          login → search by record id → detail (selected=ZTEXT AK<id>) →
          press "Bestellen/Vormerken" ($Button$1) → order page: choose
          pickup branch ($Select) + Expressbestellung ($Checkbox) +
          notification ($Select$0) → "Weiter" → confirmation page shows the
          cost ("Bei Bereitstellung entstehen Ihnen Gebühren …"/"Transport
          kostet …") → final submit via "kostenpflichtig bestellen /
          vormerken" ($Button).

        Args:
            record_id_or_url: detail URL or record id (AK…/SAK…/plain).
            pickup_branch: branch name shown in the order form's $Select
                (e.g. "Friedrichshain-Kreuzberg: Familienbibliothek Else
                Ury"); None keeps the default.
            express: check "Expressbestellung" (may incur transport fees).
            notify: "Benachrichtigung bei Bereitstellung" (Ja/Nein).
            confirm: must be True to submit the cost-bearing final button;
                otherwise the cost warning is returned without ordering.
            max_fee: if set, the order is refused when the quoted cost
                exceeds this amount (even with confirm=True).
        """
        # login first (modern OIDC flow; no-op for cookie sessions).
        # NOTE: do NOT call _start() here — it bootstraps a separate
        # session and the subsequent login would create a second one
        # (VÖBB rejects that: "Bitte schließen Sie diesen Reiter").
        if not self._cookie_session and not self._session_sid:
            self.login(account)

        rid = self._record_id(record_id_or_url)

        # detail page: search by the bare id (yields a result list whose form
        # state opens the detail view; the overview page's state does not)
        base_doc = self._last_doc or self._start_doc
        assert base_doc is not None
        nv = _all_form_inputs(base_doc)
        for i, (n, v) in enumerate(nv):
            if n == "$Autosuggest":
                nv[i] = (n, rid)
            if n == "$Select":
                nv[i] = (n, "Bibliotheksbestand")
        nv.append(("$Button", "Suchen"))
        treffer = self.html_post(self._opac_url(), nv)
        self._last_doc = treffer
        if treffer.select_one('a[href*="sp=SAK"]') is None:
            return AccountResult(False, f"Titel '{rid}' nicht gefunden")

        detail_doc = self._open_detail(rid)
        self._last_doc = detail_doc

        # press "Bestellen/Vormerken"
        btn = detail_doc.select_one('input[name="$Button$1"], input[value*="Bestellen/Vormerken"]')
        if btn is None:
            return AccountResult(False, "Kein Bestellen/Vormerken-Button auf der Detailseite gefunden")
        order_doc = self._browser_post(detail_doc, extra={"$Button$1": "Bestellen/Vormerken"})
        self._last_doc = order_doc
        body = order_doc.get_text(" ", strip=True)
        if "Bestellvorgang" not in body and "Bestellung" not in body:
            return AccountResult(False, "Bestellseite nicht erreicht",
                                 details=[body[:200]])

        # order page: pickup branch + express + notification → Weiter
        sel = order_doc.select_one('select[name="$Select"]')
        branch_val = None
        if sel is not None:
            opts = [o for o in sel.select("option") if o.get_text().strip()]
            if pickup_branch:
                for o in opts:
                    if pickup_branch.lower() in o.get_text().lower():
                        branch_val = str(o.get("value", ""))
                        break
                if branch_val is None:
                    return AccountResult(
                        False, f"Ausgabeort '{pickup_branch}' nicht im Formular",
                        details=[o.get_text().strip() for o in opts[:10]])
            elif opts:
                branch_val = str(opts[0].get("value", ""))
        extra: dict[str, str] = {"$Button": "Weiter"}
        if branch_val is not None:
            extra["$Select"] = branch_val
        extra["$Checkbox"] = "on" if express else ""
        extra["$Checkbox$0"] = ""
        extra["$Select$0"] = "Ja" if notify else "Nein"
        confirm_doc = self._browser_post(order_doc, extra=extra)
        self._last_doc = confirm_doc
        body = confirm_doc.get_text(" ", strip=True)
        fee = self._parse_order_fee(body)
        if "Bestellinformation" not in body and not re.search(r"Geb.hren|Transport", body):
            return AccountResult(False, "Bestätigungsseite nicht erreicht",
                                 details=[body[:200]])

        # cost guard: refuse when the quoted fee exceeds max_fee
        if fee is not None and max_fee is not None and fee > max_fee:
            return AccountResult(
                False, f"Kosten {fee:.2f} EUR überschreiten max_fee={max_fee} — nicht bestellt",
                details=[body[:300]])

        # fee warning → require confirm before the cost-bearing submit
        cost_btn = confirm_doc.select_one(
            'input[value*="kostenpflichtig bestellen"]')
        if cost_btn is not None and not confirm:
            fee_txt = f"{fee:.2f} EUR" if fee is not None else "?"
            return AccountResult(
                False,
                f"Kostenpflichtige Bestellung ({fee_txt}) — mit confirm=True bestätigen",
                details=[body[:300]])

        final = self._browser_post(confirm_doc, extra={"$Button": "kostenpflichtig bestellen / vormerken"})
        self._last_doc = final
        fbody = final.get_text(" ", strip=True)
        for marker in ("Der Bestellwunsch ist erfolgt", "Die Magazinbestellung ist erfolgt",
                       "Der Bestellwunsch", "Die Magazinbestellung"):
            i = fbody.find(marker)
            if i >= 0:
                return AccountResult(True, fbody[i:i + 180])
        return AccountResult(False, "Bestellung nicht bestätigt",
                             details=[fbody[:300]])

    @staticmethod
    def _parse_order_fee(body: str) -> float | None:
        """Parse the quoted order cost from the confirmation page text.

        Handles both phrasings seen live: "Bei Bereitstellung entstehen
        Ihnen Gebühren in Höhe von 2.00 Euro" (express/order fee) and
        "Der Transport kostet bei Bereitstellung 1.00 Euro" (magazine
        transport). Returns EUR as float, or None if no cost is quoted.
        """
        m = re.search(r"(?:Geb.hren in H.he von|Transport kostet bei Bereitstellung|kostet bei Bereitstellung)\s*([\d.,]+)", body)
        if not m:
            return None
        raw = m.group(1).replace(".", "").replace(",", ".") \
            if m.group(1).count(",") == 1 and m.group(1).count(".") <= 1 else m.group(1).replace(",", ".")
        try:
            return float(raw.replace(" ", ""))
        except ValueError:
            return None

    def _browser_post(self, base_doc: BeautifulSoup,
                      selected_val: str | None = None,
                      extra: dict[str, str] | None = None) -> BeautifulSoup:
        """POST like the browser: hidden inputs of the current page plus
        scriptEnabled/overrideScrollPos/$Autosuggest/$Select/$Tab and the
        page's requestCount (identity/requestCount rotate per page)."""
        data: dict[str, str] = {}
        for inp in base_doc.select('input[type="hidden"]'):
            n = str(inp.get("name") or "")
            if n:
                data[n] = str(inp.get("value") or "")
        data["scriptEnabled"] = "true"
        data["overrideScrollPos"] = "0"
        auto = base_doc.select_one('input[name="$Autosuggest"]')
        data["$Autosuggest"] = str(auto.get("value") or "") if auto else ""
        sel = base_doc.select_one('select[name="$Select"]')
        data["$Select"] = str(sel.get("value") or "Überall suchen") if sel else "Überall suchen"
        data["$Tab"] = "0"
        rc = base_doc.select_one('input[name="requestCount"]')
        data["requestCount"] = str(rc.get("value") or "0") if rc else "0"
        if selected_val:
            data["selected"] = selected_val
        if extra:
            data.update(extra)
        doc = self.html_post(self._opac_url(), [(k, v) for k, v in data.items()],
                             referer=self._opac_url())
        self._last_doc = doc
        return doc

    def _record_id(self, record_id_or_url: str) -> str:
        """Extract the bare AK id from a URL or id (strip AK/SAK prefixes)."""
        m = re.search(r"sp=SAK(\d+)", record_id_or_url)
        if m:
            return m.group(1)
        rid = record_id_or_url
        for prefix in ("AK", "SAK"):
            if rid.startswith(prefix):
                rid = rid[len(prefix):]
                break
        return rid

    def _open_detail(self, rid: str) -> BeautifulSoup:
        """Open the detail view for a record id via selected=ZTEXT AK<id>."""
        base = self._last_doc or self._start_doc
        assert base is not None, "keine Seiten-Basis für Detail-Aufruf"
        data: dict[str, str] = {}
        for inp in base.select('input[type="hidden"]'):
            n = str(inp.get("name") or "")
            if n:
                data[n] = str(inp.get("value") or "")
        data["scriptEnabled"] = "true"
        data["overrideScrollPos"] = "0"
        auto = base.select_one('input[name="$Autosuggest"]')
        data["$Autosuggest"] = str(auto.get("value") or "") if auto else ""
        sel = base.select_one('select[name="$Select"]')
        data["$Select"] = str(sel.get("value") or "Überall suchen") if sel else "Überall suchen"
        data["$Tab"] = "0"
        rc = base.select_one('input[name="requestCount"]')
        data["requestCount"] = str(rc.get("value") or "0") if rc else "0"
        data["selected"] = f"ZTEXT       AK{rid}"
        doc = self.html_post(self._opac_url(), [(k, v) for k, v in data.items()],
                             referer=self._opac_url())
        self._last_doc = doc
        return doc

    def _detail_url(self, record_id_or_url: str) -> str:
        """Resolve a record id or URL to a fetchable detail URL (session-scoped)."""
        if record_id_or_url.startswith("http"):
            # re-scope the URL to the current session (the search-result URL
            # carries no session token → the server treats it as a 2nd tab)
            url = record_id_or_url
            sid = self._session_sid or self._sid_from_cookie()
            if sid and "/aDISWeb/app/" in url:
                # re-scope the generic app path to the current session
                url = url.replace("/aDISWeb/app/", f"/aDISWeb/_{sid}/app/", 1)
            return url
        # legacy page!id or plain id → search for the SAK link
        return f"{self._opac_url()}/prod00?sp=SPROD00&sp=SAK{record_id_or_url}"

    def _sid_from_cookie(self) -> str:
        for c in self._session.cookies:
            if c.name == "_sid":
                return str(c.value)
        return ""

    # -- prolong ----------------------------------------------------------------

    def _account_links(self, doc: BeautifulSoup, sp: str) -> str | None:
        for tr in doc.select(".rTable_div tr"):
            a = tr.select_one("a")
            if a is not None and f"sp={sp}" in str(a.get("href", "")):
                return str(a.get("href", ""))
        return None

    def prolong(self, media_key: str, account: Account) -> AccountResult:
        """Renew one borrowed item. media_key: "inputname" from get_account's
        lent list (first segment of the key)."""
        self._start()
        doc = self.login(account)
        alink = self._account_links(doc, "SZA")
        if alink is None:
            return AccountResult(False, "Keine Ausleihen gefunden")
        adoc = self.html_get(alink)

        form = _all_form_inputs(adoc)
        # find checkbox for this media and check prolongability
        for tr in adoc.select(".rTable_div tr"):
            inp = tr.select_one("input")
            if inp is not None and str(inp.get("name", "")) == media_key:
                disabled = inp.has_attr("disabled")
                cells = tr.find_all(recursive=False)
                if len(cells) > 4:
                    disabled = disabled or re.search(
                        r".*nicht verl.+ngerbar.*", cells[4].get_text())
                if disabled:
                    return AccountResult(False, "Titel nicht verlängerbar")
        form.append((media_key, "on"))
        btn_name = ""
        btn = adoc.select_one('input[value="Markierte Titel verlängern"]')
        if btn is not None:
            btn_name = str(btn.get("name", ""))
        form.append((btn_name or "textButton$1", "Markierte Titel verlängern"))
        doc = self.html_post(self._opac_url(), form)

        # back to account
        back = _all_form_inputs(doc)
        back.append(("$Toolbar_0.x", "1"))
        back.append(("$Toolbar_0.y", "1"))
        self.html_post(self._opac_url(), back)
        return AccountResult(True, "Verlängerung abgeschickt")

    def prolong_all(self, account: Account) -> AccountResult:
        """Renew all prolongable borrowed items."""
        self._start()
        doc = self.login(account)
        alink = self._account_links(doc, "SZA")
        if alink is None:
            return AccountResult(False, "Keine Ausleihen gefunden")
        adoc = self.html_get(alink)

        form: list[tuple[str, str]] = []
        for el in adoc.select("input"):
            etype = el.get("type", "")
            name = el.get("name", "")
            if etype == "image" or name == "":
                continue
            if etype == "checkbox":
                if not el.has_attr("disabled"):
                    form.append((str(name), "on"))
            elif etype != "submit":
                form.append((str(name), str(el.get("value", ""))))
        btn = adoc.select_one('input[value="Markierte Titel verlängern"]')
        btn_name = str(btn.get("name", "")) if btn else ""
        form.append((btn_name or "textButton$1", "Markierte Titel verlängern"))
        doc = self.html_post(self._opac_url(), form)

        lines = []
        for tr in doc.select(".rTable_div tbody tr"):
            cells = tr.find_all(recursive=False)
            if len(cells) >= 5:
                lines.append({
                    "title": re.sub(r"<[^>]+>", "", str(cells[3])).strip()[:60],
                    "new_return_date": cells[1].get_text().strip(),
                    "message": cells[4].get_text().strip(),
                })
        back = _all_form_inputs(doc)
        back.append(("$Toolbar_0.x", "1"))
        back.append(("$Toolbar_0.y", "1"))
        self.html_post(self._opac_url(), back)
        return AccountResult(True, "Verlängerungen abgeschickt", details=lines)

    # -- cancel reservation ------------------------------------------------------

    def cancel(self, media_key: str, account: Account) -> AccountResult:
        """Cancel an active reservation. media_key: "inputname|url" as returned
        by get_account reservations (media_id field)."""
        parts = media_key.split("|")
        if len(parts) < 2:
            return AccountResult(False, "Ungültiger media_key (inputname|url erwartet)")
        checkbox_name = parts[0]
        rlink = parts[1].replace("requestCount=", "fooo=")

        self._start()
        doc = self.login(account)
        # find the reservation list link matching the media url
        sp = "SZM"
        if "sp=" in rlink.upper():
            m = re.search(r"sp=([A-Z0-9]+)", rlink, re.I)
            if m:
                sp = m.group(1).upper()
        target = None
        for tr in doc.select(".rTable_div tr"):
            a = tr.select_one("a")
            if a is None:
                continue
            text = tr.get_text()
            href = str(a.get("href", "")).upper()
            if any(k in text for k in ("Reservationen", "Vormerkung", "Bestellung")):
                first = tr.find_all(recursive=False)
                if first and first[0].get_text().strip() != "" and f"SP={sp}" in href:
                    target = str(a.get("href", ""))
                    break
        if target is None:
            return AccountResult(False, "Vormerkungsliste nicht gefunden")

        rdoc = self.html_get(target)
        form = _all_form_inputs(rdoc)
        form.append((checkbox_name, "on"))
        btn = rdoc.select_one('input[value="Markierte Titel löschen"]')
        btn_name = str(btn.get("name", "")) if btn else ""
        form.append((btn_name or "textButton$0", "Markierte Titel löschen"))
        doc = self.html_post(self._opac_url(), form)

        back = _all_form_inputs(doc)
        back.append(("$Toolbar_0.x", "1"))
        back.append(("$Toolbar_0.y", "1"))
        self.html_post(self._opac_url(), back)
        return AccountResult(True, "Vormerkung gelöscht")
