"""Library configuration for aDISWeb OPACs.

Each aDISWeb library differs only in base URL and start parameters.
Configs live as JSON under ``libraries/``; the client core is library-agnostic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LibraryConfig:
    """Configuration for one aDISWeb library."""

    name: str
    baseurl: str
    startparams: str = ""  # query string appended to baseurl on session start
    encoding: str = "UTF-8"
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    @classmethod
    def from_json(cls, path: str | Path) -> "LibraryConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)

    def start_url(self) -> str:
        """Full URL used for session bootstrap."""
        if self.startparams:
            sep = "&" if "?" in self.baseurl else "?"
            return f"{self.baseurl}{sep}{self.startparams}"
        return self.baseurl


def load_library(name: str) -> LibraryConfig:
    """Load a library config from the bundled ``libraries/`` directory."""
    path = Path(__file__).resolve().parent.parent / "libraries" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Library config not found: {path}")
    return LibraryConfig.from_json(path)
