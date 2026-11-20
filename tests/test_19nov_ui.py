"""19 Nov 2026 UI changes: full screen chart, day detail with Filter and a visible Close, matching band fonts, compact 3.5 s toasts, no Roles page.
Checked at laptop, tablet and phone widths for overflow and overlap, in light and dark."""
import pytest
from test_burndown import open_bd, click_slot

pytestmark = pytest.mark.guard
SIZES = [(1440, 900), (1024, 768), (390, 844)]


def rect(pg, sel): return pg.evaluate("s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height} }", sel)


def test_roles_page_is_gone(page):
    assert page.locator('[data-tab="who"]').count() == 0 and page.locator("#v-who").count() == 0
    assert [t.strip() for t in page.locator("#tabs .tab").all_inner_texts()] == ["Map", "Capacity", "Burndown", "Leave", "Pull log", "How it works"]
    assert "Stakeholders" not in page.content()


@pytest.mark.parametrize("w,h", SIZES)
def test_band_labels_slim_and_same_style(ctx_factory, mock, w, h):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); open_bd(pg)
    f = pg.evaluate("() => [...document.querySelectorAll('#cw svg g.bnd text')].map(t => [t.textContent, t.getAttribute('font-size'), t.getAttribute('font-weight')])")
    if f: assert len({(a[1], a[2]) for a in f}) == 1 and float(f[0][1]) <= 11, f      # one small size and weight for every caption
    leg = pg.locator(".bdleg").inner_text(); assert "Sprint Planning" in leg and "Retrospective" not in leg, leg      # the chart ends on Friday; the Monday after belongs to the next sprint
    ok = pg.evaluate("() => [...document.querySelectorAll('#cw svg g.bnd')].every(g => { const r = g.querySelector('rect').getBoundingClientRect(); return [...g.querySelectorAll('text')].every(t => { const b = t.getBoundingClientRect(); return b.left >= r.left - 1 && b.right <= r.right + 1; }); })")
    assert ok, "a band caption spills outside its band"


def test_pinned_day_is_light_blue_and_labelled(page):
    open_bd(page); click_slot(page, 4); page.wait_for_selector("#dayd:not([hidden])")
    assert page.get_attribute("#guide", "fill") == "var(--blue)" and page.locator("#guidelbl").get_attribute("visibility") == "visible"
    assert "CURRENTLY" in page.locator("#guidelbl").text_content().upper() and "OPEN" in page.locator("#guidelbl").text_content().upper()
    import re
    bg = page.evaluate("() => getComputedStyle(document.querySelector('#dayd')).backgroundColor")
    v = [float(x) for x in re.findall(r"[\d.]+", bg)[:3]]; r, b = v[0], v[2]
    assert b > r + (0.02 if "color(" in bg else 5), bg      # the open panel has a blue tint
    page.click("[data-dayclose]"); assert page.locator("#guidelbl").get_attribute("visibility") == "hidden"


def test_status_box_open_and_closed_tabs(page):
    open_bd(page)
    html = page.evaluate("() => jiraPop()")
    assert "Counted as open" in html and "Counted as closed" in html and ">Statuses<" not in html
    assert html.count("Technical Review") >= 1 and "In Documentation" in html      # both are open statuses for sub-tasks
    page.evaluate("() => { jiraTab = 'closed'; }"); closed = page.evaluate("() => jiraPop()")
    assert "Deployed to Prod" in closed and "In Documentation" not in closed.split("ttnote")[0].split("Sub-task")[-1]
    page.evaluate("() => { jiraTab = 'open'; }")


