"""Alignment guard: every (i) button sits on its label's line, cards in a row are the same size, nothing runs off the screen or scrolls sideways.
These run on every page, at phone, tablet and desktop widths, in light and dark. They exist because misaligned (i) buttons and cards are easy to miss by eye."""
import json
import pytest
from test_burndown_math import SCEN

pytestmark = pytest.mark.guard
TABS = ["map", "cap", "bd", "leave", "log", "how"]
WIDTHS = [360, 390, 430, 768, 1024, 1280, 1440]

JS_IBTN = """() => [...document.querySelectorAll('.ibtn')].filter(b => b.offsetParent !== null && b.getBoundingClientRect().width > 0 && !b.classList.contains('ci') && !b.closest('[hidden]') && (!b.checkVisibility || b.checkVisibility())).map(b => {
  const r = b.getBoundingClientRect(); let prev = b.previousSibling, rect = null;
  while (prev && !rect) {
    if (prev.nodeType === 3 && prev.textContent.trim()) { const g = document.createRange(); g.selectNodeContents(prev); const rs = g.getClientRects(); rect = rs[rs.length - 1]; }
    else if (prev.nodeType === 1 && prev.getBoundingClientRect().height > 0 && !prev.classList.contains('ibtn')) { const rs = prev.getClientRects(); rect = rs[rs.length - 1]; }
    prev = prev.previousSibling;
  }
  const p = b.parentElement;
  return { where: (p.className || p.tagName) + ' | ' + (p.innerText || '').replace(/\\s+/g, ' ').slice(0, 34), w: r.width, h: r.height,
    dy: rect ? Math.abs((r.top + r.height / 2) - (rect.top + rect.height / 2)) : null, gap: rect ? r.left - rect.right : null, spread: !!b.closest('.nh') };
})"""

JS_OVERFLOW = """() => { const vw = document.documentElement.clientWidth, out = [];
  document.querySelectorAll('body *').forEach(e => { if (e.closest('[hidden]') || e.closest('svg') || e.closest('#gtip') || e.closest('#stack') || e.closest('.tabs')) return; const r = e.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.right > vw + 1 || r.left < -1) && getComputedStyle(e).position !== 'fixed') out.push((e.id || e.className || e.tagName).toString().slice(0, 40) + ' ' + Math.round(r.left) + '..' + Math.round(r.right)); });
  const scrollers = [...document.querySelectorAll('#v-map,#v-cap,#v-bd,#v-leave,#v-log,#v-how')].flatMap(v => [...v.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowX) && !e.closest('svg')).map(e => 'scrolls sideways: ' + (e.className || e.tagName)));
  return { page: document.documentElement.scrollWidth - innerWidth, out: out.slice(0, 6), scrollers: scrollers.slice(0, 6) }; }"""


def open_all(ctx_factory, mock, width, scheme="light", leave=True):
    pg = ctx_factory(width=width, height=900 if width > 700 else 844, scheme=scheme, touch=width < 700)
    if leave: pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": SCEN["leave"]["leave"]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#tabs"); pg.wait_for_function("D.stories.length > 0"); return pg


def views(pg):
    for t in TABS:
        pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(120)
        if t == "how": pg.evaluate("document.querySelectorAll('.acc details').forEach(d => d.open = true)")
        if t == "bd":
            for v in ("overall", "person"):
                pg.click(f'[data-bdview="{v}"]'); pg.wait_for_timeout(120); yield f"bd-{v}"
        else: yield t


@pytest.mark.parametrize("width", WIDTHS)
def test_every_info_button_sits_on_its_label_line_and_has_one_size(ctx_factory, mock, width):
    pg = open_all(ctx_factory, mock, width); bad = []
    for name in views(pg):
        for b in pg.evaluate(JS_IBTN):
            if abs(b["w"] - 16) > 1 or abs(b["h"] - 16) > 1: bad.append((width, name, "size", b))
            elif b["dy"] is not None and b["dy"] > 3: bad.append((width, name, "not on the label line", b))
            elif b["gap"] is not None and not b["spread"] and not (-1 <= b["gap"] <= 16): bad.append((width, name, "too far from its label", b))
    assert not bad, bad[:4]


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_nothing_runs_off_the_screen_or_scrolls_sideways(ctx_factory, mock, width, scheme):
    if scheme == "dark" and width not in (390, 1440): pytest.skip("dark checked at phone and desktop")
    pg = open_all(ctx_factory, mock, width, scheme); bad = []
    for name in views(pg):
        o = pg.evaluate(JS_OVERFLOW)
        if o["page"] > 1 or o["out"] or o["scrollers"]: bad.append((width, scheme, name, o))
    assert not bad, bad[:3]


