"""20 Nov 2026 changes: four burndown cards, success text, toasts on the right edge, Sprint end marker, Completed verdict, ticket panel details"""
import json, re
import pytest
from test_burndown import open_bd
from test_info_tips import hover

pytestmark = pytest.mark.guard
SIZES = [(1440, 900), (1280, 800), (1024, 768), (820, 900), (390, 844)]


# ---------------------------------------------------------------- four cards
def test_four_cards_in_the_agreed_order_with_the_timeline(page):
    open_bd(page)
    labels = page.evaluate("() => [...document.querySelectorAll('#daywidgets .dwc .fl')].map(e => e.childNodes[0].textContent.trim())")
    assert labels == ["Sprint timeline", "Sprint day", "Capacity day", "Sprint success"], labels
    assert page.locator("#wtimeline b").inner_text() == "9 – 20 Nov" and page.locator("#wtimeline em").inner_text() == "Sprint 24 · 10 working days"


@pytest.mark.parametrize("w,h", SIZES)
def test_four_cards_never_overflow_or_overlap(ctx_factory, mock, w, h):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); open_bd(pg)
    r = pg.evaluate("""() => { const cs = [...document.querySelectorAll('#daywidgets .dwc')], out = { cards: cs.length, bad: [], lefts: new Set(), tops: new Set() };
      cs.forEach(c => { const b = c.querySelector('b'), q = c.getBoundingClientRect(); if (b.scrollWidth > b.clientWidth + 1) out.bad.push(c.id + ' text wider than its card'); if (q.right > innerWidth + 1 || q.left < -1) out.bad.push(c.id + ' outside the screen'); out.lefts.add(Math.round(q.left)); out.tops.add(Math.round(q.top)); });
      for (let i = 0; i < cs.length; i++) for (let j = i + 1; j < cs.length; j++) { const a = cs[i].getBoundingClientRect(), b = cs[j].getBoundingClientRect(); if (a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1) out.bad.push('overlap ' + cs[i].id + ' ' + cs[j].id); }
      return { cards: out.cards, bad: out.bad, cols: out.lefts.size, rows: out.tops.size, page: document.documentElement.scrollWidth - innerWidth }; }""")
    assert r["cards"] == 4 and not r["bad"] and r["page"] <= 1, r
    assert (r["cols"], r["rows"]) == ((4, 1) if w > 1100 else (2, 2)), r      # one row of four on a laptop, two by two on a tablet or phone
    assert not pg.errors, pg.errors


def test_success_text_has_no_rate_of_one(page):
    open_bd(page); t = hover(page, page.locator("#wsuccess .ibtn")); x = t.inner_text()
    assert "Share of committed tasks that are closed" in x and "rate of 1" not in x.lower() and "100%" not in x.split("Calculation")[0].split("Example")[0], x


# ---------------------------------------------------------------- toasts
def test_toast_text_is_short_and_sits_on_the_right_edge(page):
    page.evaluate("notify({kind: 'success', title: 'Pulled from Jira', text: '12 tickets updated', meta: '1,041 tickets read'})")
    t = page.locator(".tst.success"); t.wait_for(); page.wait_for_timeout(300)
    b = t.bounding_box(); vp = page.viewport_size
    assert vp["width"] - (b["x"] + b["width"]) <= 28 and vp["height"] - (b["y"] + b["height"]) <= 28 and b["height"] <= 90, (b, vp)
    assert t.inner_text().replace("\n", " ").replace("×", "").split() == "Pulled from Jira 12 tickets updated 1,041 tickets read".split()


def test_toast_on_a_phone_sits_above_the_bottom_bar(ctx_factory, mock):
    pg = ctx_factory(width=390, height=844); pg.goto(mock.url + "/index.html"); pg.wait_for_function("() => document.querySelectorAll('#mlist .item, #mlist button, #map .card').length > 0")
    pg.evaluate("notify({kind: 'info', title: 'Pulled from Jira', text: 'No tickets updated', meta: '1,041 tickets read'})"); t = pg.locator(".tst.info"); t.wait_for(); pg.wait_for_timeout(300)
    b = t.bounding_box(); bar = pg.evaluate("() => { const e = document.querySelector('.mbar, .tabbar, #mobtabs, nav.bottom'); if (e) { const r = e.getBoundingClientRect(); return r.top; } return null; }")
    assert b["x"] >= 0 and b["x"] + b["width"] <= 390 + 1 and b["y"] + b["height"] <= 844 - 60, b
    if bar: assert b["y"] + b["height"] <= bar + 1, (b, bar)      # never on top of the bottom bar


