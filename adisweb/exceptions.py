"""Exceptions for the aDISWeb client."""


class OpacError(Exception):
    """Base error: the OPAC reported a problem (message page, maintenance, ...)."""


class NoResultsError(OpacError):
    """The search returned no hits ("nicht gefunden")."""


class NotReachableError(OpacError):
    """Network-level failure (timeout, WAF block, HTTP error)."""


class SearchError(OpacError):
    """Search could not be executed (no criteria, unsupported combination)."""
