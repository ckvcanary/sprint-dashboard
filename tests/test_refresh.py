"""Refresh button: progress, verification and every outcome"""
import re, time
from conftest import ctl, posts

QUICK = "{poll: 250, max: 6000, expect: 5}"


def start(ctx_factory, mock, mode="ok", delay=1.5, rf=QUICK, now=None):
    ctl(mock, mode, delay); pg = ctx_factory(rf=rf) if now is None else ctx_factory(rf=rf, now=now)
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); return pg


def test_success_shows_progress_then_one_verified_toast(ctx_factory, mock):
    pg = start(ctx_factory, mock); pg.click("#rfbtn"); assert pg.is_disabled("#rfbtn")
    pg.wait_for_selector("#rfprog", state="visible"); assert re.fullmatch(r"\d+ s left", pg.inner_text("#rfpt"))
    assert pg.locator(".tst.success").count() == 0, "no success before the data is checked"
    t = pg.locator(".tst.success"); t.wait_for(timeout=8000)
    txt = t.inner_text(); assert "Pulled from Jira" in txt and "1 ticket updated" in txt and "1,077 tickets read" in txt and "other" not in txt.lower()      # counts found by comparing the data before and after the pull
    assert not pg.locator("#rfprog").is_visible() and pg.is_enabled("#rfbtn")
    assert pg.inner_text("#rfval") == "13 Nov, 4:42 PM IST" and not pg.errors


def test_a_click_always_starts_a_pull_even_when_the_data_is_seconds_old(ctx_factory, mock):
    import json
    ctl(mock, "ok"); d = mock.site / "data"; m = json.loads((d / "meta.json").read_text()); mp = json.loads((d / "map.json").read_text())
    now = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"); m["refreshedAt"] = mp["asOf"] = now      # the data on screen is a few seconds old
    (d / "meta.json").write_text(json.dumps(m)); (d / "map.json").write_text(json.dumps(mp))
    pg = ctx_factory(rf=QUICK); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn")
    pg.wait_for_function("window.__sent === undefined || true"); pg.locator(".tst").first.wait_for(timeout=8000); assert posts(mock) == 1      # no 30 second or 2 minute wait


def test_pull_with_nothing_new_in_jira_says_so_by_comparing_before_and_after(ctx_factory, mock):
    pg = start(ctx_factory, mock, "nochange"); pg.click("#rfbtn"); t = pg.locator(".tst.info"); t.wait_for(timeout=8000)
    x = t.inner_text(); assert "Pulled from Jira" in x and "No tickets updated" in x and "1,077 tickets read" in x and pg.locator(".tst.success").count() == 0
    assert pg.inner_text("#rfval") == "13 Nov, 4:42 PM IST"      # the page still shows the new pull time


def test_updated_toast_needs_the_pull_to_be_in_the_run_list(ctx_factory, mock):
    import json
    pg = start(ctx_factory, mock); pg.evaluate("window.__keep = null")
    ok = pg.evaluate("""() => { const m = { refreshedAt: '2026-11-13T11:12:00Z' }; return [verified({asOf: m.refreshedAt, stories: [1]}, {S: {win: [1], asOf: m.refreshedAt}}, m, 0, []), verified({asOf: m.refreshedAt, stories: [1]}, {S: {win: [1], asOf: m.refreshedAt}}, m, 0, [{at: m.refreshedAt, ok: true}]), verified({asOf: m.refreshedAt, stories: [1]}, {S: {win: [1], asOf: m.refreshedAt}}, m, 0, [{at: m.refreshedAt, ok: false}])]; }""")
    assert ok == [False, True, False], ok      # no run record, or a failed one, is never "updated"


def test_before_after_comparison_counts_tickets(page):
    r = page.evaluate("""() => { const a = snapOf(D, BD); const D2 = JSON.parse(JSON.stringify(D));
      D2.info['PROD-9111'].lg += 3; D2.stories[0].tasks[1].s = 'Done'; D2.stories[0].tasks[2].a = 'Sumit';
      const one = JSON.parse(JSON.stringify(D)); one.info['PROD-9111'].lg += 1;
      return { same: diffSnap(a, snapOf(D, BD)), three: diffSnap(a, snapOf(D2, BD)), one: diffSnap(a, snapOf(one, BD)), t3: ticketsText(3), t1: ticketsText(1), t0: ticketsText(0), read: readText({ issues: 1041 }) }; }""")
    assert r["same"] == {"updated": 0, "same": True} and r["three"]["updated"] == 3 and r["three"]["same"] is False and r["one"]["updated"] == 1      # logged time, a status and an owner each count their own ticket
    assert r["t3"] == "3 tickets updated" and r["t1"] == "1 ticket updated" and r["t0"] == "No tickets updated" and r["read"] == "1,041 tickets read"      # always in tickets, never "other details"