# ---------------------------------------------------------------- Sprint end marker
def test_the_last_friday_is_marked_as_sprint_end(page):
    open_bd(page)
    r = page.evaluate("""() => { const g = [...document.querySelectorAll('#cw svg g.bnd')]; const last = g[g.length - 1], rc = last.querySelector('rect');
      return { n: g.length, text: last.textContent, end: +rc.getAttribute('x') + +rc.getAttribute('width'), plot: BDV.L + BDV.pw, start: +rc.getAttribute('x'), lastSlot: BDV.L + (BDV.slots - 1) / BDV.slots * BDV.pw, title: last.querySelector('title').textContent, slots: BDV.slots }; }""")
    assert r["n"] == 2 and "SPRINT END" in r["text"] and abs(r["end"] - r["plot"]) < .5 and abs(r["start"] - r["lastSlot"]) < .5 and r["slots"] == 10, r      # the band sits exactly on the last working day, Friday
    assert "Sprint end: Fri 20 Nov, Day 10" in r["title"]
    assert "Sprint end · Fri 20 Nov" in page.locator(".bdleg").inner_text()


# ---------------------------------------------------------------- verdict
def test_verdict_is_completed_when_the_remaining_estimate_is_zero(page):
    open_bd(page)
    r = page.evaluate("""() => { const s = BD.S24, wd = workDays(s.win), at = asOfIST(), ad = at.slice(0, 10), mk = (E, burn) => person('X', { E, logs: burn, burn }, wd, at, ad, []);
      return [mk(52, { '2026-11-11': 52 }), mk(0, {}), mk(52, { '2026-11-11': 10 })].map(x => [x.vd, x.vc]); }""")
    assert r[0] == ["Completed", "ok"] and r[1] == ["No work planned", "nil"] and r[2][0] in ("Achievable", "Not achievable"), r      # 52 h estimated and 0 h left is Completed, not Achievable


# ---------------------------------------------------------------- ticket panel
def story_panel(page, key="PROD-9101"):
    page.evaluate("closeD()"); page.wait_for_timeout(350)      # a panel that is already open covers the map
    page.click(f'#map .card[data-s="{key}"]'); d = page.locator("#drawer.on"); d.wait_for(); return d


def task_panel(page, task, story="PROD-9101"):
    d = story_panel(page, story); d.locator(f'[data-t="{task}"]').click(); page.wait_for_function("document.querySelector('#drawer h2')?.textContent.length > 0 && !!document.querySelector('#drawer .kind.task')"); return page.locator("#drawer.on")


def test_task_panel_shows_reporter_assignee_due_date_labels_and_where_it_lives(page):
    d = task_panel(page, "PROD-9111"); facts = page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#drawer .fact')].map(f => [f.querySelector(':scope > span').childNodes[0].textContent.trim(), f.querySelector('b').textContent.trim()]))")
    assert facts["Assignee"] == "Nikita" and facts["Reporter"] == "Chetan Kumar Verma" and facts["Due date"] == "Fri 20 Nov", facts
    assert [l.inner_text() for l in d.locator(".lbl").all()] == ["frontend"]
    w = d.locator(".where").inner_text(); assert "Product Development" in w and "PROD board" in w and "Space" in w and "Board" in w


