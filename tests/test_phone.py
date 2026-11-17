"""Phone layout: bottom navigation, cards instead of wide tables, a chart sized for the screen, tap instead of hover"""
import pytest

pytestmark = pytest.mark.guard
from test_burndown_math import load, SCEN, cells, num

TABS = ["map", "cap", "bd", "leave", "log", "who", "how"]


def phone(ctx_factory, mock, name="leave", w=390):
    pg, M, info = load(ctx_factory, mock, name, width=w) if False else (None, None, None)
    return pg


def load_phone(ctx_factory, mock, name="leave", w=390):
    import json
    sc = SCEN[name]; pg = ctx_factory(width=w, height=844, touch=True)
    def bd(route):
        r = route.fetch(); d = r.json(); d["S24"]["people"] = sc["people"]; route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
    pg.route("**/data/burndown.json*", bd)
    if "leave" in sc: pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": sc["leave"]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#v-map :is(.card, .mmh):visible"); return pg


def test_tabs_become_a_bottom_navigation_bar(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); b = pg.locator("#tabs").bounding_box()
    assert pg.evaluate("getComputedStyle(document.querySelector('#tabs')).position") == "fixed" and abs(b["y"] + b["height"] - 844) <= 1 and b["width"] >= 389
    tabs = pg.locator("#tabs .tab"); assert tabs.count() == 7
    for i in range(7):
        t = tabs.nth(i).bounding_box(); assert t["height"] >= 44 and t["width"] >= 44 and t["x"] >= 0 and t["x"] + t["width"] <= 390, (i, t)
    labels = pg.evaluate("[...document.querySelectorAll('#tabs .tl')].map(e => getComputedStyle(e, '::after').content)")
    assert labels == ['"Map"', '"Capacity"', '"Burndown"', '"Leave"', '"Pull log"', '"Roles"', '"How"']
    assert pg.evaluate("getComputedStyle(document.querySelector('.tab .ti')).display") == "block"


def test_desktop_keeps_the_top_tabs(ctx_factory, mock):
    pg = ctx_factory(width=1440); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    assert pg.evaluate("getComputedStyle(document.querySelector('#tabs')).position") != "fixed" and pg.evaluate("getComputedStyle(document.querySelector('.tab .ti')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.tab .tl'), '::after').content") in ("none", "normal")


@pytest.mark.parametrize("w", [360, 390, 430])
def test_nothing_scrolls_sideways_on_a_phone(ctx_factory, mock, w):
    pg = load_phone(ctx_factory, mock, "leave", w)
    for t in TABS:
        pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(120)
        assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1, (t, w)
    pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    for who in ("Team", "Sumit", "Aditi"):
        pg.select_option("#bdwho", who); assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1, (who, w)


