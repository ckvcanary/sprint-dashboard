"""Guardrails: what happens when things go wrong, and what must never happen. Run before every deploy."""
import datetime as dt, json, re, time, urllib.request
import pytest
from conftest import NOW, PASSWORD, ctl, posts
import test_relay as relay

NOISE = "Failed to load resource"       # the browser's own note about a refused request, not a page error


def clean(errors): return [e for e in errors if NOISE not in e]


def load(ctx_factory, mock, route=None, **kw):
    pg = ctx_factory(**kw)
    for pat, fn in (route or {}).items(): pg.route(pat, fn)
    pg.goto(mock.url + "/index.html"); return pg


# ---------- data that cannot be loaded
def test_a_failed_data_load_shows_one_clear_message_and_recovers_after_refresh(ctx_factory, mock):
    ctl(mock, "ok", 0.8); pg = load(ctx_factory, mock, {"**/data/map.json*": lambda r: r.fulfill(status=500, body="boom")}, rf="{poll:250,max:8000,expect:4}")
    pg.wait_for_selector("#loaderr", state="visible"); t = pg.locator("#loaderr").inner_text()
    assert "Could not load the dashboard data" in t and "press Refresh or reload" in t and not pg.locator("#v-map").is_visible() and not clean(pg.errors)
    pg.click('[data-tab="bd"]'); assert pg.locator("#loaderr").is_visible()
    pg.unroute("**/data/map.json*"); pg.click("#rfbtn"); pg.locator(".tst.success").wait_for(timeout=9000)
    assert not pg.locator("#loaderr").is_visible()
    pg.click('[data-tab="map"]'); pg.wait_for_selector("#map .card")


@pytest.mark.parametrize("body", ["{not json", "", "[]", "null"])
def test_corrupt_data_never_leaves_a_blank_page(ctx_factory, mock, body):
    pg = load(ctx_factory, mock, {"**/data/map.json*": lambda r: r.fulfill(status=200, body=body)}); pg.wait_for_selector("#loaderr", state="visible"); assert not clean(pg.errors), clean(pg.errors)


def test_missing_run_history_or_burndown_data_leaves_the_other_pages_working(ctx_factory, mock):
    pg = load(ctx_factory, mock, {"**/data/runs.json*": lambda r: r.fulfill(status=404), "**/data/burndown.json*": lambda r: r.fulfill(status=404)}); pg.wait_for_selector("#map .card")
    assert not pg.locator("#loaderr").is_visible()
    pg.click('[data-tab="cap"]'); pg.wait_for_selector(".capgrid"); pg.click('[data-tab="bd"]'); assert "No time-logging data" in pg.locator("#v-bd").inner_text()
    pg.click('[data-tab="log"]'); pg.wait_for_selector(".sched3"); assert not clean(pg.errors), clean(pg.errors)


# ---------- text from Jira must never run as code
def test_hostile_text_from_jira_is_shown_as_plain_text_and_never_runs(ctx_factory, mock):
    d = mock.site / "data" / "map.json"; m = json.loads(d.read_text())
    m["stories"][0]["title"] = '<img src=x onerror="window.__xss=1">'; m["epics"][0]["title"] = '"><script>window.__xss=2</script>'
    m["stories"][0]["tasks"][0]["t"] = "<svg onload=window.__xss=6> quote\" apostrophe'"
    m["desc"]["PROD-9101"] = '<img src=x onerror=window.__xss=7>\n\n[evil](javascript:window.__xss=8) and [fine](https://example.com)'
    m["extra"]["PROD-9101"] = {"att": ["<b onmouseover=window.__xss=5>x</b>.pdf"], "cm": [{"a": "<i>Eve</i>", "at": "2026-11-12T10:00:00.000+0530", "t": "<script>window.__xss=3</script> [bad](javascript:window.__xss=4) **bold** [ok](https://example.com)"}]}
    d.write_text(json.dumps(m)); pg = load(ctx_factory, mock); pg.wait_for_selector("#map .card")
    pg.click('#map .card.story[data-s="PROD-9101"]'); pg.wait_for_selector("#drawer.on"); pg.wait_for_timeout(300)
    body = pg.locator("#drawer").inner_text()
    assert "<script>window.__xss=3</script>" in body and "<b onmouseover=window.__xss=5>" in body and "<i>Eve</i>" in body, "shown as plain text"
    assert pg.locator("#drawer a[href^='javascript' i], #map a[href^='javascript' i]").count() == 0 and pg.locator("#drawer a[href='https://example.com']").count() >= 1
    assert pg.evaluate("typeof window.__xss") == "undefined" and pg.locator("#drawer img, #drawer script, #drawer svg[onload]").count() == 0 and not clean(pg.errors)
    pg.keyboard.press("Escape"); pg.click('#map .card.epic >> nth=0'); pg.wait_for_selector("#drawer.on"); assert pg.evaluate("typeof window.__xss") == "undefined"