def test_time_bars_show_estimate_and_logged_with_the_share_logged(page):
    d = task_panel(page, "PROD-9111"); assert d.locator(".trk").count() == 2
    assert d.locator(".tpct").inner_text() == "88% logged" and "8 h" in d.locator(".tb").nth(0).inner_text() and "7 h" in d.locator(".tb").nth(1).inner_text()
    w = d.evaluate("() => [...document.querySelectorAll('#drawer .trk i')].map(i => parseFloat(i.style.width))"); assert w[0] == 100 and abs(w[1] - 87.5) < .1, w      # two bars on one scale
    d = task_panel(page, "PROD-9113"); assert d.locator(".tpct").inner_text() == "0% logged"
    d = task_panel(page, "PROD-9112"); assert d.locator(".tpct").inner_text() == "113% logged" and d.locator(".tpct.over").count() == 1 and d.locator(".trk i.log.over").count() == 1      # over the estimate is red


def test_story_and_epic_panels_add_up_their_tasks(page):
    d = story_panel(page); assert d.locator(".tpct").inner_text() == "64% logged" and "18 h" in d.locator(".tb").nth(0).inner_text() and "11.5 h" in d.locator(".tb").nth(1).inner_text()      # (7 + 4.5 + 0) / (8 + 4 + 6)
    assert [l.inner_text() for l in d.locator(".lbl").all()] == ["zippy", "documentation-task"] and d.locator(".lbl.doc").count() == 1      # the documentation label stands out
    page.keyboard.press("Escape"); page.click('#map .card.epic[data-e="PROD-9001"]'); e = page.locator("#drawer.on"); e.wait_for()
    assert "reporter" in e.inner_text().lower() and e.locator(".tpct").inner_text() == "70% logged", e.inner_text()      # (11.5 + 4) / (18 + 4)


def test_linked_work_items_are_listed_in_the_panel(page):
    d = story_panel(page); lk = d.locator(".item.lkd"); assert lk.count() == 1 and "PROD-9102" in lk.inner_text() and "blocks" in lk.inner_text() and "In Testing" in lk.inner_text()
    assert lk.get_attribute("href").endswith("/browse/PROD-9102") and lk.get_attribute("target") == "_blank" and "linked work items (1)" in d.inner_text().lower()
    d = task_panel(page, "PROD-9111"); assert "is blocked by" in d.locator(".item.lkd").inner_text()
    d = task_panel(page, "PROD-9113"); assert "linked work items (0)" in d.inner_text().lower() and "No linked work items in Jira" in d.inner_text()
    order = d.evaluate("() => [...document.querySelectorAll('#drawer .sec .lb')].map(x => x.textContent.replace(/ \\(\\d+\\)$/, ''))")
    assert order.index("Linked work items") < order.index("Comments"), order      # linked items come before the comments


def test_map_page_says_which_space_and_board_it_belongs_to(page):
    t = page.locator("#scopebar").inner_text().replace("\n", " "); assert "Space" in t and "Product Development" in t and "Board" in t and "PROD board" in t, t


def test_old_data_without_the_new_fields_still_opens_cleanly(ctx_factory, mock):
    def strip(route):
        r = route.fetch(); b = r.json(); b.pop("info", None); b.pop("scope", None); route.fulfill(response=r, body=json.dumps(b))
    pg = ctx_factory(); pg.route("**/data/map.json*", strip); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    d = story_panel(pg); assert "appear after the next refresh" in d.inner_text() and "Product Development" in d.inner_text() and not pg.errors, pg.errors      # falls back to the known space and board names


@pytest.mark.parametrize("w,h", [(1440, 900), (390, 844)])
def test_panel_fits_the_screen(ctx_factory, mock, w, h):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); pg.wait_for_function("() => document.querySelectorAll('#mlist .item, #mlist button, #map .card').length > 0")
    pg.evaluate("openItem('s', 'PROD-9101')"); pg.wait_for_selector("#drawer.on"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => { const d = document.querySelector('#drawer'); return { over: d.scrollWidth - d.clientWidth, bars: [...d.querySelectorAll('.tb')].every(t => t.scrollWidth <= t.clientWidth + 1), facts: [...d.querySelectorAll('.fact')].every(f => f.scrollWidth <= f.clientWidth + 1) }; }")
    assert r["over"] <= 1 and r["bars"] and r["facts"], r
    pg.evaluate("openItem('t', 'PROD-9111')"); pg.wait_for_timeout(200)
    r = pg.evaluate("() => { const d = document.querySelector('#drawer'); return d.scrollWidth - d.clientWidth; }"); assert r <= 1
