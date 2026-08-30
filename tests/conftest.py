"""Shared test helpers: load recorded VÖBB fixtures."""

from pathlib import Path

from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


def client() -> "AdisClient":
    from adisweb import AdisClient, load_library

    return AdisClient(load_library("Berlin"))


def make_client() -> "AdisClient":
    return client()