# ---------- many people at once
def test_twenty_people_pressing_refresh_in_the_same_second_start_one_job(page):
    r = page.evaluate(relay.HARNESS_PARALLEL, {"src": relay.SRC, "origin": relay.ALLOWED, "n": 20})
    assert r["dispatches"] == 1 and r["states"].count("started") == 1 and set(r["states"]) <= {"started", "running"}, r


def test_every_relay_answer_keeps_the_browser_allowed_to_read_it(page):
    for kw in ({"runs": [{"status": "in_progress"}]}, {"runs": [], "total": 99}, {"dispatchStatus": 500}, {"runs": [{"status": "completed", "conclusion": "success", "ago": 30}]}):
        r = relay.call(page, **kw); assert r["a"]["headers"]["Access-Control-Allow-Origin"] == relay.ALLOWED and r["a"]["code"] in (200, 202, 429, 502), r


def test_page_and_relay_agree_on_the_daily_limit():
    page = (relay.ROOT / "template.html").read_text(); js = (relay.ROOT / "api" / "refresh.js").read_text()
    assert re.search(r"LIMIT = 100, RESERVE = 5", page) and re.search(r"LIMIT = 100, RESERVE = 5", js), "the page and the relay must stop at the same point"


# ---------- the person's own computer
def test_a_computer_clock_that_runs_behind_does_not_block_refreshing(ctx_factory, mock):
    ctl(mock, "ok", 1.0); pg = ctx_factory(rf="{poll:250,max:9000,expect:4}", now=dt.datetime(2026, 11, 13, 10, 40, tzinfo=dt.timezone.utc))   # 24 minutes behind the data
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn"); pg.locator(".tst.success, .tst.error, .tst.info").first.wait_for(timeout=10000)
    assert posts(mock) == 1 and pg.locator(".tst.success").count() == 1, "the click must reach the relay, not be called 'already up to date'"


@pytest.mark.parametrize("tz", ["Asia/Kolkata", "America/New_York", "Pacific/Auckland", "Europe/London"])
def test_times_are_always_shown_in_india_time_whatever_the_computer_timezone(ctx_factory, mock, tz):
    pg = ctx_factory(tz=tz); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    assert pg.inner_text("#rfval") == "13 Nov, 4:34 PM IST"; pg.click('[data-tab="log"]'); pg.wait_for_selector(".sched3"); t = pg.locator(".sched3").inner_text()
    assert "13 Nov, 6:45 PM IST" in t and "13 Nov, 10:46 AM IST" in t


def test_blocked_browser_storage_still_lets_you_sign_in_for_the_visit(ctx_factory, mock):
    pg = ctx_factory(signed_in=False); pg.context.add_init_script("Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }})")
    pg.goto(mock.url + "/index.html"); assert pg.locator("#gate").is_visible(); pg.fill("#gpw", PASSWORD); pg.press("#gpw", "Enter"); pg.wait_for_selector("#map .card")
    pg.click("#signout"); assert pg.locator("#gate").is_visible() and not [e for e in pg.errors if "blocked" in e and "Uncaught" in e], pg.errors


