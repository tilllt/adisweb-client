"""Live compatibility scan: does each imported aDIS library work with the
current request pattern (start-page form, $Autosuggest/$Select/$Button)?

Run:
    ADISWEB_LIVE=1 .venv/bin/python scripts/scan_libraries.py [--limit N]

Classification per library:
    OK        search returned parsed hits
    ZERO      session/search worked but 0 results parsed (layout differs?)
    NOFORM    start page has no $Autosuggest form (different generation)
    ERROR     exception (WAF, TLS, timeout, ...) — detail in report
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adisweb import AdisClient, NoResultsError, NotReachableError, OpacError, load_library

REPO = Path(__file__).resolve().parent.parent
LIBRARIES = sorted(p.stem for p in (REPO / "libraries").glob("*.json"))


def scan_one(name: str, query: str = "Berlin", timeout: float = 25.0) -> dict:
    started = time.time()
    result = {"library": name, "status": "?", "hits": -1, "total": -1, "detail": ""}
    try:
        c = AdisClient(load_library(name), timeout=timeout)
        c._start()
        if c.s_app_path is None:
            result["status"] = "NOFORM"
            result["detail"] = "no form action / session token found on start page"
            result["ms"] = int((time.time() - started) * 1000)
            return result
        if not c._start_doc.select_one('input[name="$Autosuggest"]'):
            result["status"] = "NOFORM"
            result["detail"] = "start page has no $Autosuggest input"
            result["ms"] = int((time.time() - started) * 1000)
            return result
        res = c.search_simple(query)
        result["hits"] = len(res.results)
        result["total"] = res.total_result_count
        result["status"] = "OK" if res.results else "ZERO"
        result["detail"] = f"parsed {len(res.results)} hits"
        # sample first hit for the report
        if res.results:
            r0 = res.results[0]
            result["sample"] = re.sub(r"<[^>]+>", " ", r0.innerhtml).strip()[:80]
    except NoResultsError:
        result["status"] = "OK"
        result["hits"] = 0
        result["total"] = 0
        result["detail"] = "search executed, no results (query-specific, OK)"
    except NotReachableError as e:
        result["status"] = "ERROR"
        result["detail"] = f"NotReachable: {str(e)[:120]}"
    except OpacError as e:
        result["status"] = "ERROR"
        result["detail"] = f"OpacError: {str(e)[:120]}"
    except Exception as e:  # noqa: BLE001 - scan must survive anything
        result["status"] = "ERROR"
        result["detail"] = f"{type(e).__name__}: {str(e)[:120]}"
    result["ms"] = int((time.time() - started) * 1000)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=None, help="specific library names")
    ap.add_argument("--json", action="store_true", help="also write libraries-scan.json")
    args = ap.parse_args()

    names = args.only or LIBRARIES
    if args.limit:
        names = names[: args.limit]

    print(f"Scanning {len(names)} libraries (query 'Berlin')...\n")
    rows = []
    for i, name in enumerate(names, 1):
        r = scan_one(name)
        rows.append(r)
        mark = {"OK": "✔", "ZERO": "~", "NOFORM": "✘", "ERROR": "✘"}.get(r["status"], "?")
        print(f"[{i:2}/{len(names)}] {mark} {name:42} {r['status']:7} "
              f"hits={r['hits']:>3} total={r['total']:>8} {r['ms']:>5}ms")
        if r["status"] in ("ZERO", "NOFORM", "ERROR"):
            print(f"          {r['detail']}")
        if r.get("sample"):
            print(f"          sample: {r['sample']}")

    print("\n=== Zusammenfassung ===")
    from collections import Counter

    counts = Counter(r["status"] for r in rows)
    for status in ("OK", "ZERO", "NOFORM", "ERROR"):
        print(f"  {status:7}: {counts.get(status, 0)}")

    if args.json:
        out = REPO / "libraries-scan.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nReport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