def test_today_cell_is_outline_only(page):
    open_bd(page)
    bad = page.evaluate("""() => { const out = []; document.querySelectorAll('#dgrid .dgr:not(.dgh)').forEach(r => { const cs = [...r.querySelectorAll('.dgc')], i = cs.findIndex(c => c.classList.contains('now')); if (i >= 0) { const c = cs[i]; if (/ok|warn|bad/.test(c.className)) out.push(c.className); } });
      const cols = new Set(); document.querySelectorAll('#dgrid .dgr:not(.dgh)').forEach(r => { [...r.querySelectorAll('.dgc')].forEach((c, i) => { if (c.classList.contains('now')) cols.add(i); }); });
      document.querySelectorAll('#dgrid .dgr:not(.dgh)').forEach(r => { const cs = [...r.querySelectorAll('.dgc')]; cols.forEach(i => { if (cs[i] && /\\b(ok|warn|bad)\\b/.test(cs[i].className)) out.push('column ' + i + ' ' + cs[i].className); }); }); return out; }""")
    assert not bad, bad      # today is never green, amber or red for anybody


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_fullscreen_detail_is_right_under_chart(ctx_factory, mock, scheme):
    pg = ctx_factory(width=1440, height=900, scheme=scheme); pg.goto(mock.url + "/index.html"); open_bd(pg)
    pg.click("#fsbtn"); pg.wait_for_selector("#lcpanel.fs")
    p = rect(pg, "#lcpanel"); assert p["l"] == 0 and p["t"] == 0 and abs(p["w"] - 1440) < 1 and abs(p["h"] - 900) < 1, p
    assert pg.locator("#fsbtn").inner_text().strip() == "Exit full screen"
    click_slot(pg, 4); pg.wait_for_selector("#dayd:not([hidden])")
    c, d = rect(pg, "#cw svg"), rect(pg, "#dayd")
    gap = d["t"] - c["b"]; assert 0 <= gap <= 14, f"gap between chart and details is {gap}px"
    assert d["t"] < 900 - 120, "the detail header must be on screen without scrolling"
    x = rect(pg, "[data-dayclose]"); assert x and 0 <= x["t"] and x["b"] <= 900 and x["h"] >= 28
    col = pg.evaluate("() => getComputedStyle(document.querySelector('[data-dayclose]')).backgroundColor"); assert col not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)", "rgb(14, 23, 38)"), col
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1
    pg.keyboard.press("Escape"); pg.wait_for_selector("#lcpanel:not(.fs)")
    assert pg.evaluate("document.body.classList.contains('fsopen')") is False
    assert pg.locator("#fsbtn").inner_text().strip() == "Full screen"


def test_normal_view_gap_and_close_visible(page):
    open_bd(page); click_slot(page, 4); page.wait_for_selector("#dayd:not([hidden])")
    gap = rect(page, "#dayd")["t"] - rect(page, "#cw svg")["b"]; assert 0 <= gap <= 14, gap
    x = rect(page, "[data-dayclose]"); assert x and x["w"] > 60
    page.click("[data-dayclose]"); assert page.locator("#dayd").is_hidden()


def test_filter_checkboxes_replace_tabs(page):
    open_bd(page); click_slot(page, 4); page.wait_for_selector("#dayd:not([hidden])")
    assert page.locator("[data-dtab]").count() == 0 and page.locator("[data-dfilter]").count() == 1
    def keys(): return page.evaluate("() => [...document.querySelectorAll('#dayd .dtab tbody tr:not(.dgrp):not(.rnone) td:first-child a')].map(a => a.textContent)")
    dflt = keys(); assert page.locator("[data-dfilter] b").inner_text() == "1"
    page.click("[data-dfilter]"); assert page.locator("#dfm").is_visible()
    assert [t.strip() for t in page.locator("#dfm label").all_inner_texts()] == ["Closed on this day", "Closed up to this day", "Still open"]
    page.check('[data-dfk="open"]'); both = keys(); assert set(dflt) <= set(both) and len(both) >= len(dflt) and len(both) == len(set(both))
    assert page.locator("[data-dfilter] b").inner_text() == "2" and page.locator("#dfm").is_visible()      # the menu stays open while ticking
    page.uncheck('[data-dfk="today"]'); page.click('[data-dfk="open"]')      # every box can be cleared
    assert not any(page.locator(f'[data-dfk="{k}"]').is_checked() for k in ("today", "closed", "open"))
    assert page.locator("[data-dfilter] b").inner_text() == "0" and "Tick a group" in page.locator("#dayd .dtab").inner_text()
    page.keyboard.press("Escape"); assert page.locator("#dfm").is_hidden()
    nums = page.evaluate("() => [...document.querySelectorAll('#dayd .dsum tbody tr')].map(r => r.innerText.replace(/\\s+/g,' '))"); assert len(nums) == 3


