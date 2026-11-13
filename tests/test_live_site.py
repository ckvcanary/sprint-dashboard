"""The same checks, run against the real Vercel link with real data. Read-only: signs in, looks, hovers, signs out.
Run:  LIVE_URL=https://sprint-dashboard-umber.vercel.app DASH_PASSWORD='<team password>' python -m pytest tests/test_live_site.py
Add LIVE_REFRESH=1 to also press Refresh once (it uses one of the 100 daily refreshes)."""
import json, os, re, urllib.request
import pytest
from playwright.sync_api import sync_playwright

URL = os.environ.get("LIVE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set LIVE_URL to run against the live site")
from conftest import PASSWORD, SESSION
TABS = ["map", "cap", "bd", "log", "who", "how"]


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True); yield b; b.close()


def fresh(pw, width=1440, scheme="light", signed_in=True):
    c = pw.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    if signed_in: c.add_init_script(f"localStorage.setItem('sd_auth', '{SESSION}')")
    pg = c.new_page(); pg.set_default_timeout(20000); pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e))); pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    pg.goto(URL + "/"); return pg


def data(name): return json.load(urllib.request.urlopen(f"{URL}/data/{name}.json?v={os.getpid()}", timeout=30))


def test_the_live_link_asks_for_the_password_then_opens_the_dashboard(pw):
    pg = fresh(pw, signed_in=False); assert pg.locator("#gate").is_visible() and not pg.locator(".wrap").is_visible()
    pg.fill("#gpw", "definitely-wrong"); pg.click("#gsub"); pg.locator(".tst.error").wait_for(); assert "Incorrect password" in pg.locator(".tst.error").inner_text()
    pg.fill("#gpw", PASSWORD); pg.press("#gpw", "Enter"); pg.wait_for_selector("#map .card"); assert not pg.locator("#gate").is_visible()
    pg.reload(); pg.wait_for_selector("#map .card"); pg.click("#signout"); assert pg.locator("#gate").is_visible(); pg.reload(); assert pg.locator("#gate").is_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_page_renders_with_real_data_and_no_errors(pw, scheme):
    pg = fresh(pw, scheme=scheme); pg.wait_for_selector("#map .card")
    assert pg.locator("#map .card.story").count() >= 10 and pg.locator("#map .card.epic").count() >= 5
    for t in TABS: pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(200)
    pg.click('[data-tab="map"]'); pg.click("#map .card.story >> nth=3"); pg.wait_for_selector("#drawer.on"); assert not pg.errors, pg.errors


