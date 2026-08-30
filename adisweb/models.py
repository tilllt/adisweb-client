"""Data model for aDISWeb OPAC results (ported from opacapp/opacclient objects)."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from enum import Enum


class MediaType(Enum):
    """Media types mapped from the aDISWeb image title attributes."""

    BOOK = "Buch"
    CD_SOFTWARE = "CD/DVD-ROM"
    PACKAGE = "Medienkombination"
    DVD = "DVD-Video"
    SCORE_MUSIC = "Noten"
    GAME_CONSOLE = "Konsolenspiel"
    CD = "CD"
    MAGAZINE = "Zeitschrift"
    NEWSPAPER = "Zeitung"
    EBOOK = "E-Book"
    MAP = "Karte"
    EAUDIO = "E-Audio"
    BLURAY = "Blu-Ray"
    UNKNOWN = "Unbekannt"

    @classmethod
    def from_title(cls, title: str) -> "MediaType":
        """Map an aDISWeb image title to a MediaType (case-insensitive)."""
        if not title:
            return cls.UNKNOWN
        t = title.strip()
        mapping = {
            "buch": cls.BOOK,
            "band": cls.BOOK,
            "dvd-rom": cls.CD_SOFTWARE,
            "cd-rom": cls.CD_SOFTWARE,
            "medienkombination": cls.PACKAGE,
            "dvd-video": cls.DVD,
            "dvd": cls.DVD,
            "noten": cls.SCORE_MUSIC,
            "konsolenspiel": cls.GAME_CONSOLE,
            "spielkonsole": cls.GAME_CONSOLE,
            "cd": cls.CD,
            "zeitschrift": cls.MAGAZINE,
            "zeitschriftenheft": cls.MAGAZINE,
            "zeitung": cls.NEWSPAPER,
            "beitrag e-book": cls.EBOOK,
            "elektronische ressource": cls.EBOOK,
            "e-book": cls.EBOOK,
            "e-ressource": cls.EBOOK,
            "karte": cls.MAP,
            "e-audio": cls.EAUDIO,
            "blu-ray": cls.BLURAY,
            "munzinger": cls.EBOOK,
        }
        return mapping.get(t.lower(), cls.UNKNOWN)


class Status(Enum):
    """Availability status of a search hit."""

    UNKNOWN = 0
    GREEN = 1
    RED = 2
    YELLOW = 3


@dataclass
class SearchResult:
    """One entry in the hit list."""

    nr: int = 0
    id: str = ""
    innerhtml: str = ""  # title + author/year, "<br />"-joined like the Java original
    type: MediaType = MediaType.UNKNOWN
    status: Status = Status.UNKNOWN
    cover: str = ""
    detail_url: str = ""  # direct detail URL (current-gen aDISWeb)


@dataclass
class Detail:
    """A single metadata row of the detail view (title/value or title/URL)."""

    title: str
    content: str = ""
    url: str = ""


@dataclass
class Copy:
    """One physical copy / holding row of the detail view."""

    branch: str = ""
    location: str = ""
    signature: str = ""
    status: str = ""
    return_date: _dt.date | None = None
    url: str = ""


@dataclass
class DetailedItem:
    """Full record detail view."""

    id: str = ""
    title: str = ""
    cover: str = ""
    details: list[Detail] = field(default_factory=list)
    copies: list[Copy] = field(default_factory=list)
    reservable: bool = False
    reservation_info: str = ""


@dataclass
class SearchRequestResult:
    """A page of search results."""

    results: list[SearchResult] = field(default_factory=list)
    total_result_count: int = -1
    page: int = 1
