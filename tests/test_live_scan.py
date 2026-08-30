"""Live compatibility scan for all imported aDIS libraries.

These tests hit the real OPACs and are therefore opt-in:
    ADISWEB_LIVE=1 .venv/bin/python -m pytest tests/test_live_scan.py -v

Each library is classified:
    OK      search returned parsed hits
    ZERO    session/search worked but 0 results parsed (layout differs?)
    ERROR   start page unreachable / wrong config (410/404/TLS/...) —
            these are *config* issues (dead hosts), not client bugs.

Run the full report (with per-library detail) via:
    .venv/bin/python scripts/scan_libraries.py --json
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adisweb import NoResultsError, NotReachableError, OpacError, load_library  # noqa: E402

LIBRARIES = sorted(p.stem for p in (Path(__file__).resolve().parent.parent / "libraries").glob("*.json"))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("ADISWEB_LIVE"),
        reason="live test — set ADISWEB_LIVE=1 to run",
    ),
]


def _scan(name: str) -> str:
    from adisweb import AdisClient

    c = AdisClient(load_library(name), timeout=25.0)
    try:
        c._start()
        res = c.search_simple("Berlin")
        return "OK" if res.results else "ZERO"
    except NoResultsError:
        return "OK"  # executed, query had no hits
    except (OpacError, NotReachableError) as e:
        return f"ERROR: {str(e)[:60]}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {type(e).__name__}: {str(e)[:60]}"


@pytest.mark.parametrize("library", LIBRARIES)
def test_library_searchable(library: str):
    """Every imported aDIS library must answer a search with parsed hits."""
    result = _scan(library)
    assert result == "OK", f"{library}: {result}"
