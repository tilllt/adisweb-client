#!/usr/bin/env python3
"""Extract current aDISWeb endpoints (symbolic sp= names) for BSZ-hosted
libraries via Brave Search API.

The old opacapp configs used sp=S<host>:<port> (dead since BSZ migrated to
symbolic names). This script searches for each library's current aDISWeb URL
on bsz.ibs-bw.de and extracts the symbolic sp= parameter.

Usage:
    .venv/bin/python scripts/bsz_symbolic_names.py [--limit N]
Writes: bsz-endpoints.json
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

# BSZ-hosted dead libraries: (config name, human name for search)
BSZ_LIBS = [
    ("Aalen_HS", "Hochschule Aalen"),
    ("Furtwangen_HS", "Hochschule Furtwangen"),
    ("Heidelberg_PH", "Pädagogische Hochschule Heidelberg"),
    ("Heilbronn_HS", "Hochschule Heilbronn"),
    ("Konstanz_HTWG", "HTWG Konstanz"),
    ("Ludwigsburg_PH", "Pädagogische Hochschule Ludwigsburg"),
    ("Mannheim_HS", "Hochschule Mannheim"),
    ("Mannheim_Muho", "Musikhochschule Mannheim"),
    ("Offenburg_HS", "Hochschule Offenburg"),
    ("Pforzheim_HS", "Hochschule Pforzheim"),
    ("Reutlingen_Hochschulbibliothek", "Hochschule Reutlingen"),
    ("Schwaebisch_Gmuend_Paedagogische_Hochschule", "Pädagogische Hochschule Schwäbisch Gmünd"),
    ("Stuttgart_HdM", "Hochschule der Medien Stuttgart"),
    ("Stuttgart_HfT", "Hochschule für Technik Stuttgart"),
    ("Stuttgart_Muho", "Musikhochschule Stuttgart"),
    ("Trossingen_Muho", "Musikhochschule Trossingen"),
    ("Weingarten_HS", "Pädagogische Hochschule Weingarten"),
    ("Mannheim_Duale_Hochschule", "DHBW Mannheim"),
    ("Mosbach_DHBW", "DHBW Mosbach"),
    ("Nuertingen_HfWU", "HfWU Nürtingen"),
    ("Ravensburg_DHBW", "DHBW Ravensburg"),
    ("Loerrach_DHBW", "DHBW Lörrach"),
]

# Non-BSZ dead libs (probed separately)
OTHER_LIBS = [
    ("Freiburg_UB", "Universitätsbibliothek Freiburg"),
    ("Stuttgart_WLB", "Württembergische Landesbibliothek"),
    ("Tuebingen_Uni", "Universitätsbibliothek Tübingen"),
    ("Ulm_Uni", "Universitätsbibliothek Ulm"),
]


def brave_search(q: str, count: int = 5) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": q, "count": count}
    )
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": BRAVE_KEY,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode()).get("web", {}).get("results", [])


def probe(url: str, timeout: int = 20) -> tuple[int, str]:
    import urllib.error as urlerror

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(60000).decode("utf-8", errors="replace")
            return resp.getcode(), body
    except urlerror.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, f"ERR {type(e).__name__}"


def extract_sp(url: str) -> str | None:
    """Find sp=SOMETHING (symbolic, not S<ip>:<port>) in a URL."""
    m = re.search(r"[?&]sp=([^&]+)", url)
    if not m:
        return None
    val = urllib.parse.unquote(m.group(1))
    if re.match(r"^S\d+\.\d+\.\d+\.\d+", val):
        return None  # old-style IP, skip
    return val


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not BRAVE_KEY:
        print("BRAVE_SEARCH_API_KEY fehlt")
        return 1

    entries = (BSZ_LIBS + OTHER_LIBS)[: args.limit] if args.limit else (BSZ_LIBS + OTHER_LIBS)
    out = []
    for i, (name, human) in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] {name}")
        found = {}
        # Query 1: aDISWeb URL on bsz host
        for q in (
            f'"{human}" aDISWeb Katalog',
            f"{human} Online-Katalog aDISWeb bsz.ibs-bw.de",
        ):
            try:
                hits = brave_search(q)
            except Exception as e:  # noqa: BLE001
                print(f"    search err: {e}")
                continue
            for h in hits[:5]:
                url = h.get("url", "")
                sp = extract_sp(url)
                if sp and "aDISWeb" in url:
                    found[sp] = url
            if found:
                break
            time.sleep(1.1)

        if not found:
            # Query 2: just "Katalog" page, then probe for aDISWeb link
            try:
                hits = brave_search(f"{human} Bibliothek Katalog OPAC")
            except Exception as e:  # noqa: BLE001
                print(f"    search2 err: {e}")
                hits = []
            for h in hits[:3]:
                url = h.get("url", "")
                status, body = probe(url)
                if status == 200 and "aDISWeb" in body:
                    for m in re.finditer(r"https?://[^\"'<> ]*aDISWeb[^\"'<> ]*", body):
                        cand = m.group(0).replace("&amp;", "&")
                        sp = extract_sp(cand)
                        if sp:
                            found.setdefault(sp, cand)
            time.sleep(1.1)

        print(f"    -> {found if found else 'nichts gefunden'}")
        out.append({"library": name, "human": human, "symbolic": found})

    (REPO / "bsz-endpoints.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nReport: bsz-endpoints.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
