"""Detail view parsing tests against the recorded VÖBB detail page."""

from tests.conftest import load, make_client


def test_parse_result_metadata():
    c = make_client()
    det = c.parse_result("AK15065844", load("detail.html"))
    assert det.title == "Berlin"
    titles = [d.title for d in det.details]
    assert "Titel" in titles
    assert "Person" in titles
    assert "Veröffentlichung" in titles


def test_parse_result_cover():
    c = make_client()
    det = c.parse_result("AK15065844", load("detail.html"))
    assert "vlb/cover/" in det.cover


def test_parse_result_copies():
    c = make_client()
    det = c.parse_result("AK15065844", load("detail.html"))
    assert len(det.copies) >= 1
    copy = det.copies[0]
    assert copy.branch != ""
    assert copy.status != ""


def test_parse_result_reservable():
    c = make_client()
    det = c.parse_result("AK15065844", load("detail.html"))
    assert det.reservable is True
