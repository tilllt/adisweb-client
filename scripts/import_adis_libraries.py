#!/usr/bin/env python3
"""Import aDIS library configs from opacapp-config-files (MIT licensed).

Source repo: https://github.com/opacapp/opacapp-config-files
This script converts the `bibs/*.json` entries whose `api` field is `adis`
into our `libraries/*.json` format.

Usage:
    .venv/bin/python scripts/import_adis_libraries.py /path/to/opacapp-config-files

Only `baseurl` and `startparams` are carried over (that's all the aDISWeb
client needs); the rest of the opacapp metadata (geo, city, ...) is dropped.
"""

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "libraries"


def convert(src: dict, name: str) -> dict:
    data = src.get("data", {})
    return {
        "name": name,
        "baseurl": data.get("baseurl", ""),
        "startparams": data.get("startparams", ""),
        "encoding": "UTF-8",
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    bibs = Path(sys.argv[1]) / "bibs"
    if not bibs.is_dir():
        print(f"bibs dir not found: {bibs}")
        return 1

    out_backup = OUT / ".." / "libraries.bak"
    if OUT.exists() and not out_backup.exists():
        shutil.copytree(OUT, out_backup)

    imported = 0
    skipped = []
    for f in sorted(bibs.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped.append((f.stem, "invalid JSON"))
            continue
        if data.get("api") != "adis":
            continue
        cfg = convert(data, f.stem)
        if not cfg["baseurl"]:
            skipped.append((f.stem, "no baseurl"))
            continue
        (OUT / f"{f.stem}.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        imported += 1

    print(f"imported {imported} aDIS libraries into {OUT}")
    if skipped:
        print("skipped:")
        for name, why in skipped:
            print(f"  {name}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
