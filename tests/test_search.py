"""Search result parsing tests against the recorded VÖBB hit list."""

from adisweb.models import MediaType, Status
from tests.conftest import load, make_client


def test_parse_search_counts_hits():
    c = make_client()
    res = c.parse_search(load("results.html"), 1)
    assert len(res.results) == 22
    assert res.total_result_count == 1190992
    assert res.page == 1


def test_parse_search_extracts_fields():
    c = make_client()
    res = c.parse_search(load("results.html"), 1)
    r = res.results[0]
    assert r.id == "AK15065844"
    assert r.type == MediaType.BOOK
    assert r.status == Status.GREEN
    assert "Berlin" in r.innerhtml
    assert "Aleš Šteger" in r.innerhtml
    assert "voebb.de/vlb/cover/" in r.cover
    assert "sp=SAK15065844" in r.detail_url


def test_parse_search_ids_sequential():
    c = make_client()
    res = c.parse_search(load("results.html"), 1)
    ids = [r.id for r in res.results]
    assert ids[0] == "AK15065844"
    assert ids[1] == "AK15919359"
    assert len(set(ids)) == len(ids)
