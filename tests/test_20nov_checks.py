"""20 Nov 2026 checks: small screens (overflow, clipped text, overlapping text) and logic (status lists in the info boxes against the data script and the grids)"""
import importlib.util, json, pathlib
import pytest
from test_burndown import open_bd

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("refresh", ROOT / "scripts" / "refresh.py"); R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)

# ------------------------------------------------------------------ small screens
WIDTHS = [(320, 640), (360, 740), (375, 812), (390, 844), (412, 915), (430, 932), (600, 900), (720, 900), (768, 1024)]
PAGES = ["map", "cap", "bd-overall", "bd-person", "leave", "log", "how"]

CHECK = """() => {
  const vw = innerWidth, out = [], vis = e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return r.width > 2 && r.height > 2 && c.visibility !== 'hidden' && c.display !== 'none' && c.opacity !== '0' && !e.closest('[hidden]') && !(e.closest('details:not([open])') && !e.closest('summary')) && !e.closest('#drawer:not(.on)'); };
  const sideways = document.documentElement.scrollWidth - vw; if (sideways > 1) out.push('page scrolls sideways by ' + sideways + 'px');
  const scrolls = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') return true; } return false; };
  const label = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/)[0] : '')) + ' "' + (e.textContent || '').trim().slice(0, 30) + '"';
  const scope = document.querySelector('main') || document.body;
  scope.querySelectorAll('*').forEach(e => { if (!vis(e) || e.closest('svg') || e.closest('.tip, #gtip, #tip, #toasts, #stack, .sr')) return; const r = e.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !scrolls(e)) out.push('sticks out of the screen: ' + label(e));
    const c = getComputedStyle(e); if ((c.overflow === 'hidden' || c.overflowX === 'hidden') && c.textOverflow !== 'ellipsis' && e.children.length === 0 && (e.textContent || '').trim() && e.scrollWidth > e.clientWidth + 1) out.push('text is cut off: ' + label(e)); });
  const leaves = [...scope.querySelectorAll('*')].filter(e => vis(e) && !e.closest('svg') && !e.closest('.tip, #gtip, #tip, #toasts, #stack, .sr, select, option') && e.children.length === 0 && (e.textContent || '').trim().length > 0);
  for (let i = 0; i < leaves.length; i++) for (let j = i + 1; j < leaves.length; j++) { const a = leaves[i], b = leaves[j]; if (a.contains(b) || b.contains(a)) continue; const p = a.getBoundingClientRect(), q = b.getBoundingClientRect();
    const w = Math.min(p.right, q.right) - Math.max(p.left, q.left), h = Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top); if (w > 3 && h > 3) out.push('text overlaps: ' + label(a) + ' and ' + label(b)); }
  return out.slice(0, 12);
}"""


def go(pg, name):
    if name == "map": pg.click('[data-tab="map"]')
    elif name == "cap": pg.click('[data-tab="cap"]')
    elif name == "bd-overall": pg.click('[data-tab="bd"]'); pg.click('[data-bdview="overall"]')
    elif name == "bd-person": pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    elif name == "leave": pg.click('[data-tab="leave"]')
    elif name == "log": pg.click('[data-tab="log"]')
    elif name == "how": pg.click('[data-tab="how"]')
    pg.wait_for_timeout(250)


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize("w,h", WIDTHS)
def test_no_overflow_cut_off_or_overlapping_text_on_small_screens(ctx_factory, mock, w, h, name):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); pg.wait_for_function("() => document.querySelectorAll('#mlist .item, #mlist button, #map .card').length > 0")
    go(pg, name); problems = pg.evaluate(CHECK)
    assert not problems, (w, name, problems)
    assert not pg.errors, pg.errors


@pytest.mark.parametrize("w,h", WIDTHS)
def test_ticket_panel_and_day_panel_fit_small_screens(ctx_factory, mock, w, h):
    pg = ctx_factory(width=w, height=h); pg.goto(mock.url + "/index.html"); pg.wait_for_function("() => document.querySelectorAll('#mlist .item, #mlist button, #map .card').length > 0")
    for kind, key in (("e", "PROD-9001"), ("s", "PROD-9101"), ("t", "PROD-9111"), ("t", "PROD-9112")):
        pg.evaluate(f"closeD(); openItem('{kind}', '{key}')"); pg.wait_for_timeout(280)
        r = pg.evaluate("""() => { const d = document.querySelector('#drawer'), q = d.getBoundingClientRect(), bad = [];
          d.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 0 && (r.right > q.right + 1 || r.left < q.left - 1) && !e.closest('svg')) bad.push(e.tagName + '.' + (e.className || '') + ' ' + (e.textContent || '').trim().slice(0, 24)); });
          return { over: d.scrollWidth - d.clientWidth, width: q.width, bad: bad.slice(0, 6) }; }""")
        assert r["over"] <= 1 and not r["bad"] and r["width"] <= w + 1, (w, key, r)
    pg.evaluate("closeD()"); pg.wait_for_timeout(300); open_bd(pg); pg.evaluate("pinDay(null)") if False else None
    pg.evaluate("() => { bdDay = 3; setGuide(3, true); renderDay(); }"); pg.wait_for_timeout(250)
    assert not pg.evaluate(CHECK), (w, pg.evaluate(CHECK))


# ------------------------------------------------------------------ logic: the status words
def lists(page):
    return page.evaluate("""() => { const grab = tab => { jiraTab = tab; const doc = new DOMParser().parseFromString(jiraPop(), 'text/html'); return [...doc.querySelectorAll('.ttg')].map(g => [g.querySelector('.ttgl').textContent.trim(), [...g.querySelectorAll('.tchip')].map(c => c.textContent.trim())]); };
      const o = grab('open'), c = grab('closed'); jiraTab = 'open'; return { open: o, closed: c, ST_EPIC, ST_STORY, ST_BUG, TASK_CLOSED, STORY_CLOSED, EPIC_CLOSED }; }""")