def test_cards_show_points_only_and_epics_say_total(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card")
    for c in pg.locator("#map .card").all(): assert not re.search(r"\b\d+(\.\d+)?\s*h\b", c.inner_text()), c.inner_text()
    assert pg.locator("#map .card.epic .pill.n", has_text="total").count() >= 3


def test_the_data_on_the_live_site_is_consistent_and_complete(pw):
    m, meta, bd = data("map"), data("meta"), data("burndown")
    assert m.get("asOf") == meta["refreshedAt"], "map and meta must carry the same pull stamp (refresh once if this is the first deploy)"
    assert "extra" in m and isinstance(m["extra"], dict), "comments and attachment names must be present (refresh once after the first deploy)"
    s24 = bd["S24"]; assert s24["start"] < s24["end"] and len(s24["tasks"]) > 50 and "stories" in s24 and "epics" in s24 and s24["win"][0] >= s24["start"]
    assert sum(t["e"] for t in s24["tasks"]) > 100


def test_burndown_overall_and_per_person_with_hover_and_day_panel(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card"); pg.click('[data-tab="bd"]'); pg.wait_for_selector(".term")
    t = pg.locator(".term").inner_text(); assert "of 10" in t and "Whole team" in pg.locator(".capb").inner_text()
    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg"); svg = pg.locator("#cw svg").bounding_box(); x = svg["x"] + (60 + 4.5 / 11 * 924) / 1000 * svg["width"]
    pg.mouse.move(x, svg["y"] + svg["height"] * .4); pg.wait_for_selector("#tip:not([hidden])"); tip = pg.locator("#tip").inner_text()
    assert "Epics" in tip and "Ideal pace" in tip and "data as of" in tip and pg.locator("#tip .mt tbody tr").count() == 5 and pg.locator("#tip .tc .tchip").count() == 8
    pg.mouse.click(x, svg["y"] + svg["height"] * .4); pg.wait_for_selector("#dayd:not([hidden])"); pg.get_by_role("tab", name="Still open").click(); assert pg.locator("#dayd tbody tr").count() > 10
    pg.select_option("#bdwho", index=1); assert "Used" in pg.locator(".pcap").inner_text()


def test_tooltips_and_how_it_works_are_plain_and_complete(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card"); pg.click('[data-tab="how"]'); pg.wait_for_selector(".hw"); t = pg.locator(".hw").inner_text()
    assert "This dashboard shows what is in Jira." in t and "nothing runs on Claude" in t and "12 Nov 2027" in pg.locator(".hw").inner_html()
    pg.locator(".hw [data-tip]:visible").nth(3).hover(); tip = pg.locator("#gtip").inner_text(); assert "A few seconds of wait" in tip
    pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg"); pg.locator("th:has-text('Flag') .ibtn").scroll_into_view_if_needed(); pg.mouse.move(2, 2); pg.wait_for_timeout(150)
    pg.locator("th:has-text('Flag') .ibtn").hover(); assert "On track" in pg.locator("#gtip").inner_text() and "Cannot finish in time" in pg.locator("#gtip").inner_text()


def test_pull_log_lists_the_weekday_schedule_by_sprint(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card"); pg.click('[data-tab="log"]'); pg.wait_for_selector(".plt"); days = pg.locator(".plt").first.locator("tbody tr td:nth-child(1)").all_inner_texts()
    assert "Sat" not in days and "Sun" not in days and len(days) >= 10 and "Twice every weekday" in pg.locator(".sched3").inner_text()


def test_a_ticket_drawer_shows_hours_files_and_comments(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card"); pg.click("#map .card.story >> nth=0"); pg.wait_for_selector("#drawer.on"); d = pg.locator("#drawer"); t = d.inner_text().lower()
    assert "original estimate" in t and "attachments (" in t and "comments (" in t and d.locator(".fact.hi").count() >= 1


def test_phone_width_has_no_sideways_scroll_on_any_page(pw):
    pg = fresh(pw, width=390); pg.wait_for_selector("#v-map .card >> visible=true")
    for t in TABS: pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(200); assert pg.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1, t


def test_the_relay_rules_hold_on_the_live_site():
    def call(method, origin):
        r = urllib.request.Request(URL + "/api/refresh", method=method, data=b"" if method == "POST" else None, headers={"Origin": origin} if origin else {})
        try: return urllib.request.urlopen(r, timeout=30).status
        except urllib.error.HTTPError as e: return e.code
    assert call("POST", "https://evil.example") == 403 and call("GET", URL) == 403 and call("POST", None) == 403


@pytest.mark.skipif(not os.environ.get("LIVE_REFRESH"), reason="set LIVE_REFRESH=1 to press Refresh once on the live site")
def test_pressing_refresh_on_the_live_site_shows_a_verified_toast_and_new_data(pw):
    pg = fresh(pw); pg.wait_for_selector("#map .card"); before = pg.inner_text("#rfval")
    age = pg.evaluate("(Date.now() - Date.parse(META.refreshedAt)) / 1000")
    if age < 170: pg.wait_for_timeout(int((170 - age) * 1000))   # the relay counts 2 minutes from when the last refresh finished
    pg.click("#rfbtn"); pg.wait_for_selector("#rfprog", state="visible"); t = pg.locator(".tst.success, .tst.error, .tst.info"); t.first.wait_for(timeout=240000)
    msg = t.first.inner_text().replace("\n", " | "); assert "tst success" in t.first.get_attribute("class") and "Data refreshed" in msg and pg.inner_text("#rfval") != before and not pg.locator("#rfprog").is_visible(), msg
