"""What an info box shows must exist on the page: a marker only where the page draws the same marker, names and numbers equal to what the code produces"""
import re, pathlib, pytest

pytestmark = pytest.mark.guard
SRC = (pathlib.Path(__file__).resolve().parent.parent / "template.html").read_text()


def all_tips(page):
    return page.evaluate("() => Object.fromEntries(Object.keys(TT).map(k => [k, ttHtml(TT[k])]))")


def test_no_info_box_has_a_dot_the_page_does_not_show(page):
    for k, h in all_tips(page).items():
        assert 'class="td' not in h and "<i class=\"td" not in h, (k, "a coloured dot in an info box needs a matching dot on the page")


def test_markers_are_real_tags_and_chips(page):
    t = all_tips(page)
    for k in ("flag", "verdict", "missing"):
        assert '<span class="tag ' in t[k], k
    assert t["slot"].count('<span class="chip ') == 5
    for k in ("type", "day", "capday", "left", "leave", "expected", "over", "ideal", "remaining", "renew", "n1", "n2", "n3", "n4", "n5", "c1", "c2", "c3", "cron", "budget"):
        assert '<span class="tag' not in t[k] and '<span class="chip' not in t[k], (k, "no marker where the page shows none")


def test_refresh_tip_dots_match_the_dot_beside_the_time(page):
    h = page.evaluate("refreshTip()"); assert h.count('class="td') == 3 and "Green" in h and "Orange" in h and "Blue, pulsing" in h
    r = page.evaluate("""() => { const out = {}; const probe = (cls) => { const host = document.querySelector('.rfcard'); const e = document.createElement('i'); e.className = cls; host.appendChild(e); const c = getComputedStyle(e).backgroundColor; e.remove(); return c; };
      out.ok = [probe('td ok'), probe('dot')]; out.old = [probe('td warn'), probe('dot old')]; out.busy = [probe('td blue'), probe('dot busy')]; return out; }""")
    for k, (legend, real) in r.items(): assert legend == real, (k, legend, real)
    assert "14 * 3600e3" in SRC and "Under 14 hours old" in h and "Older than 14 hours" in h


def test_flag_and_verdict_names_are_the_words_the_page_prints(page):
    t = all_tips(page)
    for name in re.findall(r'<span class="tag \w+">([^<]+)</span>', t["flag"]): assert f"'{name}'" in SRC.split("function person")[1] or f"st = '{name}'" in SRC, name
    for name in re.findall(r'<span class="tag \w+">([^<]+)</span>', t["verdict"]): assert f"'{name}'" in SRC, name
    assert set(re.findall(r'<span class="tag \w+">([^<]+)</span>', t["flag"])) == {"Not started", "On pace", "Behind pace", "Well behind pace"}


def test_pull_status_names_equal_the_chips_in_the_table(page):
    page.click('[data-tab="log"]'); page.wait_for_selector(".plt")
    shown = set(page.locator(".plt .chip").all_inner_texts()); legend = set(re.findall(r'<i></i>([^<]+)</span>', all_tips(page)["slot"]))
    assert {s.split(" · ")[0].strip() for s in shown} <= legend, (shown, legend)
    assert legend == {"Pulled", "Failed", "Missed", "Upcoming", "Not scheduled"}


def test_type_legend_names_the_real_issue_types(page):
    h = all_tips(page)["type"]; assert "Epic" in h and "User story" in h and "Sub-task, Story sub-task, Bug sub-task, New Feature sub-task" in h


def test_times_and_numbers_in_info_boxes_equal_the_code(page):
    t = all_tips(page); assert "10:50 AM and 6:50 PM IST" in t["c1"] and "10:50 AM and 6:50 PM IST" in t["c3"] and "10:55" not in "".join(t.values())
    assert "100 pulls in 24 hours" in t["budget"] and "95" in t["budget"] and "const LIMIT = 100, RESERVE = 5" in SRC
    assert "Retries 30 and 60 minutes later" in t["c1"]
    assert "(sprint day) − (planning days)" in t["capday"] and "(6) − (2) = 4 of 8" in t["capday"]