def test_closed_lists_in_the_page_are_the_ones_the_data_script_uses(page):
    L = lists(page)
    assert set(L["TASK_CLOSED"]) == R.TASK_DONE - {"Technical Review"} and set(L["STORY_CLOSED"]) == set(R.STORY_DONE) and set(L["EPIC_CLOSED"]) == set(R.EPIC_DONE), (L["TASK_CLOSED"], R.TASK_DONE)
    assert "Technical Review" in R.TASK_DONE and "In Documentation" not in R.TASK_DONE      # Technical Review closes only with the label; In Documentation never


def test_open_and_closed_lists_never_share_or_lose_a_status(page):
    L = lists(page); o = dict(L["open"]); c = dict(L["closed"])
    for typ, full, closed in (("Epic", L["ST_EPIC"], L["EPIC_CLOSED"]), ("User story", L["ST_STORY"], L["STORY_CLOSED"])):
        assert not set(o[typ]) & set(c[typ]), typ
        assert set(o[typ]) | (set(c[typ]) & set(full)) == set(full), (typ, o[typ], c[typ], full)      # every status of the workflow is either open or closed
    sub = [k for k in o if k.startswith("Sub-task")][0]; bug = o["Bug sub-task"]; task_closed = c[[k for k in c if k.startswith("Sub-task")][0]]
    assert not set(o[sub]) & set(task_closed) and not set(bug) & set(task_closed)
    assert set(o[sub]) | (set(task_closed) & set(L["ST_STORY"])) == set(L["ST_STORY"]) and set(bug) | (set(task_closed) & set(L["ST_BUG"])) == set(L["ST_BUG"])
    assert "Technical Review" in o[sub] and "In Documentation" in o[sub] and "Technical Review" not in task_closed      # open in the list: the label decides, and the box says so


def test_every_status_in_the_data_is_one_the_info_boxes_know(page):
    L = lists(page); known = set(L["ST_EPIC"]) | set(L["ST_STORY"]) | set(L["ST_BUG"]) | set(L["TASK_CLOSED"]) | set(L["STORY_CLOSED"]) | set(L["EPIC_CLOSED"])
    seen = page.evaluate("() => { const s = new Set(); D.epics.forEach(e => e.s && s.add(e.s)); D.stories.forEach(x => { x.s && s.add(x.s); x.tasks.forEach(t => t.s && s.add(t.s)); }); return [...s]; }")
    assert set(seen) <= known, set(seen) - known      # a status that no info box lists would be a stale or invented word


def test_closed_and_open_groups_in_the_day_panel_agree_with_each_ticket_status(page):
    open_bd(page); r = page.evaluate("""() => { const x = BDV.days.find(d => d.d === '2026-11-13'), cl = dayRows(x, { today: false, closed: true, open: false }), op = dayRows(x, { today: false, closed: false, open: true });
      const set = { Task: TASK_CLOSED, Story: STORY_CLOSED, Epic: EPIC_CLOSED }, doc = k => ((INFO(k) || { lb: [] }).lb).some(isDocLabel), closed = r => set[r.kind].includes(r.s) || (r.kind === 'Task' && r.s === 'Technical Review' && doc(r.key));
      return { n: [cl.length, op.length], wrongClosed: cl.filter(r => !closed(r)).map(r => r.key + ' ' + r.s), wrongOpen: op.filter(closed).map(r => r.key + ' ' + r.s) }; }""")
    assert r["n"][0] > 0 and r["n"][1] > 0 and not r["wrongClosed"] and not r["wrongOpen"], r      # nothing listed as closed is open in the map data, and the other way round


def test_status_shown_in_the_panel_and_the_day_list_is_the_status_in_the_data(page):
    open_bd(page); r = page.evaluate("""() => { const x = BDV.days.find(d => d.d === '2026-11-13'); const rows = dayRows(x, { today: true, closed: true, open: true }); const bad = [];
      const all = {}; D.epics.forEach(e => all[e.key] = e.s); D.stories.forEach(s => { all[s.key] = s.s; s.tasks.forEach(t => all[t.key] = t.s); });
      rows.forEach(r => { if (all[r.key] !== undefined && all[r.key] !== r.s) bad.push(r.key + ': ' + r.s + ' vs ' + all[r.key]); }); return { bad, n: rows.length }; }""")
    assert r["n"] > 0 and not r["bad"], r
    page.evaluate("closeD()"); page.wait_for_timeout(300); page.click("[data-tab=\"map\"]")
    for key in ("PROD-9111", "PROD-9112", "PROD-9122"):
        page.evaluate(f"closeD(); openItem('t', '{key}')"); page.wait_for_timeout(250)
        want = page.evaluate(f"T['{key}'].s"); got = page.evaluate("() => [...document.querySelectorAll('#drawer .fact')].find(f => /status/i.test(f.textContent)).querySelector('b').textContent.trim()")
        assert got == want, (key, got, want)


def test_sprint_success_box_lists_what_closes_each_kind_of_ticket(page):
    from test_info_tips import hover
    open_bd(page); t = hover(page, page.locator("#wsuccess .ibtn")); x = t.inner_text()
    L = lists(page)
    assert "Epic is closed in" in x and ", ".join(L["EPIC_CLOSED"]) in x and "User story is closed in" in x and ", ".join(L["STORY_CLOSED"]) in x
    assert "Sub-task is closed in" in x and ", ".join(L["TASK_CLOSED"]) in x
    assert "Technical Review" in x and "documentation-task" in x and "stays open" in x      # only a sub-task in Technical Review with the label counts as closed