@pytest.mark.parametrize("w,h", SIZES)
def test_day_detail_no_overflow_or_overlap(ctx_factory, mock, w, h):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); open_bd(pg)
    pg.click("#fsbtn"); click_slot(pg, 4); pg.wait_for_selector("#dayd:not([hidden])")
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1
    ov = pg.evaluate("() => { const p = document.querySelector('#lcpanel'); return p.scrollWidth - p.clientWidth }"); assert ov <= 1, ov
    a, b = rect(pg, ".dh h3"), rect(pg, "[data-dayclose]"); assert a["r"] <= b["l"] + 1, "title overlaps the Close button"
    f, s = rect(pg, "[data-dfilter]"), rect(pg, ".dsel"); assert f["r"] <= s["l"] + 1 or f["b"] <= s["t"] + 1 or s["b"] <= f["t"] + 1, "filter button overlaps its summary"
    pg.click("[data-dfilter]"); m = rect(pg, "#dfm"); assert m["l"] >= 0 and m["r"] <= w + 1, m
    assert not pg.errors, pg.errors


def test_toast_compact_and_leaves_in_3_5_seconds(page):
    page.evaluate("notify({kind: 'success', title: 'Data refreshed', text: 'Sprint 24 · 105 issues synced from Jira', meta: 'Last refreshed 19 Nov, 7:13 PM IST'})")
    page.wait_for_selector(".tst.on"); h = rect(page, ".tst")["h"]; assert h <= 78, f"toast is {h}px tall"
    assert page.locator(".tst .tbar").count() == 1
    page.clock.run_for(3000); assert page.locator(".tst").count() == 1
    page.clock.run_for(900); page.wait_for_timeout(100); page.clock.run_for(400); assert page.locator(".tst").count() == 0


def test_error_toast_also_short(page):
    page.evaluate("notify({kind: 'error', title: 'Refresh failed', text: 'x', ms: 9000})"); page.wait_for_selector(".tst.on")
    page.clock.run_for(4400); page.clock.run_for(400); assert page.locator(".tst").count() == 0       # an old 9 s request is capped at 4 s


def test_hover_card_does_not_cover_the_details_just_opened(page):
    from test_burndown import hover_slot
    open_bd(page); click_slot(page, 4); page.wait_for_selector("#dayd:not([hidden])")
    assert page.locator("#tip").is_hidden(), "the hover card must not sit over the details that were just opened"
    hover_slot(page, 6); assert page.locator("#tip").is_visible()      # moving to another day brings the hover card back


@pytest.mark.parametrize("slot", [0, 4, -1])
def test_open_label_never_overlaps_caption_or_line(page, slot):
    open_bd(page); n = page.evaluate("BDV.slots"); click_slot(page, slot if slot >= 0 else n - 1); page.wait_for_selector("#dayd:not([hidden])")
    r = page.evaluate("""() => { const l = document.querySelector('#guidelbl').getBoundingClientRect(); const out = [];
      document.querySelectorAll('#cw svg g.bnd text').forEach(t => { const b = t.getBoundingClientRect(); if (!(b.right < l.left || b.left > l.right || b.bottom < l.top || b.top > l.bottom)) out.push(t.textContent); }); return out; }""")
    assert not r, r      # the label does not sit on a band caption
