"""Staying signed in until Sign out, and what happens when many people use the same link"""
import datetime as dt, json, urllib.request
from conftest import PASSWORD, SESSION, NOW


def sign_in(ctx_factory, mock):
    pg = ctx_factory(signed_in=False); pg.goto(mock.url + "/index.html"); pg.fill("#gpw", PASSWORD); pg.press("#gpw", "Enter"); pg.wait_for_selector("#map .card"); return pg


def test_signing_in_keeps_the_browser_signed_in_with_no_expiry(ctx_factory, mock):
    pg = sign_in(ctx_factory, mock); assert pg.evaluate("localStorage.getItem('sd_auth')") == SESSION
    pg.reload(); pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible()
    pg.clock.set_system_time(NOW + dt.timedelta(days=90)); pg.reload(); pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible(), "still signed in after 90 days"


def test_a_new_tab_in_the_same_browser_is_already_signed_in(ctx_factory, mock):
    pg = sign_in(ctx_factory, mock); tab = pg.context.new_page(); tab.goto(mock.url + "/index.html"); tab.wait_for_selector("#map .card"); assert not tab.locator("#gate").is_visible()


def test_sign_out_button_is_in_the_header_and_only_when_signed_in(ctx_factory, mock):
    pg = ctx_factory(signed_in=False); pg.goto(mock.url + "/index.html"); assert not pg.locator("#signout").is_visible()
    pg = sign_in(ctx_factory, mock); b = pg.locator("#signout"); assert b.is_visible() and b.inner_text().strip() == "Sign out"
    rf = pg.locator(".rfcard").bounding_box(); bb = b.bounding_box(); assert bb["x"] >= rf["x"] + rf["width"] - 1 or bb["y"] >= rf["y"] + rf["height"] - 1


def test_sign_out_locks_the_page_forgets_the_session_and_asks_for_the_password_again(ctx_factory, mock):
    pg = sign_in(ctx_factory, mock); pg.click("#signout")
    assert pg.locator("#gate").is_visible() and not pg.locator(".wrap").is_visible() and pg.evaluate("localStorage.getItem('sd_auth')") is None
    t = pg.locator(".tst.info"); t.wait_for(); assert "Signed out" in t.inner_text()
    pg.reload(); assert pg.locator("#gate").is_visible(), "a reload must not sign back in"
    pg.fill("#gpw", PASSWORD); pg.press("#gpw", "Enter"); pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible()


def test_signing_out_in_one_tab_signs_out_every_tab(ctx_factory, mock):
    a = sign_in(ctx_factory, mock); b = a.context.new_page(); b.goto(mock.url + "/index.html"); b.wait_for_selector("#map .card")
    a.click("#signout"); b.wait_for_selector("#gate", state="visible", timeout=5000); assert b.evaluate("localStorage.getItem('sd_auth')") is None


def test_signing_in_in_one_tab_opens_the_other_locked_tab(ctx_factory, mock):
    a = ctx_factory(signed_in=False); a.goto(mock.url + "/index.html"); b = a.context.new_page(); b.goto(mock.url + "/index.html")
    b.fill("#gpw", PASSWORD); b.press("#gpw", "Enter"); b.wait_for_selector("#map .card"); a.wait_for_selector(".wrap", state="visible", timeout=5000)


def test_signing_out_elsewhere_closes_an_open_ticket_here(ctx_factory, mock):
    pg = sign_in(ctx_factory, mock); other = pg.context.new_page(); other.goto(mock.url + "/index.html"); other.wait_for_selector("#map .card")
    pg.click('#map .card[data-s="PROD-9101"]'); pg.wait_for_selector("#drawer.on"); other.click("#signout")
    pg.wait_for_selector("#gate", state="visible", timeout=5000); assert pg.locator("#drawer.on").count() == 0 and pg.locator(".tst.success, .tst.error").count() == 0


# ---------- many people on one link
def newer(mock): urllib.request.urlopen(urllib.request.Request(mock.url + "/__newer", method="POST", data=b""))


def test_a_teammates_refresh_reaches_an_open_page_without_a_click(page, mock):
    assert page.inner_text("#rfval") == "13 Nov, 4:34 PM IST"; newer(mock)
    page.clock.run_for(61000); page.wait_for_function("document.querySelector('#rfval').textContent.includes('4:42 PM')", timeout=8000)
    t = page.locator(".tst.info"); t.wait_for(); assert "Data updated" in t.inner_text() and "someone on the team" in t.inner_text()


def test_the_update_waits_while_a_ticket_is_open_then_arrives(page, mock):
    page.click('#map .card[data-s="PROD-9101"]'); page.wait_for_selector("#drawer.on"); newer(mock)
    page.clock.run_for(61000); page.wait_for_timeout(800); assert page.inner_text("#rfval") == "13 Nov, 4:34 PM IST" and page.locator("#drawer.on").count() == 1, "must not close what the reader is reading"
    page.keyboard.press("Escape"); page.clock.run_for(61000); page.wait_for_function("document.querySelector('#rfval').textContent.includes('4:42 PM')", timeout=8000)


def test_nothing_changes_when_there_is_no_new_data(page):
    page.clock.run_for(130000); page.wait_for_timeout(500); assert page.inner_text("#rfval") == "13 Nov, 4:34 PM IST" and page.locator(".tst").count() == 0
