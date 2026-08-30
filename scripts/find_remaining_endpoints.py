#!/usr/bin/env python3
"""Find endpoints for the remaining 7 dead libraries via Brave Search."""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

KEY = ""
for line in (Path("/opt/data/.env")).read_text().splitlines():
    if line.startswith("BRAVE_SEARCH_API_KEY="):
        KEY = line.split("=", 1)[1].strip()

REMAINING = [
    ("Dormagen", "Stadtbibliothek Dormagen OPAC Katalog"),
    ("Meerbusch", "Stadtbibliothek Meerbusch OPAC Katalog"),
    ("Neuss", "Stadtbibliothek Neuss OPAC Katalog"),
    ("Dortmund", "Stadt- und Landesbibliothek Dortmund Katalog"),
    ("Herne", "Stadtbibliothek Herne OPAC Katalog"),
    ("Nuremberg_Bibliothek_des_Germanischen_Nationalmuseums", "Germanisches Nationalmuseum Nürnberg Bibliothek Katalog"),
    ("Tuebingen_Uni", "Universitätsbibliothek Tübingen Katalog OPAC"),
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"


def brave(q: str, count: int = 8) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": q, "count": count})
    req = urllib.request.Request(url, headers={"X-Subscription-Token": KEY, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("web", {}).get("results", [])


def probe(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.getcode(), r.read(80000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, f"ERR {type(e).__name__}"


def extract_symbolic_sp(html_or_url: str) -> list[str]:
    found = set()
    for m in re.finditer(r"sp=([A-Z0-9_]+)", html_or_url):
        v = m.group(1)
        if not re.match(r"^S\d+\.\d+\.\d+\.\d+", v):
            found.add(v)
    return sorted(found)


def main() -> int:
    out = []
    for i, (name, query) in enumerate(REMAINING, 1):
        print(f"[{i}/{len(REMAINING)}] {name}")
        found = {}
        for q in (f'"{query}"', f"{query} aDISWeb", f"{query} Online-Katalog"):
            try:
                hits = brave(q)
            except Exception as e:  # noqa: BLE001
                print(f"    search err: {e}")
                continue
            for h in hits[:8]:
                url = h.get("url", "")
                if "aDISWeb" in url:
                    for sp in extract_symbolic_sp(url):
                        found.setdefault(sp, url)
            if found:
                break
            time.sleep(1.1)
        # if nothing: fetch library homepage, look for aDISWeb links
        if not found:
            try:
                hits = brave(f"{query} Bibliothek")
                for h in hits[:4]:
                    url = h.get("url", "")
                    status, body = probe(url)
                    if status == 200:
                        for sp in extract_symbolic_sp(body):
                            m = re.search(r"https?://[^\"'<> ]*aDISWeb[^\"'<> ]*", body)
                            if m:
                                found.setdefault(sp, m.group(0).replace("&amp;", "&"))
            except Exception as e:  # noqa: BLE001
                print(f"    probe err: {e}")
        print(f"    -> {found if found else 'nichts'}")
        out.append({"library": name, "found": found})
    (REPO / "remaining-endpoints.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