def test_running_refresh_is_joined_and_still_verified(ctx_factory, mock):
    pg = start(ctx_factory, mock, "running"); pg.click("#rfbtn")
    pg.wait_for_function("document.querySelector('#rfps').textContent.includes('Another refresh is already running')"); pg.locator(".tst.success").wait_for(timeout=8000)


def test_failed_run_is_reported_not_hidden(ctx_factory, mock):
    pg = start(ctx_factory, mock, "fail"); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for(timeout=8000)
    assert "Refresh failed" in t.inner_text() and "Jira answered 401" in t.inner_text() and "Still showing data from 13 Nov, 4:34 PM IST" in t.inner_text()
    assert pg.inner_text("#rfval") == "13 Nov, 4:34 PM IST" and pg.locator(".tst.success").count() == 0


def test_no_new_data_is_never_called_an_update(ctx_factory, mock):
    pg = start(ctx_factory, mock, "noop"); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for(timeout=12000)
    assert "No new data yet" in t.inner_text() and pg.locator(".tst.success").count() == 0 and pg.inner_text("#rfval") == "13 Nov, 4:34 PM IST"


def test_files_from_different_pulls_are_not_accepted(ctx_factory, mock):
    pg = start(ctx_factory, mock, "mismatch"); pg.click("#rfbtn"); pg.locator(".tst.error").wait_for(timeout=12000)
    assert pg.locator(".tst.success").count() == 0 and pg.inner_text("#rfval") == "13 Nov, 4:34 PM IST"


def test_relay_errors_are_explained(ctx_factory, mock):
    for mode, word in (("error502", "502"), ("forbidden", "403")):
        pg = start(ctx_factory, mock, mode); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for()
        assert "Could not start the refresh" in t.inner_text() and word in t.inner_text() and pg.is_enabled("#rfbtn") and not pg.locator("#rfprog").is_visible()


def test_double_click_sends_one_request(ctx_factory, mock):
    pg = start(ctx_factory, mock); pg.click("#rfbtn"); pg.click("#rfbtn", force=True, timeout=2000) if False else None
    pg.evaluate("document.querySelector('#rfbtn').click(); document.querySelector('#rfbtn').click()"); pg.locator(".tst.success").wait_for(timeout=8000); assert posts(mock) == 1


def test_newer_data_already_on_server_is_shown_honestly(ctx_factory, mock):
    pg = start(ctx_factory, mock, "noop"); mock_post = __import__("urllib.request").request; mock_post.urlopen(mock_post.Request(mock.url + "/__newer", method="POST", data=b""))
    pg.click("#rfbtn"); t = pg.locator(".tst.info"); t.wait_for(timeout=12000)
    assert "Showing the latest data" in t.inner_text() or "already up to date" in t.inner_text(); assert pg.inner_text("#rfval") == "13 Nov, 4:42 PM IST"


def test_toast_sits_on_the_right_edge_of_the_screen_and_can_be_dismissed(ctx_factory, mock):
    pg = start(ctx_factory, mock, "fail"); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for(timeout=8000)
    b = t.bounding_box(); rf = pg.locator(".rfcard").bounding_box(); vp = pg.viewport_size
    assert vp["width"] - (b["x"] + b["width"]) <= 28 and vp["height"] - (b["y"] + b["height"]) <= 28, ("on the right edge, at the bottom", b, vp)
    assert not (b["x"] < rf["x"] + rf["width"] and b["x"] + b["width"] > rf["x"] and b["y"] < rf["y"] + rf["height"] and b["y"] + b["height"] > rf["y"]), "never on the Last refreshed card"
    t.locator(".cl2").click(); pg.wait_for_selector(".tst", state="detached")


def test_toasts_disappear_on_their_own(ctx_factory, mock):
    pg = start(ctx_factory, mock); pg.click("#rfbtn"); pg.locator(".tst.success").wait_for(timeout=8000)
    pg.wait_for_selector(".tst", state="detached", timeout=9000)


def test_progress_card_is_hidden_before_any_click(page):
    assert not page.locator("#rfprog").is_visible()


