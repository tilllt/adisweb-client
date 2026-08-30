"""adisweb-client — Python client for aDISWeb OPAC systems.

Port of opacapp/opacclient's Adis.java (GPL-3.0).
"""

from .client import AdisClient
from .exceptions import NoResultsError, NotReachableError, OpacError, SearchError
from .libraries import LibraryConfig, load_library
from .models import (
    Copy,
    Detail,
    DetailedItem,
    MediaType,
    SearchRequestResult,
    SearchResult,
    Status,
)

__all__ = [
    "AdisClient",
    "Copy",
    "Detail",
    "DetailedItem",
    "LibraryConfig",
    "MediaType",
    "NoResultsError",
    "NotReachableError",
    "OpacError",
    "SearchError",
    "SearchRequestResult",
    "SearchResult",
    "Status",
    "load_library",
]

__version__ = "0.1.0"
