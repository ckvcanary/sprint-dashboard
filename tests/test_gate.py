"""Sign-in page"""
from conftest import PASSWORD, SESSION


def open_locked(ctx_factory, mock):
    pg = ctx_factory(signed_in=False); pg.goto(mock.url + "/index.html"); return pg


def test_gate_shows_first_and_hides_dashboard(ctx_factory, mock):
    pg = open_locked(ctx_factory, mock)
    assert pg.locator("#gate").is_visible() and not pg.locator(".wrap").is_visible()
    assert pg.get_by_role("heading", name="Sprint Dashboard").is_visible()


def test_wrong_password_shows_toast_top_right_and_stays_locked(ctx_factory, mock):
    pg = open_locked(ctx_factory, mock)
    pg.fill("#gpw", "wrong"); pg.click("#gsub")
    t = pg.locator(".tst.error"); t.wait_for(); assert "Incorrect password" in t.inner_text()
    box = t.bounding_box(); vw = pg.viewport_size["width"]
    assert box["x"] + box["width"] > vw - 40 and box["y"] < 40, "toast must sit in the top right corner"
    assert pg.locator("#gate").is_visible() and pg.locator("#gerr").inner_text() == "Incorrect password. Try again."


def test_show_and_hide_password(ctx_factory, mock):
    pg = open_locked(ctx_factory, mock); pg.fill("#gpw", "abc")
    pg.click("#gshow"); assert pg.get_attribute("#gpw", "type") == "text" and pg.inner_text("#gshow") == "Hide"
    pg.click("#gshow"); assert pg.get_attribute("#gpw", "type") == "password"


def test_correct_password_opens_dashboard_and_survives_reload(ctx_factory, mock):
    pg = open_locked(ctx_factory, mock); pg.fill("#gpw", PASSWORD); pg.press("#gpw", "Enter")
    pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible()
    pg.reload(); pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible()


def test_a_foreign_or_old_marker_does_not_unlock(ctx_factory, mock):
    pg = ctx_factory(signed_in=False); pg.goto(mock.url + "/index.html")
    for bad in ('{"exp": 99999999999999}', "true", "old-marker", ""):
        pg.evaluate("v => localStorage.setItem('sd_auth', v)", bad); pg.reload(); assert pg.locator("#gate").is_visible(), bad
    pg.evaluate("v => localStorage.setItem('sd_auth', v)", SESSION); pg.reload(); assert not pg.locator("#gate").is_visible()


def test_page_marker_matches_the_password_hash(mock):
    src = (mock.site / "index.html").read_text(); import re
    h = re.search(r"GATE_HASH = '([0-9a-f]{64})'", src).group(1); assert f"!=='{h[:12]}'" in src and h[:12] == SESSION


def test_plain_password_is_not_in_the_page_source(mock):
    src = (mock.site / "index.html").read_text()
    assert PASSWORD not in src
