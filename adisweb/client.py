"""aDISWeb OPAC client — Python port of opacapp/opacclient's Adis.java.

Ports the proven aDISWeb web-frontend interaction (session bootstrap, form
POSTs, HTML parsing) to a generic, library-agnostic Python client.

Reference: https://github.com/opacapp/opacclient (GPL-3.0, Adis.java)
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .account import AccountMixin
from .exceptions import NoResultsError, NotReachableError, OpacError, SearchError
from .libraries import LibraryConfig
from .models import (
    Copy,
    Detail,
    DetailedItem,
    MediaType,
    SearchRequestResult,
    SearchResult,
    Status,
)

_SID_RE = re.compile(r".*;jsessionid=([0-9A-Fa-f]+)[^0-9A-Fa-f].*")
_ID_RE = re.compile(r"javascript:.*htmlOnLink\('([0-9A-Za-z]+)'\)")
_REQUEST_COUNT_RE = re.compile(r"requestCount=([0-9]+)")
_TOTAL_COUNT_RE = re.compile(r".*Treffer: .* von ([0-9]+)[^0-9]*")
_TOTAL_COUNT_RE2 = re.compile(r"Treffer:\s*([\d.]+)")
# current-generation aDISWeb embeds the session token in the form action:
#   <form action="/aDISWeb/_<token>/app" ...>
_FORM_ACTION_RE = re.compile(r"^(/aDISWeb/_[^/]+/app)$")


def _attr(el, name: str, default: str = "") -> str:
    """Read a tag attribute, always returning a plain str."""
    v = el.get(name)
    if v is None:
        return default
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return str(v)

# search field keys, mirroring the aDISWeb advanced-search form
_FREE_SEARCH = "FELD01_1"


class AdisClient(AccountMixin):
    """Stateful client for one aDISWeb library (one instance = one session)."""

    @classmethod
    def from_config(cls, cfg: dict, timeout: float = 30.0) -> "AdisClient":
        """Build a client from a raw config dict (name/baseurl/startparams)."""
        return cls(LibraryConfig(**cfg), timeout=timeout)

    @classmethod
    def with_session_cookies(cls, library: LibraryConfig, cookies: list[dict],
                             timeout: float = 30.0) -> "AdisClient":
        """Build a client that authenticates via exported browser session
        cookies (VÖBB OIDC callback is WAF-protected against non-browser
        clients; the aDISWeb API itself accepts browser session cookies).

        cookies: list of {name, value, domain, path, secure, httpOnly}.
        """
        client = cls(library, timeout=timeout)
        client._cookie_session = True
        for c in cookies:
            client._session.cookies.set(
                c["name"], c["value"],
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                secure=c.get("secure", False),
            )
        return client

    @classmethod
    def from_cookie_file(cls, library: LibraryConfig, path: str,
                         timeout: float = 30.0) -> "AdisClient":
        import json

        from pathlib import Path

        cookies = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.with_session_cookies(library, cookies, timeout=timeout)

    def __init__(self, library: LibraryConfig, timeout: float = 30.0):
        self.library = library
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": library.user_agent,
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }
        )

        # session state (same names as Adis.java for traceability)
        self.s_sid: str | None = None
        self.s_app_path: str | None = None  # form action path (with or without token)
        self._origin: str = ""  # scheme+netloc of the final start page (after redirects)
        self.s_service: str | None = None
        self.s_exts: list[str] | None = None
        self.s_pageform: list[tuple[str, str]] = []
        self.s_request_count: int = -1
        self.s_last_page: int = 1
        self.s_next_button = "$Toolbar_5"
        self.s_previous_button = "$Toolbar_4"
        self.s_reusedoc: BeautifulSoup | None = None
        self._advanced_search_form_body: list[tuple[str, str]] | None = None
        self._account_form_oldstyle: bool = False
        self._account_form_body: list[tuple[str, str]] | None = None
        self._cookie_session: bool = False
        self._last_doc: BeautifulSoup | None = None
        self._session_sid: str = ""

    # ------------------------------------------------------------------ HTTP

    def _request_count_query(self, url: str) -> str:
        if "requestCount" not in url and self.s_request_count >= 0:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}requestCount={self.s_request_count}"
        return url

    def _session_origin(self) -> str:
        """Effective URL of the most recent HTTP response (follows redirects)."""
        resp = getattr(self._session, "_last_response", None)
        if resp is not None:
            return resp.url
        return self.library.start_url()

    def _fetch(self, url: str) -> str:
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise NotReachableError(f"GET failed: {url}: {e}") from e
        self._session._last_response = resp  # type: ignore[attr-defined]
        return resp.text

    def _post(self, url: str, data: list[tuple[str, str]], referer: str | None = None) -> str:
        try:
            headers = {"Referer": referer} if referer else {}
            resp = self._session.post(url, data=data, timeout=self.timeout, headers=headers)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise NotReachableError(f"POST failed: {url}: {e}") from e
        self._session._last_response = resp  # type: ignore[attr-defined]
        return resp.text

    def _parse(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def html_get(self, url: str) -> BeautifulSoup:
        """GET + parse; keeps requestCount in sync with the OPAC."""
        doc = self._parse(self._fetch(self._request_count_query(url)))
        self._update_request_count(doc)
        self.s_reusedoc = doc  # latest page is the form-state base for next POST
        return doc

    def html_post(self, url: str, data: list[tuple[str, str]],
                  referer: str | None = None) -> BeautifulSoup:
        data = list(data)
        if not any(n == "requestCount" for n, _ in data):
            data.append(("requestCount", str(self.s_request_count)))
        doc = self._parse(self._post(url, data, referer=referer))
        self._update_request_count(doc)
        self.s_reusedoc = doc  # latest page is the form-state base for next POST
        return doc

    def _update_request_count(self, doc: BeautifulSoup) -> None:
        for a in doc.select("a[href]"):
            m = _REQUEST_COUNT_RE.search(_attr(a, "href"))
            if m:
                self.s_request_count = int(m.group(1))

    def _opac_url(self) -> str:
        """Base URL for stateful requests: post-login session, form-action
        path (with or without session token), or classic ;jsessionid= form."""
        if self._session_sid:
            return f"https://{self._netloc}/aDISWeb/_{self._session_sid}/app"
        if self.s_app_path is not None:
            origin = self._origin or f"https://{self._netloc}"
            return f"{origin}{self.s_app_path}"
        if self._cookie_session:
            # browser-cookie session: the _sid cookie carries the session token
            sid = ""
            for c in self._session.cookies:
                if c.name == "_sid":
                    sid = c.value
                    break
            if sid:
                return f"https://{self._netloc}/aDISWeb/_{sid}/app"
        return f"{self.library.baseurl};jsessionid={self.s_sid}"

    @property
    def _netloc(self) -> str:
        from urllib.parse import urlparse

        return urlparse(self.library.baseurl).netloc

    # ---------------------------------------------------------------- session

    def _start(self) -> None:
        """Bootstrap the aDISWeb session (port of Adis.java _start, extended
        for current-generation aDISWeb where the session token lives in the
        form action instead of ;jsessionid= navigation links)."""
        self.s_request_count = -1
        self.s_exts = None
        self.s_service = None
        self.s_reusedoc = None
        doc = self.html_get(self.library.start_url())
        self._start_doc = doc
        # remember the origin of the FINAL page (after redirects) — some
        # aDISWeb instances live on a different host than the configured base
        from urllib.parse import urlparse

        final = urlparse(self._session_origin())
        self._origin = f"{final.scheme}://{final.netloc}"

        msg = doc.select_one(".msgpage")
        if msg:
            raise OpacError(msg.get_text(strip=True))

        # session token in <form action="/aDISWeb/_<token>/app"> (current gen)
        # or plain form action "/aDISWeb/app" (cookie-session gen, e.g. Zürich)
        form_action = doc.select_one("form[action]")
        if form_action is not None:
            action = _attr(form_action, "action")
            m = _FORM_ACTION_RE.search(action)
            if m:
                self.s_app_path = m.group(1)
            elif action.startswith("/") and "/app" in action:
                self.s_app_path = action.split("?")[0]

        nav_sel = "#unav li a, #hnav li a, .tree_ul li a, a.search-adv"
        for nav in doc.select(nav_sel):
            href = _attr(nav, "href")
            if "service=" in href:
                self.s_service = _query_param(href, "service")
            if "Erweiterte Suche" in nav.get_text():
                self.s_exts = _query_params(href, "sp")
            m = _SID_RE.match(href)
            if m:
                self.s_sid = m.group(1)

        # Old OPACs use an <a> to the account form, newer ones a button
        self._account_form_oldstyle = any(
            "sp=SBK" in _attr(a, "href")
            for a in doc.select("#unav li a, #hnav li a, .tree_ul li a")
        )
        self.update_pageform(doc)

        # account form body (used by login when not oldstyle): page form +
        # the hidden "BK" script button
        if not self._account_form_oldstyle:
            self._account_form_body = list(self.s_pageform) + [
                ("$ScriptButton_hidden", "BK")
            ]
        else:
            self._account_form_body = None

        if (self.s_exts is None and doc.select_one("input.search-adv")
                and not doc.select_one('input[name="$Autosuggest"]')):
            # advanced search not in menu and no direct start-page form;
            # discover via account menu item (legacy layout, e.g. HfM Karlsruhe)
            for nav in doc.select("#unav li a, #hnav li a, .tree_ul li a"):
                if "Konto" in nav.get_text():
                    self.s_exts = _query_params(_attr(nav, "href"), "sp")
                    break
            inp = doc.select_one("input.search-adv")
            assert inp is not None
            body = list(self.s_pageform) + [
                (_attr(inp, "name"), _attr(inp, "value"))
            ]
            self._advanced_search_form_body = body
            self.s_pageform = []  # page form is consumed by the POST body

        if self.s_exts is None:
            self.s_exts = ["SS6"]

    def update_pageform(self, doc: BeautifulSoup) -> None:
        """Capture hidden form state (port of Adis.java updatePageform)."""
        form: list[tuple[str, str]] = []
        for el in doc.select("input, select"):
            etype = _attr(el, "type")
            name = _attr(el, "name")
            value = _attr(el, "value")
            if etype in ("image", "submit", "checkbox") or name == "":
                continue
            if value == "":
                continue
            form.append((name, value))
        self.s_pageform = form

    def _get_advanced_search_doc(self) -> BeautifulSoup:
        if self._advanced_search_form_body is not None:
            return self.html_post(self._opac_url(), self._advanced_search_form_body)
        return self.html_get(
            f"{self._opac_url()}?service={self.s_service}{self._sp_params()}"
        )

    def _sp_params(self, override_second: str | None = None) -> str:
        if override_second is not None and len(self.s_exts) == 1:
            return f"&sp={override_second}"
        parts = []
        for i, sp in enumerate(self.s_exts):
            if i == 1 and override_second is not None:
                parts.append(f"&sp={override_second}")
            else:
                parts.append(f"&sp={sp}")
        return "".join(parts)

    # ----------------------------------------------------------------- search

    def search_simple(self, query: str, area: str = "Bibliotheksbestand") -> SearchRequestResult:
        """Simple search via the start-page form (current-generation aDISWeb,
        e.g. VÖBB). ``area`` selects the search scope ($Select option text)."""
        self._start()
        doc = self._start_doc

        # set values IN the form DOM so the serialized payload carries them
        # exactly once (appending duplicates breaks the search: the server
        # uses the first, empty value)
        autosuggest = doc.select_one('input[name="$Autosuggest"]')
        if autosuggest is not None:
            autosuggest["value"] = query
        select = doc.select_one('select[name="$Select"]')
        if select is not None:
            select["value"] = area

        nvpairs = self._form_payload(doc)
        nvpairs.append(("$Button", "Suchen"))

        docresults = self.html_post(self._opac_url(), nvpairs)
        return self.parse_search_wrapped(docresults, 1)

    def search(self, queries: list[tuple[str, str]]) -> SearchRequestResult:
        """Execute a search. queries: list of (field_key, value) with
        field keys like ``FELD01_1`` (free text) or select ids."""
        self._start()
        doc = self._get_advanced_search_doc()

        dropdown_text_count = 0
        total_count = 0
        for key, value in queries:
            if value == "":
                continue
            total_count += 1
            sel = doc.select_one(f"select#{key}")
            if sel is not None:
                sel["value"] = value  # bs4 sets selected option by value attr
                continue
            inp = doc.select_one(f"input#{key}")
            if inp is not None:
                inp["value"] = value
                continue
            # generic field: SUCH01_x select + FELD01_x input pattern
            dropdown_text_count += 1
            if dropdown_text_count > 4:
                raise SearchError("max 4 search criteria supported")
            idx = dropdown_text_count
            idx_sel = doc.select_one(f"select#SUCH01_{idx}")
            idx_inp = doc.select_one(f"input#FELD01_{idx}, input[data-fld=FELD01_{idx}]")
            if idx_sel is not None:
                idx_sel["value"] = key
            if idx_inp is not None:
                idx_inp["value"] = value

        if total_count == 0:
            raise SearchError("no search criteria given")

        nvpairs = self._form_payload(doc)
        nvpairs.append(("$Toolbar_0.x", "1"))
        nvpairs.append(("$Toolbar_0.y", "1"))

        docresults = self.html_post(self._opac_url(), nvpairs)
        return self.parse_search_wrapped(docresults, 1)

    def _form_payload(self, doc: BeautifulSoup) -> list[tuple[str, str]]:
        """Serialize all non-image/submit inputs (port of the Java loop)."""
        nvpairs: list[tuple[str, str]] = []
        for el in doc.select("input, select"):
            etype = _attr(el, "type")
            name = _attr(el, "name")
            value = _attr(el, "value")
            if etype == "image" or etype == "submit" or name == "":
                continue
            nvpairs.append((name, value))
        return nvpairs

    def parse_search_wrapped(self, doc: BeautifulSoup, page: int) -> SearchRequestResult:
        try:
            return self.parse_search(doc, page)
        except _SingleResultFound:
            # Exactly one hit -> aDISWeb jumps straight to the detail view;
            # go back to the hit list (port of parse_search_wrapped).
            nvpairs = self._form_payload(doc)
            name = self._toolbar_name_trefferliste(doc)
            nvpairs.append((f"{name}.x", "1"))
            nvpairs.append((f"{name}.y", "1"))
            doc = self.html_post(self._opac_url(), nvpairs)
            return self.parse_search(doc, page)

    def parse_search(self, doc: BeautifulSoup, page: int) -> SearchRequestResult:
        """Parse the hit list (port of Adis.java parse_search)."""
        msg = doc.select_one(".message h1, .msgpage h1")
        if msg and not doc.select_one("#right #R06"):
            raise OpacError(msg.get_text(strip=True))
        if "#OPACLI" in str(doc) and "nicht gefunden" in (doc.get_text() or ""):
            raise NoResultsError("no results")

        total_result_count = -1
        r06 = doc.select_one("#R06")
        if r06:
            m = _TOTAL_COUNT_RE.match(r06.get_text().strip())
            if m:
                total_result_count = int(m.group(1))
            else:
                m2 = _TOTAL_COUNT_RE2.search(r06.get_text())
                if m2:
                    total_result_count = int(m2.group(1).replace(".", ""))
            if r06.get_text().strip().endswith("Treffer: 1"):
                total_result_count = 1

        r03 = doc.select_one("#R03")
        if r03 and r03.get_text().strip().endswith("Treffer: 1"):
            raise _SingleResultFound()

        results: list[SearchResult] = []
        if doc.select_one("table.rTable_table tbody"):
            sel_row = "table.rTable_table tbody tr"
            sel_link = ".rTable_td_text a"
            sel_text = ".rList_name"
            sel_img = ".rTable_td_img img, .rTable_td_text img"
            sel_num = "tr td:first-child"
        else:
            # modern layout, e.g. Berlin (aDISWeb Mosaik): <ul class="rList">
            # with <li class="rList_li rList_even|rList_odd">
            sel_row = "ul.rList li.rList_li"
            sel_link = ".rList_titel a"
            sel_text = ".rList_name, .rList_jahr"
            sel_img = ".rList_medium img, .rList_availability img, .rList_titel img"
            sel_num = ".rList_num"

        nr = 1
        for tr in doc.select(sel_row):
            res = SearchResult()
            inner = tr.select_one(sel_link)
            if inner is None:
                continue
            for img in inner.select("img"):
                img.decompose()
            descr = str(inner)
            for n in tr.select(sel_text):
                t = n.get_text().replace("\u00a0", " ").strip()
                if t:
                    descr += f"<br />{t.strip()}"
            res.innerhtml = descr

            try:
                res.nr = int(tr.select_one(sel_num).get_text().strip())
            except (ValueError, AttributeError):
                res.nr = nr

            link = tr.select_one(sel_link)
            href = _attr(link, "href")
            # current-gen: id in data-ajax attr or sp=SAK… href param
            data_ajax = _attr(tr, "data-ajax")
            if data_ajax:
                res.id = data_ajax
            elif "sp=SAK" in href:
                res.id = href.split("sp=SAK")[-1].split("&")[0]
            else:
                m = _ID_RE.match(href)
                if m:
                    res.id = f"{page}!{m.group(1)}"
            # keep the direct detail URL for current-gen records
            if "sp=SAK" in href or data_ajax:
                res.detail_url = href

            for img in tr.select(sel_img):
                ttext = _attr(img, "title")
                src = _attr(img, "src") or _attr(img, "href")
                if ttext in _MEDIA_TITLES or ttext.split("+")[0].strip() in _MEDIA_TITLES:
                    res.type = MediaType.from_title(ttext)
                elif re.search(r".*ist verf.+gbar", ttext) or "is available" in ttext or \
                        "ist ausleihbar" in ttext or "verfu_ja" in src or \
                        "availability-green" in src:
                    res.status = Status.GREEN
                elif re.search(r".*nicht verf.+gbar", ttext) or "not available" in ttext or \
                        "nicht ausleihbar" in ttext or "verfu_nein" in src or \
                        "availability-red" in src:
                    res.status = Status.RED

            cover_img = tr.select_one(".rList_cover img")
            if cover_img is not None:
                url = _attr(cover_img, "data-src")
                if url:
                    res.cover = url

            results.append(res)
            nr += 1

        self.update_pageform(doc)
        self.s_last_page = page

        next_btn = doc.select_one('input[title="nächster"], input[title="Vorwärts blättern"]')
        prev_btn = doc.select_one('input[title="nächster"], input[title="Rückwärts blättern"]')
        if next_btn is not None:
            self.s_next_button = _attr(next_btn, "name", self.s_next_button)
        if prev_btn is not None:
            self.s_previous_button = _attr(prev_btn, "name", self.s_previous_button)

        return SearchRequestResult(results, total_result_count, page)

    # ------------------------------------------------------------- pagination

    def search_get_page(self, page: int) -> SearchRequestResult:
        """Navigate to a result page (port of Adis.java searchGetPage)."""
        res: SearchRequestResult | None = None
        while page != self.s_last_page:
            nvpairs = [
                (n, v)
                for n, v in self.s_pageform
                if "$Toolbar_" not in n
            ]
            if page > self.s_last_page:
                nvpairs.append((f"{self.s_next_button}.x", "1"))
                nvpairs.append((f"{self.s_next_button}.y", "1"))
                p = self.s_last_page + 1
            else:
                nvpairs.append((f"{self.s_previous_button}.x", "1"))
                nvpairs.append((f"{self.s_previous_button}.y", "1"))
                p = self.s_last_page - 1
            doc = self.html_post(self._opac_url(), nvpairs)
            res = self.parse_search_wrapped(doc, p)
        assert res is not None
        return res

    # ------------------------------------------------------------------ detail

    def get_result_by_id(self, id: str) -> DetailedItem:
        """Fetch the detail view for a record id.

        current-generation aDISWeb (VÖBB): the record is opened by POSTing
        ``selected=ZTEXT AK<id>`` with the form state of the most recent page
        (identity/requestCount must stay in sync — reuse the last document).
        """
        if id.startswith("http"):
            return self.parse_result(id, self.html_get(id))

        base = self.s_reusedoc or self._start_doc
        nvpairs = self._detail_payload(base, id)
        doc = self.html_post(self._opac_url(), nvpairs, referer=self._opac_url())
        self.s_reusedoc = doc
        return self.parse_result(id, doc)

    def _detail_payload(self, base: BeautifulSoup, record_id: str) -> list[tuple[str, str]]:
        """Form payload that opens a record detail view (current-gen).

        Mirrors the browser click: hidden inputs of the current page plus
        scriptEnabled/overrideScrollPos/$Select/$Tab, requestCount from the
        current page, and selected=ZTEXT AK<id>.
        """
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
        # record ids from search hits may already carry the AK- or SAK-
        # prefix; the detail POST expects exactly one AK-prefixed key
        rid = record_id
        for prefix in ("AK", "SAK"):
            if rid.startswith(prefix):
                rid = rid[len(prefix):]
                break
        data["selected"] = f"ZTEXT       AK{rid}"
        return [(k, v) for k, v in data.items()]

    def get_availability_by_query(self, query: str, branch_filter: str | None = None,
                                  area: str = "Bibliotheksbestand") -> list[dict]:
        """Search ``query`` and return per-record copy availability.

        Runs search + detail fetches in ONE session (aDISWeb form state —
        identity/requestCount — is session-bound; separate sessions break it).
        ``branch_filter``: substring matched (case-insensitive) against the
        library/branch name; None returns all branches.
        """
        res = self.search_simple(query, area=area)
        out = []
        for r in res.results:
            try:
                detail = self.get_result_by_id(r.id)
            except OpacError:
                continue
            copies = []
            for c in detail.copies:
                if branch_filter and branch_filter.lower() not in c.branch.lower():
                    continue
                copies.append({
                    "branch": c.branch, "location": c.location,
                    "signature": c.signature, "status": c.status,
                    "return_date": c.return_date.isoformat() if c.return_date else None,
                })
            out.append({
                "id": r.id,
                "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.innerhtml)).strip(),
                "copies": copies,
            })
        return out

    def parse_result(self, id: str, doc: BeautifulSoup) -> DetailedItem:
        """Parse the detail view (port of Adis.java parseResult)."""
        res = DetailedItem()

        cover_img = doc.select_one("#R001 img")
        if cover_img is None:
            # current-gen aDISWeb: cover is a .img-delayed image, src may be
            # a placeholder until JS swaps data-src. Prefer the real cover
            # (vlb/cover or external URL) over the media-type icon.
            for cand in doc.select("img.img-delayed[data-src]"):
                cand_url = _attr(cand, "data-src")
                if "vlb/cover" in cand_url or cand_url.startswith("http"):
                    cover_img = cand
                    break
            else:
                cover_img = doc.select_one("img.img-delayed[data-src]")
        if cover_img is not None:
            url = _attr(cover_img, "data-src") or _attr(cover_img, "src")
            if url and not url.endswith("erne.gif") and "cover-bg" not in url:
                res.cover = url

        for tr in doc.select("#R06 .aDISListe table tbody tr"):
            children = tr.find_all(recursive=False)
            if len(children) < 2:
                continue
            title = children[0].get_text().strip()
            value = children[1].get_text().strip()
            link = children[1].select_one("a")
            if ("hier klicken" in value or value.startswith("zur ") or "URL" in title) \
                    and link is not None:
                res.details.append(Detail(title, value, _attr(link, "href")))
            else:
                res.details.append(Detail(title, value))
            if "Titel" in title and res.title == "":
                res.title = re.split(r"[:/;]", value, maxsplit=1)[0].strip()

        if res.title == "":
            for d in res.details:
                if "Gesamtwerk" in d.content or "Zeitschrift" in d.content:
                    res.title = d.title
                    break

        reservable = doc.select_one(
            "input[value*=Reservieren], input[value*=Vormerken], "
            "input[value*=Einzelbestellung]"
        )
        if reservable is not None and id is not None:
            res.reservable = True
            res.reservation_info = id

        table = doc.select_one("#R08 table.rTable_table, #R09 table.rTable_table")
        if table is not None:
            colmap: dict[int, str] = {}
            thead = table.select_one("thead")
            if thead is not None:
                for i, th in enumerate(thead.select("tr th")):
                    head = th.get_text().strip()
                    if "Bibliothek" in head or "Library" in head:
                        colmap[i] = "branch"
                    elif "Standort" in head or "Location" in head:
                        colmap[i] = "location"
                    elif "Signatur" in head or "Call number" in head:
                        colmap[i] = "signature"
                    elif "URL" in head:
                        colmap[i] = "url"
                    elif ("Status" in head or "Hinweis" in head or "Leihfrist" in head
                          or re.search(r".*Verf.+gbarkeit.*", head)):
                        colmap[i] = "status"
            for tr in table.select("tbody tr"):
                cells = tr.find_all(recursive=False)
                copy = Copy()
                for i, kind in colmap.items():
                    if i >= len(cells):
                        continue
                    text = cells[i].get_text().strip()
                    if kind == "status":
                        if " am: " in text:
                            copy.status = (copy.status + " - " if copy.status else "") + \
                                text.split("-")[0].strip()
                            try:
                                raw = text.split(": ", 1)[1].strip()
                                copy.return_date = _dt.datetime.strptime(
                                    raw, "%d.%m.%Y"
                                ).date() if "." in raw else None
                            except (ValueError, IndexError):
                                # tolerate 1.9.2026 (no zero padding)
                                m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
                                if m:
                                    try:
                                        copy.return_date = _dt.date(
                                            int(m.group(3)), int(m.group(2)), int(m.group(1))
                                        )
                                    except ValueError:
                                        pass
                        else:
                            copy.status = (copy.status + " - " if copy.status else "") + text
                    else:
                        setattr(copy, kind, text)
                res.copies.append(copy)

        zitierlink = doc.select_one("a:contains(Zitierlink)")
        if zitierlink is not None:
            res.id = zitier_attr(link, "href")
        return res

    # ---------------------------------------------------------------- helpers

    def _toolbar_name_trefferliste(self, doc: BeautifulSoup) -> str:
        el = doc.select_one("[id^=Toolbar_][title*=Trefferliste]")
        if el is not None:
            return _attr(el, "name", "$Toolbar_0")
        return "$Toolbar_0"

    def _toolbar_name_first_page(self, doc: BeautifulSoup) -> str:
        el = doc.select_one("[id^=Toolbar_][title*=Beginn], [id^=Toolbar_][title*=Anfang]")
        if el is not None:
            return _attr(el, "name")
        raise OpacError("internal error: first-page button not found")


class _SingleResultFound(Exception):
    """Internal: aDISWeb jumped straight to a single detail view."""


def _query_param(url: str, key: str) -> str | None:
    vals = _query_params(url, key)
    return vals[0] if vals else None


def _query_params(url: str, key: str) -> list[str]:
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(url).query, keep_blank_values=True)
    return qs.get(key, [])


# media-type titles recognized in image title attributes (subset)
_MEDIA_TITLES = {
    "Buch", "Band", "DVD-ROM", "CD-ROM", "Medienkombination", "DVD-Video",
    "DVD", "Noten", "Konsolenspiel", "Spielkonsole", "CD", "Zeitschrift",
    "Zeitschriftenheft", "Zeitung", "Beitrag E-Book", "Elektronische Ressource",
    "E-Book", "Karte", "E-Ressource", "Munzinger", "E-Audio", "Blu-Ray",
}