def test_tables_turn_into_labelled_cards(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    assert pg.evaluate("getComputedStyle(document.querySelector('#tlog thead')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('#tlog tbody tr')).display") == "block"
    labels = pg.evaluate("[...document.querySelectorAll('#tlog tbody tr:first-child td')].map(c => c.dataset.l || '')")
    assert labels == ["", "Logged (h)", "Over estimate (h)", "Expected log by now (h)", "Missing log (h)", "Leave (h)", "Flag"]
    shown = pg.evaluate("getComputedStyle(document.querySelector('#tlog tbody tr:first-child td:nth-child(2)'), '::before').content")
    assert shown == '"Logged (h)"'
    assert pg.locator("#tplan tbody tr").first.bounding_box()["width"] <= 390


def test_chart_is_drawn_for_the_phone_not_squeezed(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    vb, w = pg.evaluate("() => { const e = document.querySelector('#cw svg'); return [e.viewBox.baseVal.width, e.getBoundingClientRect().width] }")
    assert 300 <= vb <= 390 and abs(vb - w) <= 2, (vb, w)          # one unit is one pixel, so the text is never squeezed
    assert pg.evaluate("document.querySelector('#cw').scrollWidth <= document.querySelector('#cw').clientWidth + 1")
    labels = pg.evaluate("[...document.querySelectorAll('#cw svg text')].map(t => t.textContent)")
    assert "M" in labels and "SPRINT DAY" not in labels, "short day letters on a phone, no long axis titles"
    assert min(float(x.replace('px', '')) for x in pg.evaluate("[...document.querySelectorAll('#cw svg text')].map(t => getComputedStyle(t).fontSize)") if x) >= 10


def test_tap_a_day_shows_the_verdict_and_the_ticket_counts(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    pg.locator("#cw").scroll_into_view_if_needed(); pg.wait_for_timeout(300); b = pg.locator("#cw svg").bounding_box()
    vb = pg.evaluate("document.querySelector('#cw svg').viewBox.baseVal.width"); L, pw, slots = 44, vb - 44 - 12, 11; x = b["x"] + (L + (3 + .5) / slots * pw) / vb * b["width"]
    pg.touchscreen.tap(x, b["y"] + b["height"] * .4); pg.wait_for_selector("#dayd:not([hidden])")
    t = pg.locator("#dayd").inner_text()
    assert "Thu 12 Nov" in t and ("ahead of the ideal pace" in t or "behind the ideal pace" in t or "On ideal pace" in t) and "Sub-tasks" in t and "Closed up to this day" in t, t


def test_tap_targets_are_big_enough(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.wait_for_selector(".seg")
    for sel in (".seg button", "#ddbtn", "#rfbtn"):
        for el in pg.locator(sel).all():
            assert el.bounding_box()["height"] >= 40, (sel, el.bounding_box())
    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#bdwho"); assert pg.locator("#bdwho").bounding_box()["height"] >= 44


def test_hours_by_person_is_a_list_of_bars_on_a_phone(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock, "overtime"); pg.click('[data-tab="bd"]'); pg.wait_for_selector("#gbm")
    assert pg.locator("#gbm .gbr").count() == 3 and pg.locator("#gbm .gbl").count() == 9 and pg.locator(".gb svg").count() == 0 or not pg.locator(".gb svg").is_visible()
    w = pg.evaluate("() => [...document.querySelectorAll('#gbm .gbr')[0].querySelectorAll('.gbt i')].map(i => parseFloat(i.style.width))")
    assert max(w) <= 100 and all(x >= 0 for x in w)


def test_phone_pages_have_no_console_errors(ctx_factory, mock):
    pg = load_phone(ctx_factory, mock)
    for t in TABS: pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(100)
    assert not pg.errors, pg.errors


def test_phone_map_asks_epics_or_user_stories_and_shows_a_numbered_flow(ctx_factory, mock):
    pg = ctx_factory(width=390, height=844, touch=True); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#mm .mmtabs")
    assert pg.locator("#mm").is_visible() and not pg.locator("#mlist").is_visible() and not pg.locator("#map").is_visible()
    assert pg.locator("#mm .mmtabs button").all_inner_texts() == ["Epics", "User stories"] and pg.locator("#mm .mmtabs button[aria-selected=true]").inner_text() == "Epics"
    nums = pg.locator("#mm .mmn").all_inner_texts(); heads = [n for n in nums if "." not in n]; assert heads == [str(i + 1) for i in range(len(heads))], nums
    kids = [n for n in nums if "." in n]; assert kids and all(k.split(".")[0] in heads for k in kids) and nums[0] == "1" and nums[1] == "1.1", nums
    first = pg.locator("#mm .mme").first; assert first.locator(".mmh b").inner_text() == "Zippy ATS Registration" and first.locator(".mms").count() == len([k for k in kids if k.startswith("1.")]) >= 1
    assert pg.locator("#mm .mmc").first.evaluate("e => getComputedStyle(e).borderLeftWidth") == "2px", "a vertical line joins the user stories to their epic"
    pg.click('#mm [data-mm="stories"]'); pg.wait_for_selector("#mm .mmc.flat")
    assert pg.locator("#mm .mmtabs button[aria-selected=true]").inner_text() == "User stories"
    flat = pg.locator("#mm .mmn").all_inner_texts(); assert flat == [str(i + 1) for i in range(len(flat))] and len(flat) == len(kids)
    tags = pg.locator("#mm .mmt").all_inner_texts(); assert tags[0] == "Epic 1 · Zippy ATS Registration" and all(t.startswith("Epic ") or t == "No epic" for t in tags)
    pg.click("#mm .mms >> nth=0"); pg.wait_for_selector("#drawer.on"); assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1


def test_laptop_map_is_unchanged_and_the_phone_flow_is_hidden(ctx_factory, mock):
    pg = ctx_factory(width=1440); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    assert pg.locator("#map").is_visible() and not pg.locator("#mm").is_visible() and pg.locator("#map .card.epic").count() >= 2


def test_phone_labels_are_tapped_not_dotted_with_circles(ctx_factory, mock):
    import json
    from test_burndown_math import SCEN
    pg = load_phone(ctx_factory, mock); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    assert pg.locator("#tlog td .ci, #tplan td .ci").count() == 0 or pg.evaluate("[...document.querySelectorAll('#tlog td .ci, #tplan td .ci')].every(e => getComputedStyle(e).display === 'none')")
    u = pg.evaluate("getComputedStyle(document.querySelector('#tlog tbody tr td[data-tip]'), '::before').textDecorationLine"); assert "underline" in u, "the label of a tappable field is underlined with dots"
    cell = pg.locator("#tlog tbody tr:first-child td[data-tip]").nth(1); cell.scroll_into_view_if_needed(); cell.click(); tip = pg.locator("#gtip"); tip.wait_for()
    assert "sheet" in (tip.get_attribute("class") or "") and "Formula" in tip.inner_text()
    b = tip.bounding_box(); nav = pg.locator("#tabs").bounding_box(); assert b["x"] >= 0 and b["x"] + b["width"] <= 390 and b["y"] + b["height"] <= nav["y"] + 1, "the explanation is a sheet above the tab bar"
    pg.mouse.click(200, 40); pg.wait_for_timeout(150); assert not tip.is_visible()
    # the phone card keeps one right edge for every value
    v = pg.evaluate("[...document.querySelectorAll('#tlog tbody tr:first-child td .v')].map(e => Math.round(e.getBoundingClientRect().right))"); assert len(set(v)) == 1, v