def test_every_tip_example_is_arithmetically_true(page):
    bad = []
    for k, h in all_tips(page).items():
        for m in re.finditer(r"\(([\d.]+) ?h?\) ([−+×/]) \(([\d.]+) ?h?\) = ([\d.]+)", re.sub(r"<[^>]+>", " ", h).replace("&#39;", "'")):
            a, op, b, r = float(m[1]), m[2], float(m[3]), float(m[4]); v = {"−": a - b, "+": a + b, "×": a * b, "/": a / b if b else 0}[op]
            if abs(max(v, 0) - r) > .051: bad.append((k, m[0]))
    assert not bad, bad


def test_every_plain_row_is_a_grey_bullet_and_colour_is_only_a_real_tag_chip_or_dot(page):
    t = all_tips(page)
    for k, h in t.items():
        rows = re.findall(r'<div class="ttr[^"]*"><span class="ttn">(.*?)</span>', h)
        for r in rows:
            assert ('<i class="bl"></i>' in r) or ('<span class="tag ' in r) or ('<span class="chip ' in r) or ('class="td ' in r), (k, r)
    assert page.evaluate("[...document.querySelectorAll('.ttn')].length >= 0")
    page.evaluate("document.body.insertAdjacentHTML('beforeend', '<div id=pb class=tt>' + ttHtml(TT.day) + '</div>')")
    cols = page.evaluate("[...document.querySelectorAll('#pb .bl')].map(e => getComputedStyle(e).backgroundColor)")
    assert cols and len(set(cols)) == 1, "all plain bullets share one neutral colour"


def test_without_data_the_box_shows_an_example_and_with_data_a_calculation(page):
    page.click('[data-tab="bd"]'); page.wait_for_timeout(400)
    live = page.evaluate("ttHtml(TT.remaining, 'remaining')"); assert ">Calculation<" in live and ">Example<" not in live
    page.evaluate("CALC = null"); ex = page.evaluate("ttHtml(TT.remaining, 'remaining')"); assert ">Example<" in ex and ">Calculation<" not in ex and "(6 h) − (2 h) = 4 h" in ex


def test_pace_target_divides_by_capacity_days_after_leave(ctx_factory, mock):
    """half a day of leave: 8 working days become 7.5 capacity days, so the daily pace target is E / 7.5, and the formula says so"""
    import json
    pg = ctx_factory(width=1440, height=900)
    pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": [{"name": "Nikita", "date": "2026-11-12", "hours": 4}]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#bdwho"); pg.select_option("#bdwho", "Nikita"); pg.wait_for_timeout(400)
    r = pg.evaluate("(() => { const r = CALC.rs.find(x => x.name === 'Nikita'); return {E: r.E, capDays: r.capDays, daily: r.dailyT, passed: r.daysPassed, exp: r.exp, leave: r.leaveH}; })()")
    assert abs(r["capDays"] - 7.5) < 1e-6 and abs(r["daily"] - r["E"] / 7.5) < 1e-6 and r["leave"] == 4
    # an independent model: capacity hours passed over capacity hours in the sprint, with the leave hours taken out of the day they fall on
    days = ["2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]; avail = [4 if d == "2026-11-12" else 8 for d in days]
    el = pg.evaluate("(() => { const s = BD.S24; return elapsed(workDays(s.win), asOfIST().slice(0, 10) + 'T' + asOfIST().slice(11, 16)); })()")
    passed_h, left = 0, el
    for a in avail:
        t = min(8, left); passed_h += a * t / 8; left -= t
    assert abs(r["exp"] - r["E"] * passed_h / sum(avail)) < .01, (r, passed_h, sum(avail))
    b = pg.locator("th:has-text('Pace target by now') .ibtn").first; b.scroll_into_view_if_needed(); pg.wait_for_timeout(300); b.hover(); pg.wait_for_selector("#gtip:not([hidden])"); x = pg.inner_text("#gtip")
    assert "7.5 = 8 − 0.5" in x and "2.4 h" in x and "calculation" in x.lower()