def test_a_cut_network_during_refresh_gives_a_clear_toast_and_frees_the_button(ctx_factory, mock):
    pg = ctx_factory(rf="{poll:250,max:5000,expect:4}"); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.route("**/api/refresh", lambda r: r.abort())
    pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for(); assert "Could not start the refresh" in t.inner_text() and pg.is_enabled("#rfbtn") and not pg.locator("#rfprog").is_visible()
    assert pg.inner_text("#rfval") == "13 Nov, 4:34 PM IST"


def test_messages_never_pile_up_beyond_three(page):
    page.evaluate("for (let i = 0; i < 9; i++) notify({ kind: 'info', title: 'Message ' + i })"); assert page.locator(".tst").count() == 3


# ---------- accessibility basics
def test_every_control_has_a_name_and_the_page_declares_its_language(page):
    assert page.get_attribute("html", "lang") == "en"
    for tab in ("map", "cap", "bd", "log", "who", "how"):
        page.click(f'[data-tab="{tab}"]')
        if tab == "bd": page.click('[data-bdview="person"]')
        bad = page.evaluate("""() => [...document.querySelectorAll('button, input, select')].filter(e => e.offsetParent !== null).filter(e => !(e.innerText || '').trim() && !e.getAttribute('aria-label') && !e.title && !(e.labels && e.labels.length)).map(e => e.outerHTML.slice(0, 80))""")
        assert not bad, (tab, bad)


def test_refresh_and_sign_out_can_be_reached_with_the_keyboard(page):
    seen = []
    for _ in range(40):
        page.keyboard.press("Tab"); seen.append(page.evaluate("document.activeElement && document.activeElement.id"))
        if "signout" in seen and "rfbtn" in seen: break
    assert "rfbtn" in seen and "signout" in seen, seen


# ---------- size
def test_a_much_bigger_sprint_still_loads_quickly(ctx_factory, mock):
    d = mock.site / "data"; m = json.loads((d / "map.json").read_text()); bd = json.loads((d / "burndown.json").read_text()); stories, tasks = [], []
    for i in range(300):
        ts = [{"key": f"PROD-{20000 + i * 10 + j}", "t": f"Task {i}.{j}", "a": ["Nikita", "Sumit", "Aditi"][j % 3], "h": 4, "s": ["Backlog", "In Progress", "Done"][j % 3]} for j in range(6)]
        stories.append({"key": f"PROD-{19000 + i}", "title": f"Story {i}", "epic": "PROD-9001" if i % 2 else "PROD-9002", "sprint": "S24", "a": "Nikita", "sp": 3, "own": 0, "s": "In Progress", "tasks": ts})
        tasks += [{"k": t["key"], "a": t["a"], "e": 4, "d": "2026-11-12" if t["s"] == "Done" else None} for t in ts]
    m["stories"] = [s for s in m["stories"] if s["sprint"] != "S24"] + stories; bd["S24"]["tasks"] = tasks; bd["S24"]["stories"] = [{"k": s["key"], "a": "Nikita", "d": None} for s in stories]
    for n in ("Nikita", "Sumit", "Aditi"): bd["S24"]["people"][n]["E"] = 600.0
    (d / "map.json").write_text(json.dumps(m)); (d / "burndown.json").write_text(json.dumps(bd))
    pg = ctx_factory(); t0 = time.time(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); assert time.time() - t0 < 8, "map with 300 stories and 1,800 tasks"
    t0 = time.time(); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg"); assert time.time() - t0 < 4
    svg = pg.locator("#cw svg").bounding_box(); pg.mouse.click(svg["x"] + (60 + 4.5 / 11 * 924) / 1000 * svg["width"], svg["y"] + svg["height"] * .4); pg.wait_for_selector("#dayd:not([hidden])"); pg.get_by_role("tab", name="Still open").click(); assert pg.locator("#dayd tbody tr").count() > 1000
    assert not clean(pg.errors), clean(pg.errors)