def overlap(a, b): return not (a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"] or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])


def test_progress_and_toast_never_overlap_the_header_or_push_the_page(ctx_factory, mock):
    pg = start(ctx_factory, mock, "ok", delay=2.5); h0 = pg.evaluate("document.documentElement.scrollHeight"); top0 = pg.locator("#v-map .colh").first.bounding_box()["y"]
    pg.click("#rfbtn"); pg.wait_for_selector("#rfprog", state="visible")
    rf, pr = pg.locator(".rfcard").bounding_box(), pg.locator("#rfprog").bounding_box()
    assert not overlap(rf, pr) and pr["y"] >= rf["y"] + rf["height"]
    assert pg.evaluate("document.documentElement.scrollHeight") == h0 and pg.locator("#v-map .colh").first.bounding_box()["y"] == top0, "the page must not move"
    t = pg.locator(".tst.success"); t.wait_for(timeout=9000); tb = t.bounding_box(); assert not overlap(rf, tb)
    assert pg.locator("#v-map .colh").first.bounding_box()["y"] == top0


def fill_runs(mock, n, minutes_ago=30):
    import json
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    import datetime as dt, conftest
    for i in range(n): runs.append({"at": (conftest.NOW - dt.timedelta(hours=1, minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "trigger": "manual", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": "tester"})
    d.write_text(json.dumps(runs))


def test_at_the_daily_limit_the_click_is_stopped_with_a_clear_toast(ctx_factory, mock):
    ctl(mock, "ok"); fill_runs(mock, 94)    # 3 earlier runs in the last 24 h + 94 = 97
    pg = ctx_factory(rf=QUICK); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn")
    t = pg.locator(".tst.error"); t.wait_for(); x = t.inner_text()
    assert "Daily refresh limit reached" in x and "of 100 refreshes were used in the last 24 hours" in x and "free Vercel plan" in x and "5 are kept for the scheduled pulls" in x
    assert "You can refresh again after" in x and "ckvcanary.github.io/sprint-dashboard" in x and posts(mock) == 0 and pg.is_enabled("#rfbtn")


def test_close_to_the_limit_warns_but_still_refreshes(ctx_factory, mock):
    ctl(mock, "ok", 1.0); fill_runs(mock, 85)    # 88 in the last 24 h
    pg = ctx_factory(rf=QUICK); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn")
    w = pg.locator(".tst.info"); w.wait_for(); assert "Close to the daily refresh limit" in w.inner_text() and "88 of 100" in w.inner_text()
    pg.locator(".tst.success").wait_for(timeout=9000)


def test_relay_reporting_the_limit_shows_the_same_toast(ctx_factory, mock):
    pg = start(ctx_factory, mock, "limit"); pg.click("#rfbtn"); t = pg.locator(".tst.error"); t.wait_for()
    assert "Daily refresh limit reached" in t.inner_text() and "96 of 100" in t.inner_text() and not pg.locator(".tst.success").count()


def test_refresh_card_info_shows_the_limit_and_usage_on_hover(page):
    page.hover(".rfcard .ibtn"); tip = page.locator("#gtip"); tip.wait_for()
    t = tip.inner_text(); assert "100 pulls in 24 hours" in t and "3 of 100" in t and "Every click starts a pull" in t and "whole team" in t
    assert tip.locator(".tth").inner_text() == "Refresh limit" and tip.locator(".ttr").count() == 6 and all(w in t for w in ("Green", "Orange", "Blue, pulsing"))
    page.mouse.move(5, 5); tip.wait_for(state="hidden")


# ---------- "Data refreshed" must be backed by a check (19 Nov 2026)
def test_no_success_toast_when_a_data_file_is_still_the_old_copy(ctx_factory, mock):
    pg = start(ctx_factory, mock, "stale_bd"); before = pg.inner_text("#rfval"); pg.click("#rfbtn")
    pg.locator(".tst.error, .tst.info, .tst.success").first.wait_for(timeout=12000)
    assert pg.locator(".tst.success").count() == 0, "burndown.json still carried the old stamp, so nothing may be called refreshed"
    assert pg.inner_text("#rfval") == before and "No new data yet" in pg.locator(".tst").first.inner_text()


def test_no_success_toast_when_the_pull_started_before_the_click(ctx_factory, mock):
    pg = start(ctx_factory, mock, "since_late"); before = pg.inner_text("#rfval"); pg.click("#rfbtn")
    pg.locator(".tst.error, .tst.info, .tst.success").first.wait_for(timeout=12000)
    assert pg.locator(".tst.success").count() == 0, "a pull that began before the click may have missed a new time log"
    assert "began before your click" in pg.locator(".tst").first.inner_text()


def test_success_toast_when_the_pull_started_after_the_click(ctx_factory, mock):
    pg = start(ctx_factory, mock, "since_ok"); pg.click("#rfbtn"); t = pg.locator(".tst.success"); t.wait_for(timeout=8000)
    assert pg.inner_text("#rfval") == "13 Nov, 4:42 PM IST" and "Pulled from Jira" in t.inner_text()


def test_shown_stamp_equals_the_stamp_in_all_three_files_when_success_is_announced(ctx_factory, mock):
    pg = start(ctx_factory, mock); pg.click("#rfbtn"); pg.locator(".tst.success").wait_for(timeout=8000)
    got = pg.evaluate("() => ({meta: META.refreshedAt, map: D.asOf, bd: Object.values(BD).filter(v => v && v.win).map(v => v.asOf)})")
    assert got["meta"] == got["map"] and set(got["bd"]) == {got["meta"]}, got