@pytest.mark.parametrize("width", [1280, 1440])
def test_table_header_text_ends_where_the_numbers_end(ctx_factory, mock, width):
    pg = open_all(ctx_factory, mock, width); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog"); bad = []
    for t in ("#tplan", "#tlog"):
        res = pg.evaluate("""t => { const th = [...document.querySelectorAll(t + ' thead th')], row = document.querySelector(t + ' tbody tr'); return th.slice(1).map((h, i) => {
          const g = document.createRange(); g.selectNodeContents([...h.childNodes].find(n => n.nodeType === 3 && n.textContent.trim())); const hr = g.getBoundingClientRect();
          const c = row.cells[i + 1], v = c.querySelector('.v') || c; const g2 = document.createRange(); g2.selectNodeContents(v); const vr = g2.getBoundingClientRect(); return [h.innerText.trim(), Math.round(hr.right - vr.right)]; }); }""", t)
        bad += [(t, n, d) for n, d in res if abs(d) > 2 and not n.upper().startswith(("VERDICT", "FLAG"))]
    assert not bad, bad


@pytest.mark.parametrize("width", [390, 768, 1024, 1440])
def test_table_header_cells_are_one_line_and_equal_height(ctx_factory, mock, width):
    if width <= 1120: pytest.skip("up to 1120px the tables become cards")
    pg = open_all(ctx_factory, mock, width); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    for t in ("#tplan", "#tlog"):
        h = pg.evaluate("t => [...document.querySelectorAll(t + ' thead th')].map(e => Math.round(e.getBoundingClientRect().height))", t); assert len(set(h)) == 1, (t, h)
        tops = pg.evaluate("t => [...document.querySelectorAll(t + ' thead th')].map(e => Math.round(e.getBoundingClientRect().top))", t); assert len(set(tops)) == 1


@pytest.mark.parametrize("width", [390, 1024, 1440])
def test_how_it_works_cards_are_equal_and_spaced(ctx_factory, mock, width):
    pg = open_all(ctx_factory, mock, width); pg.click('[data-tab="how"]'); pg.wait_for_selector(".startsec")
    h = pg.locator(".startsec h3").bounding_box(); cards = pg.locator(".startsec .chipc"); boxes = [cards.nth(i).bounding_box() for i in range(3)]
    assert boxes[0]["y"] - (h["y"] + h["height"]) >= 12, "space between the heading and the cards"
    if width > 900:
        assert len({round(b["y"]) for b in boxes}) == 1 and len({round(b["width"]) for b in boxes}) == 1 and len({round(b["height"]) for b in boxes}) == 1, boxes
    else:
        assert len({round(b["x"]) for b in boxes}) == 1 and len({round(b["width"]) for b in boxes}) == 1, boxes
    for i in range(3):
        c = cards.nth(i); t = c.locator("b").first.bounding_box(); ib = c.locator(".ibtn").bounding_box(); assert abs((t["y"] + t["height"] / 2) - (ib["y"] + ib["height"] / 2)) <= 3


def test_tooltips_never_cover_their_button(ctx_factory, mock):
    pg = open_all(ctx_factory, mock, 1440); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog"); pg.locator("#tlog").scroll_into_view_if_needed(); pg.wait_for_timeout(400); bad = []
    for i in range(pg.locator("#v-bd .ibtn:visible").count()):
        b = pg.locator("#v-bd .ibtn:visible").nth(i); b.scroll_into_view_if_needed(); pg.mouse.move(2, 2); pg.wait_for_timeout(450); bx = b.bounding_box(); pg.mouse.move(bx["x"] + 8, bx["y"] + 8); pg.wait_for_timeout(200)
        if pg.locator("#gtip").is_hidden(): bad.append((i, "no tip")); continue
        t = pg.locator("#gtip").bounding_box(); over = not (t["x"] >= bx["x"] + bx["width"] or t["x"] + t["width"] <= bx["x"] or t["y"] >= bx["y"] + bx["height"] or t["y"] + t["height"] <= bx["y"])
        if over or t["x"] < 0 or t["y"] < 0 or t["x"] + t["width"] > 1440 or t["y"] + t["height"] > 900: bad.append((i, "covers the button or leaves the screen", t, bx))
    assert not bad, bad[:3]
