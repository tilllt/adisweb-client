#!/usr/bin/env python3
"""Record live VÖBB pages as test fixtures (run from repo root).

Usage: .venv/bin/python scripts/record_fixtures.py
Saves: tests/fixtures/start.html, results.html, detail.html
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adisweb import AdisClient, load_library

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

c = AdisClient(load_library("voebb"))
c._start()
(OUT / "start.html").write_text(str(c._start_doc), encoding="utf-8")
print("start.html:", len(str(c._start_doc)))

doc = c._start_doc
autosuggest = doc.select_one('input[name="$Autosuggest"]')
assert autosuggest is not None
autosuggest["value"] = "Berlin"
select = doc.select_one('select[name="$Select"]')
assert select is not None
select["value"] = "Bibliotheksbestand"
nvpairs = c._form_payload(doc)
nvpairs.append(("$Button", "Suchen"))
doc2 = c.html_post(c._opac_url(), nvpairs)
(OUT / "results.html").write_text(str(doc2), encoding="utf-8")
print("results.html:", len(str(doc2)))

r = c.parse_search(doc2, 1).results[0]
detail = c.html_get(r.detail_url)
(OUT / "detail.html").write_text(str(detail), encoding="utf-8")
print("detail.html:", len(str(detail)))
print("recorded id:", r.id)
