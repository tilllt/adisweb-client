#!/usr/bin/env python3
"""Update library configs with discovered symbolic endpoints and verify.

Reads bsz-endpoints.json (from bsz_symbolic_names.py), rewrites the
libraries/*.json configs (baseurl + startparams with symbolic sp=), then
probes each candidate with the real client to pick the working one.

Usage:
    .venv/bin/python scripts/apply_endpoints.py [--check-only]
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from adisweb import AdisClient, NoResultsError, NotReachableError, OpacError, load_library  # noqa: E402


def candidates_for(lib_name: str, entries: list[dict]) -> list[dict]:
    for e in entries:
        if e["library"] == lib_name:
            return [{"sp": sp, "url": url} for sp, url in e.get("symbolic", {}).items()]
    return []


def probe(lib_name: str, sp: str, baseurl: str) -> str:
    """Try the client against baseurl + symbolic sp; returns status string."""
    cfg_path = REPO / "libraries" / f"{lib_name}.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["baseurl"] = baseurl
    cfg["startparams"] = f"service=direct/0/Home/%24DirectLink&sp={sp}"
    try:
        c = AdisClient.from_config(cfg, timeout=25.0)
        res = c.search_simple("Berlin")
        return "OK" if res.results else "ZERO"
    except NoResultsError:
        return "OK(0)"
    except (OpacError, NotReachableError) as e:
        return f"ERR {str(e)[:60]}"
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {str(e)[:60]}"


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true",
                    help="only probe, do not write configs")
    args = ap.parse_args()

    report = json.loads((REPO / "bsz-endpoints.json").read_text(encoding="utf-8"))
    results = []
    for e in report:
        lib_name = e["library"]
        cands = candidates_for(lib_name, report)
        if not cands:
            print(f"{lib_name:45} KEINE KANDIDATEN")
            continue
        chosen = None
        for cand in cands:
            sp = cand["sp"]
            url = cand["url"]
            # derive baseurl from the discovered URL
            from urllib.parse import urlsplit

            baseurl = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}/aDISWeb/app"
            status = probe(lib_name, sp, baseurl)
            print(f"{lib_name:45} {sp:10} {status}")
            if status.startswith("OK"):
                chosen = {"sp": sp, "baseurl": baseurl}
                break
        results.append({"library": lib_name, "chosen": chosen, "candidates": [
            {"sp": c["sp"], "url": c["url"]} for c in cands]})

    if not args.check_only:
        n_ok = 0
        for r in results:
            if not r["chosen"]:
                continue
            cfg_path = REPO / "libraries" / f"{r['library']}.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["baseurl"] = r["chosen"]["baseurl"]
            cfg["startparams"] = f"service=direct/0/Home/%24DirectLink&sp={r['chosen']['sp']}"
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            n_ok += 1
        print(f"\n{len(results)} Bibliotheken, {n_ok} aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
