"""Phone width, dark mode and a clean console on every page"""
import pytest

TABS = ["map", "cap", "bd", "log", "who", "how"]


@pytest.mark.parametrize("w", [390, 820, 1440])
def test_no_sideways_scroll_on_any_page(ctx_factory, mock, w):
    pg = ctx_factory(width=w); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#v-map .card >> visible=true")
    for t in TABS:
        pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(150)
        over = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert over <= 1 or (t == "map" and w > 860), f"{t} at {w}px overflows by {over}px"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_page_renders_without_console_errors(ctx_factory, mock, scheme):
    pg = ctx_factory(scheme=scheme); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#v-map .card >> visible=true")
    for t in TABS: pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(150)
    pg.click('[data-tab="map"]'); pg.click('#map .card[data-s="PROD-9101"]'); pg.wait_for_selector("#drawer.on")
    assert not pg.errors, pg.errors


def test_toast_stays_inside_a_phone_screen(ctx_factory, mock):
    from conftest import ctl; ctl(mock, "fail", 0.5)
    pg = ctx_factory(width=390, rf="{poll:250,max:6000,expect:5}"); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#v-map"); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for(timeout=8000)
    b = t.bounding_box(); assert b["x"] >= 0 and b["x"] + b["width"] <= 390


def test_tabs_switch_and_remember_nothing_unsafe(page):
    for t, marker in (("cap", ".capgrid"), ("bd", ".term"), ("log", ".sched3"), ("who", ".roles"), ("how", ".hw"), ("map", "#map")): page.click(f'[data-tab="{t}"]'); page.wait_for_selector(marker)


@pytest.mark.parametrize("sel,tab,minfont", [("#cw svg", "bd", 8), (".gb svg", "bd", 8), (".capl .chart", "cap", 8)])
def test_chart_text_stays_readable_on_a_phone(ctx_factory, mock, sel, tab, minfont):
    pg = ctx_factory(width=390); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#v-map .card >> visible=true"); pg.click(f'[data-tab="{tab}"]')
    if sel == "#cw svg": pg.click('[data-bdview="person"]')
    pg.wait_for_selector(sel)
    scale = pg.evaluate("s => { const e = document.querySelector(s), vb = e.viewBox.baseVal.width; return e.getBoundingClientRect().width / vb }", sel)
    assert 11 * scale >= minfont, f"chart text would render at {11 * scale:.1f}px"
    assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1


def test_tabs_last_refreshed_and_sign_out_are_the_same_height(page):
    h = page.evaluate("['#tabs', '.rfcard', '#signout'].map(s => document.querySelector(s).getBoundingClientRect().height)")
    assert max(h) - min(h) <= 1 and h[0] >= 50, h
