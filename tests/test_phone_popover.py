"""Phone (i) buttons: a popover with an arrow at the tapped button, a gap, tap again or tap anywhere to close"""
import pytest
from test_phone import load_phone

pytestmark = pytest.mark.guard

BOX = "e => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; }"


def visible_buttons(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.ibtn[data-tip]')].map((e, i) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
        return {i, ok: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && r.top > 70 && r.bottom < innerHeight - 90 && r.left >= 0 && r.right <= innerWidth, l: r.left, t: r.top}; }).filter(x => x.ok)""")


def open_phone(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog"); return pg


def check_one(pg, btn):
    b = btn.evaluate(BOX); btn.tap(); tip = pg.locator("#gtip"); tip.wait_for(); pg.wait_for_timeout(260)
    t = tip.evaluate(BOX); a = pg.locator("#gtipA").evaluate(BOX); cx = b["l"] + b["w"] / 2
    assert "pop" in (tip.get_attribute("class") or ""), "phone uses the popover"
    assert t["l"] >= 11 and t["r"] <= 390 - 11, ("inside the screen edges", t)
    nav = pg.locator("#tabs").bounding_box(); assert t["b"] <= nav["y"] + 1, ("above the tab bar", t, nav)
    below = t["t"] > b["b"]; above = t["b"] < b["t"]; assert below or above, "never on top of the button"
    gap = t["t"] - b["b"] if below else b["t"] - t["b"]; assert gap >= 8, ("a clear gap between the button and the popover", gap)
    acx = a["l"] + a["w"] / 2; assert abs(acx - cx) <= 1.5 or acx in (t["l"] + 18, t["r"] - 18), ("the arrow points at the button", acx, cx)
    assert (a["t"] + a["h"] / 2 <= t["t"] + 1) if below else (a["t"] + a["h"] / 2 >= t["b"] - 1), "the arrow sits on the edge facing the button"
    assert pg.locator("#gtipA").is_visible() and btn.get_attribute("aria-expanded") == "true" and btn.get_attribute("aria-describedby") == "gtip"
    return tip


def test_every_visible_info_button_opens_a_popover_with_an_arrow(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); vis = visible_buttons(pg); assert len(vis) >= 3, vis
    pick = vis
    for v in pick:
        btn = pg.locator(".ibtn[data-tip]").nth(v["i"]); tip = check_one(pg, btn)
        pg.mouse.click(5, 300); pg.wait_for_timeout(120); assert not tip.is_visible() and not pg.locator("#gtipA").is_visible()


def test_tapping_the_same_button_again_closes_it(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); btn = pg.locator(".ibtn[data-tip]").nth(visible_buttons(pg)[0]["i"]); tip = check_one(pg, btn)
    btn.tap(); pg.wait_for_timeout(150); assert not tip.is_visible() and not pg.locator("#gtipA").is_visible() and btn.get_attribute("aria-expanded") is None


def test_tapping_anywhere_else_closes_and_inside_does_not(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); btn = pg.locator(".ibtn[data-tip]").nth(visible_buttons(pg)[0]["i"]); tip = check_one(pg, btn)
    tb = tip.bounding_box(); pg.mouse.click(tb["x"] + 20, tb["y"] + 14); pg.wait_for_timeout(150); assert tip.is_visible(), "a tap inside the popover keeps it open"
    pg.mouse.click(195, 760 if tb["y"] < 600 else 120); pg.wait_for_timeout(150); assert not tip.is_visible()


def test_tapping_another_button_moves_the_popover_to_it(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); vis = visible_buttons(pg); a = pg.locator(".ibtn[data-tip]").nth(vis[0]["i"]); b = pg.locator(".ibtn[data-tip]").nth(vis[-1]["i"])
    check_one(pg, a); tip = check_one(pg, b); assert a.get_attribute("aria-expanded") is None


def test_escape_closes_and_the_touch_target_is_44px(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); btn = pg.locator(".ibtn[data-tip]").nth(visible_buttons(pg)[0]["i"])
    hit = btn.evaluate("e => { const a = getComputedStyle(e, '::after'); return [parseFloat(a.width), parseFloat(a.height)]; }"); assert hit[0] >= 44 and hit[1] >= 44, hit
    tip = check_one(pg, btn); pg.keyboard.press("Escape"); pg.wait_for_timeout(120); assert not tip.is_visible()


def test_a_label_tap_on_a_card_also_gets_an_arrow(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); cell = pg.locator("#tlog tbody tr:first-child td[data-tip]").nth(1); cell.scroll_into_view_if_needed(); cell.tap()
    tip = pg.locator("#gtip"); tip.wait_for(); pg.wait_for_timeout(260); assert pg.locator("#gtipA").is_visible() and "pop" in tip.get_attribute("class")
    pg.mouse.click(5, 440 if tip.bounding_box()['y'] < 400 else 120); pg.wait_for_timeout(150); assert not tip.is_visible() and not pg.locator("#gtipA").is_visible()


def test_the_popover_is_not_used_on_desktop(page):
    page.click('[data-tab="bd"]'); b = page.locator(".ibtn[data-tip]").first; b.hover(); page.wait_for_timeout(250)
    assert "pop" not in (page.locator("#gtip").get_attribute("class") or "") and not page.locator("#gtipA").is_visible()


def test_a_button_low_on_the_screen_opens_the_popover_above_it(ctx_factory, mock):
    pg = open_phone(ctx_factory, mock); pg.set_viewport_size({"width": 390, "height": 560}); pg.wait_for_timeout(300)
    vis = [v for v in visible_buttons(pg)]; lowest = max(vis, key=lambda v: v["t"]); btn = pg.locator(".ibtn[data-tip]").nth(lowest["i"])
    nav = pg.locator("#tabs").bounding_box(); b = btn.evaluate(BOX); assert b["t"] > nav["y"] - 230, ("the button is low enough", b, nav)
    tip = check_one(pg, btn); assert tip.evaluate(BOX)["b"] < b["t"], "not enough room below, so it opens above with the arrow pointing down"
    assert "up" in pg.locator("#gtipA").get_attribute("class")
