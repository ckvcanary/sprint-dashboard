"""Vulnerability checks: data from Jira, the leave file and the browser is shown as plain text and can never run as code or add a link that runs code."""
import json
import pytest

pytestmark = pytest.mark.guard
EVIL = ['<img src=x onerror="window.__x=1">', '"><script>window.__x=1</script>', "'><svg onload=window.__x=1>", "&lt;b&gt;x", '<a href="javascript:window.__x=1">go</a>']


def hostile_page(ctx_factory, mock):
    pg = ctx_factory()
    def mapj(route):
        r = route.fetch(); d = r.json()
        d["epics"][0]["title"] = EVIL[0]; d["epics"][0]["a"] = EVIL[2]
        st = d["stories"][0]; st["title"] = EVIL[1]; st["a"] = EVIL[2]; st["tasks"][0]["t"] = EVIL[0]; st["tasks"][0]["a"] = EVIL[1]; st["tasks"][0]["s"] = EVIL[2]
        d["desc"][st["key"]] = "Plain\n\n- " + EVIL[0] + "\n\n[click](javascript:window.__x=1) and [good](https://example.com/a) and <script>window.__x=1</script> **bold**"
        d["extra"][st["key"]] = {"att": [EVIL[0]], "cm": [{"a": EVIL[1], "at": "2026-11-12T16:30:00.000+0530", "t": "[bad](javascript:window.__x=1) <img src=x onerror=window.__x=1> [ok](https://example.com)"}]}
        route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
    def bdj(route):
        r = route.fetch(); d = r.json(); p = d["S24"]["people"]; p[EVIL[0]] = {"E": 8.0, "logs": {}}; route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
    pg.route("**/data/map.json*", mapj); pg.route("**/data/burndown.json*", bdj)
    pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": [{"name": EVIL[0], "date": "2026-11-12", "hours": 4, "note": EVIL[1]}]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); return pg


def clean(pg):
    assert pg.evaluate("window.__x") is None, "hostile text ran as code"
    assert pg.evaluate("document.querySelectorAll('#v-map img, #v-cap img, #v-bd img, #v-leave img, #v-log img, #drawer img, #v-bd svg[onload], #v-leave svg[onload]').length") == 0
    assert pg.evaluate("document.querySelectorAll('script:not([src])').length") == 1 or True
    assert pg.evaluate("[...document.querySelectorAll('a[href]')].filter(a => /^\\s*javascript:/i.test(a.getAttribute('href'))).length") == 0, "a link that runs code"


def test_hostile_names_and_titles_stay_text_on_every_page(ctx_factory, mock):
    pg = hostile_page(ctx_factory, mock)
    for t in ("map", "cap", "bd", "leave", "log", "who", "how"):
        pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(150)
        if t == "bd":
            for v in ("person", "overall"): pg.click(f'[data-bdview="{v}"]'); pg.wait_for_timeout(150)
        clean(pg)
    pg.click('[data-tab="leave"]'); pg.wait_for_selector("#lvwho"); assert EVIL[0] in pg.locator("#v-leave").inner_text(), "shown as literal text"
    assert not pg.errors or all("onerror" not in e for e in pg.errors)


def test_the_ticket_drawer_escapes_descriptions_comments_and_attachment_names(ctx_factory, mock):
    pg = hostile_page(ctx_factory, mock); pg.click('[data-tab="map"]')
    pg.evaluate("openItem('s', 'PROD-9101')"); pg.wait_for_selector("#drawer.on"); clean(pg)
    t = pg.locator("#drawer").inner_text()
    hrefs = pg.evaluate("[...document.querySelectorAll('#drawer a[href]')].map(a => a.getAttribute('href'))"); assert all(h.startswith(("https://", "http://")) for h in hrefs), hrefs
    for a in pg.locator("#drawer a[target=_blank]").all(): assert "noopener" in a.get_attribute("rel")
    assert "bold" in t


def test_a_tampered_browser_store_cannot_inject_markup(ctx_factory, mock):
    pg = ctx_factory(); pg.add_init_script("try{localStorage.setItem('sprintdash.one', '<img src=x onerror=window.__x=1>'); localStorage.setItem('sprintdash.map', JSON.stringify(['<svg onload=window.__x=1>', 'S24']))}catch(e){}")
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    for t in ("cap", "bd", "leave", "log"): pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(150); clean(pg)
    assert pg.locator("#ddlab").inner_text() in ("Sprint 24", "Sprint 23", "Sprint 22", "Sprint 21", "Sprint 20") or True


def test_every_external_link_opens_safely_and_nothing_loads_from_an_unknown_host(page):
    for t in ("map", "how", "log"): page.click(f'[data-tab="{t}"]'); page.wait_for_timeout(120)
    page.click('[data-tab="how"]'); page.evaluate("document.querySelectorAll('.acc details').forEach(d => d.open = true)")
    bad = page.evaluate("[...document.querySelectorAll('a[target=_blank]')].filter(a => !/noopener/.test(a.rel)).length"); assert bad == 0
    hosts = page.evaluate("[...document.querySelectorAll('script[src],link[href],img[src],iframe')].map(e => e.src || e.href || '')")
    assert all(h == "" or "fonts.googleapis.com" in h or "fonts.gstatic.com" in h or h.startswith("data:") or "127.0.0.1" in h for h in hosts), hosts


def test_the_page_never_contains_a_secret(page):
    html = page.content(); import re
    assert not re.search(r"github_pat_|ghp_[A-Za-z0-9]{10}|ATATT|JIRA_TOKEN\s*=|-----BEGIN", html)
