#!/usr/bin/env python3
"""Find new OPAC endpoints for dead aDIS libraries via Brave Search API.

For each dead library, queries Brave for its current catalogue URL, then
probes the top candidates with a HEAD/GET and reports whether the target
looks like aDISWeb (aDISWeb/app), another OPAC, or is unreachable.

Usage:
    .venv/bin/python scripts/find_new_endpoints.py [--limit N]
"""

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

BRAVE_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
if not BRAVE_KEY and (REPO.parent / ".env").exists():
    for line in (REPO.parent / ".env").read_text().splitlines():
        if line.startswith("BRAVE_SEARCH_API_KEY="):
            BRAVE_KEY = line.split("=", 1)[1].strip()

# (library name, search query)
DEAD = [
    ("Aalen_HS", "Hochschule Aalen Bibliothek OPAC Katalog"),
    ("Freiburg_UB", "Universitätsbibliothek Freiburg Katalog OPAC"),
    ("Furtwangen_HS", "Hochschule Furtwangen Bibliothek Katalog OPAC"),
    ("Heidelberg_PH", "Pädagogische Hochschule Heidelberg Bibliothek OPAC"),
    ("Heilbronn_HS", "Hochschule Heilbronn Bibliothek Katalog OPAC"),
    ("Konstanz_HTWG", "HTWG Konstanz Bibliothek OPAC Katalog"),
    ("Ludwigsburg_PH", "Pädagogische Hochschule Ludwigsburg Bibliothek OPAC"),
    ("Mannheim_HS", "Hochschule Mannheim Bibliothek Katalog OPAC"),
    ("Mannheim_Muho", "Musikhochschule Mannheim Bibliothek OPAC"),
    ("Offenburg_HS", "Hochschule Offenburg Bibliothek Katalog OPAC"),
    ("Pforzheim_HS", "Hochschule Pforzheim Bibliothek OPAC Katalog"),
    ("Reutlingen_Hochschulbibliothek", "Hochschule Reutlingen Bibliothek OPAC"),
    ("Schwaebisch_Gmuend_Paedagogische_Hochschule", "PH Schwäbisch Gmünd Bibliothek OPAC"),
    ("Stuttgart_HdM", "Hochschule der Medien Stuttgart Bibliothek OPAC"),
    ("Stuttgart_HfT", "Hochschule für Technik Stuttgart Bibliothek OPAC"),
    ("Stuttgart_Muho", "Musikhochschule Stuttgart Bibliothek OPAC"),
    ("Stuttgart_WLB", "Württembergische Landesbibliothek Stuttgart Katalog OPAC"),
    ("Trossingen_Muho", "Musikhochschule Trossingen Bibliothek OPAC"),
    ("Tuebingen_Uni", "Universitätsbibliothek Tübingen Katalog OPAC"),
    ("Ulm_Uni", "Universitätsbibliothek Ulm Katalog OPAC"),
    ("Weingarten_HS", "PH Weingarten Bibliothek OPAC Katalog"),
    ("Dormagen", "Stadtbibliothek Dormagen OPAC Katalog"),
    ("Meerbusch", "Stadtbibliothek Meerbusch OPAC Katalog"),
    ("Neuss", "Stadtbibliothek Neuss OPAC Katalog"),
    ("Dortmund", "Stadt- und Landesbibliothek Dortmund Katalog OPAC"),
    ("Mannheim_Duale_Hochschule", "DHBW Mannheim Bibliothek OPAC Katalog"),
    ("Mosbach_DHBW", "DHBW Mosbach Bibliothek OPAC Katalog"),
    ("Nuertingen_HfWU", "HfWU Nürtingen-Geislingen Bibliothek OPAC"),
    ("Ravensburg_DHBW", "DHBW Ravensburg Bibliothek OPAC Katalog"),
    ("Herne", "Stadtbibliothek Herne OPAC Katalog"),
    ("Loerrach_DHBW", "DHBW Lörrach Bibliothek OPAC Katalog"),
    ("Nuremberg_Bibliothek_des_Germanischen_Nationalmuseums", "Germanisches Nationalmuseum Bibliothek OPAC Katalog"),
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def brave_search(q: str, count: int = 5) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": q, "count": count}
    )
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": BRAVE_KEY,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get("web", {}).get("results", [])


def probe(url: str) -> tuple[int, str]:
    """Return (status, kind) where kind ∈ aDISWeb / other / error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.getcode()
            body = resp.read(40000).decode("utf-8", errors="replace")
            final = resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "error"
    except Exception as e:  # noqa: BLE001
        return 0, f"error: {type(e).__name__}"
    if "aDISWeb" in body or "/aDISWeb/" in final:
        return status, "aDISWeb"
    if "<title>" in body.lower() or "opac" in body.lower() or "katalog" in body.lower():
        return status, "other-opac"
    return status, "unknown"


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    entries = DEAD[: args.limit] if args.limit else DEAD

    if not BRAVE_KEY:
        print("BRAVE_SEARCH_API_KEY fehlt (in /opt/data/.env erwartet)")
        return 1

    results = []
    for i, (name, query) in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] {name}: '{query}'")
        try:
            hits = brave_search(query)
        except Exception as e:  # noqa: BLE001
            print(f"    SEARCH-FEHLER: {e}")
            results.append({"library": name, "search": query, "error": str(e)})
            continue
        candidates = []
        for h in hits[:5]:
            url = h.get("url", "")
            status, kind = probe(url)
            candidates.append({"url": url, "title": h.get("title", "")[:80],
                               "status": status, "kind": kind})
            print(f"    {status} {kind:10} {url[:90]}")
        results.append({"library": name, "search": query, "candidates": candidates})
        time.sleep(1.1)  # Brave free tier: 1 req/s

    (REPO / "endpoint-hunt.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nReport: endpoint-hunt.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
