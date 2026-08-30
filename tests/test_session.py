"""Session bootstrap tests against the recorded VÖBB start page."""

from adisweb import AdisClient, load_library


def test_start_captures_session_state():
    c = AdisClient(load_library("Berlin"))
    c._start()
    assert c.s_app_path is not None
    assert c.s_app_path.startswith("/aDISWeb/_")
    assert c.s_app_path.endswith("/app")


def test_start_pageform_has_identity():
    c = AdisClient(load_library("Berlin"))
    c._start()
    names = [n for n, _ in c.s_pageform]
    assert "identity" in names
    # $Autosuggest/$Select carry empty values on the start page and are
    # correctly skipped by update_pageform (they get set before the POST)
    assert "requestCount" in names


def test_update_pageform_skips_empty_and_buttons():
    from tests.conftest import load

    c = AdisClient(load_library("Berlin"))
    doc = load("start.html")
    c.update_pageform(doc)
    assert len(c.s_pageform) >= 5
    for name, value in c.s_pageform:
        assert value != ""
        assert not name.startswith("$Button")
