"""Burndown maths: every number on the page is compared with an independent model of the rules, in different situations
(a developer logs more or less than the estimate, leave, a sprint that is over, a sprint that has not started).
The model below is written separately from the page code on purpose: if the two ever disagree, a number on the page is wrong."""
import json, re
import pytest

pytestmark = pytest.mark.math

DH, CAP = 8, 64
WD = ["2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]   # the 8 working days of the fixture sprint
BASE_ASOF = "2026-11-13T11:04:00Z"      # Fri 13 Nov, 4:34 PM IST (the fixture's pull time)


def people(**kw):
    """name -> {E, logs, burn}: burn is what reduces the remaining estimate (hours logged on a task, capped at that task's estimate)"""
    out = {}
    for n, (E, logs, burn) in kw.items(): out[n] = {"E": float(E), "logs": logs, "burn": burn}
    return out


BASE = people(Nikita=(18, {"2026-11-11": 4, "2026-11-12": 6}, {"2026-11-11": 4, "2026-11-12": 6}),
              Sumit=(16, {"2026-11-11": 8, "2026-11-12": 8}, {"2026-11-11": 8, "2026-11-12": 8}),
              Aditi=(16, {"2026-11-11": 5}, {"2026-11-11": 5}))
SCEN = {
    "baseline": dict(people=BASE),
    "overtime": dict(people=people(Nikita=(18, {"2026-11-11": 10, "2026-11-12": 10, "2026-11-13": 10}, {"2026-11-11": 6, "2026-11-12": 6, "2026-11-13": 6}),   # 30 h logged on 18 h of tasks
                                   Sumit=(40, {"2026-11-11": 8, "2026-11-12": 8}, {"2026-11-11": 8, "2026-11-12": 8}),
                                   Aditi=(16, {"2026-11-11": 5}, {"2026-11-11": 5}))),
    "under_logging": dict(people=people(Nikita=(20, {}, {}), Sumit=(16, {"2026-11-11": 8, "2026-11-12": 8, "2026-11-13": 5.5}, {"2026-11-11": 8, "2026-11-12": 8, "2026-11-13": 0}),
                                        Aditi=(16, {"2026-11-11": 2}, {"2026-11-11": 2}))),
    "leave": dict(people=BASE, leave=[{"name": "Sumit", "date": "2026-11-12", "hours": 4}, {"name": "Sumit", "date": "2026-11-13", "hours": 6},
                                      {"name": "Aditi", "date": "2026-11-11", "hours": 8}, {"name": "Aditi", "date": "2026-11-12", "hours": 8}, {"name": "Aditi", "date": "2026-11-13", "hours": 8}]),
    "not_achievable": dict(people=people(Nikita=(70, {"2026-11-11": 5, "2026-11-12": 5}, {"2026-11-11": 5, "2026-11-12": 5}), Sumit=(16, {"2026-11-11": 8, "2026-11-12": 8}, {"2026-11-11": 8, "2026-11-12": 8}), Aditi=(16, {"2026-11-11": 5}, {"2026-11-11": 5}))),
    "sprint_over": dict(asof="2026-11-24T05:00:00Z", people=people(Nikita=(18, {"2026-11-11": 9, "2026-11-12": 9}, {"2026-11-11": 9, "2026-11-12": 9}),
                                                                   Sumit=(16, {"2026-11-11": 8, "2026-11-12": 4}, {"2026-11-11": 8, "2026-11-12": 4}), Aditi=(16, {"2026-11-11": 5}, {"2026-11-11": 5}))),
    # the rule: every capacity day covers one equal chunk of the original estimate, so expected log = (estimate / capacity days) x capacity days passed
    "chunk": dict(asof="2026-11-16T13:30:00Z", people=people(Nikita=(51, {"2026-11-11": 8, "2026-11-12": 8, "2026-11-13": 5, "2026-11-16": 5}, {"2026-11-11": 8, "2026-11-12": 8, "2026-11-13": 5, "2026-11-16": 5}),      # 51 h over 8 days = 6.375 h a day, 4 days passed = 25.5 h expected, 26 h logged
                                                         Aditi=(51, {"2026-11-11": 4, "2026-11-12": 4, "2026-11-13": 4, "2026-11-16": 4}, {"2026-11-11": 4, "2026-11-12": 4, "2026-11-13": 4, "2026-11-16": 4}),     # 16 h logged against 25.5 h: 9.5 h missing
                                                         Sumit=(48, {"2026-11-11": 6, "2026-11-13": 6, "2026-11-16": 8}, {"2026-11-11": 6, "2026-11-13": 6, "2026-11-16": 8})),
              leave=[{"name": "Sumit", "date": "2026-11-12", "hours": 8}]),                                                                                                                                      # a full day of leave leaves 7 capacity days: 48 h / 7 x 3 days passed = 20.57 h
    "not_started": dict(asof="2026-11-10T06:00:00Z", people=people(Nikita=(18, {}, {}), Sumit=(16, {}, {}), Aditi=(16, {}, {}))),
}


# ---------- the independent model ----------
def model(sc):
    asof = sc.get("asof", BASE_ASOF)
    ist = __import__("datetime").datetime.fromisoformat(asof.replace("Z", "+00:00")) + __import__("datetime").timedelta(hours=5, minutes=30)
    ad, hh = ist.date().isoformat(), ist.hour + ist.minute / 60
    last = WD[-1]
    if ist.date().isoformat() + "T" + ist.strftime("%H:%M") > last + "T19:00": ad, hh = last, 19.0      # the page never goes past the last working hour
    el = sum(DH if d < ad else max(0, min(DH, hh - 11)) if d == ad else 0 for d in WD)
    late = ist.date().isoformat() > last
    tot = len(WD) * DH; k = CAP / tot
    out = {}
    for n, p in sc["people"].items():
        lv = {}
        for x in sc.get("leave", []):
            if x["name"] == n and x["date"] in WD: lv[x["date"]] = min(DH, lv.get(x["date"], 0) + x["hours"])
        avail = [max(0, DH - lv.get(d, 0)) * k for d in WD]; cap = sum(avail)
        def used_at(h, avail=avail):
            u, rest = 0.0, max(0, h)
            for a in avail:
                if rest <= 1e-9: break
                t = min(DH, rest); u += a * t / DH; rest -= t
            return u
        logged = sum(h for d, h in p["logs"].items() if d <= ad); burned = sum(h for d, h in p["burn"].items() if d <= ad)
        used = used_at(el); remain = max(0, p["E"] - burned); left = max(0, cap - used); gap = remain - left
        exp = p["E"] * used / cap if cap > 0 else 0          # (original estimate / capacity days) x capacity days passed
        miss = max(0, exp - logged)
        if late: verdict = "Not completed" if remain > .05 else "Completed"
        else: verdict = "Not achievable" if gap > .05 else "Achievable"
        flag = "Not started" if el <= 0 else "Time log missing" if miss > 8 else "Behind on logging" if miss > .05 else "On track"
        out[n] = dict(E=p["E"], logged=logged, burned=burned, remain=remain, over=max(0, logged - burned), exp=exp, miss=miss, left=left, cap=cap, used=used, leave=sum(lv.values()), gap=gap, verdict=verdict, flag=flag, used_at=used_at, p=p)
    return out, dict(el=el, ad=ad, late=late)


def ideal_at(M, h): return sum((m["E"] * max(0, 1 - m["used_at"](h) / m["cap"]) if m["cap"] > 0 else m["E"]) for m in M.values())
def remaining_at(M, h, ad, el):
    """the blue line: each person's estimate minus the hours burned up to the point h (working hours since day 3 started)"""
    tot = 0.0
    for m in M.values():
        burn = m["p"]["burn"]; cum = sum(v for d, v in burn.items() if d < WD[0]); pts = [(0, m["E"] - cum)]
        for i, d in enumerate(WD):
            if d > ad: continue
            cum += sum(v for x, v in burn.items() if x > (WD[i - 1] if i else "0000") and x <= d and x >= WD[0])
            pts.append((el if d == ad else (i + 1) * DH, max(0, m["E"] - cum)))
        cur = [max(0, y) for x, y in pts if x <= h + 1e-9]; tot += cur[-1] if cur else m["E"]
    return tot


# ---------- page helpers ----------
def load(ctx_factory, mock, name, width=1440):
    sc = SCEN[name]; pg = ctx_factory(width=width)
    def bd(route):
        r = route.fetch(); d = r.json(); d["S24"]["people"] = sc["people"]; route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
    pg.route("**/data/burndown.json*", bd)
    if "leave" in sc: pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": sc["leave"]}), content_type="application/json"))
    if "asof" in sc:
        def meta(route):
            r = route.fetch(); d = r.json(); d["refreshedAt"] = sc["asof"]; route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
        pg.route("**/data/meta.json*", meta)
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#tabs"); pg.wait_for_function("D.stories.length > 0"); pg.click('[data-tab="bd"]'); pg.wait_for_selector(".seg")
    M, info = model(sc)
    return pg, M, info


def num(t): return float(re.search(r"-?\d+(?:\.\d+)?", t).group(0))
def near(a, b, tol=.06): return abs(a - b) <= tol


def cells(pg, sel):
    return pg.evaluate("s => [...document.querySelectorAll(s + ' tbody tr')].map(r => [...r.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim()))", sel)


def bars(pg, scope):
    t = pg.locator(scope + " .cb").all_inner_texts(); out = {}
    for x in t:
        name = x.split("\n")[0].strip(); m = re.search(r"([\d.]+) h of ([\d.]+) h \((\d+)%\)", x); out[name] = (float(m.group(1)), float(m.group(2)), int(m.group(3)), x)
    return out


NAMES = ["Nikita", "Sumit", "Aditi"]


@pytest.mark.parametrize("name", list(SCEN))
def test_per_person_tables_match_the_model(ctx_factory, mock, name):
    pg, M, info = load(ctx_factory, mock, name); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tplan")
    plan = {r[0]: r for r in cells(pg, "#tplan")}; log = {r[0]: r for r in cells(pg, "#tlog")}
    assert set(plan) - {"Everyone"} == set(NAMES) and set(log) - {"Everyone"} == set(NAMES)
    for n in NAMES:
        m = M[n]; r, l = plan[n], log[n]
        assert near(num(r[1]), m["E"]) and near(num(r[2]), m["remain"]) and near(num(r[3]), m["left"]), (name, n, r, m["remain"], m["left"])
        assert r[4].startswith(m["verdict"]), (name, n, r, m["verdict"])
        assert near(num(l[1]), m["logged"]) and near(num(l[2]), m["over"]) and near(num(l[3]), m["exp"]) and near(num(l[4]), m["miss"]) and near(num(l[5]), m["leave"]), (name, n, l, {k: m[k] for k in ("logged", "over", "exp", "miss", "leave")})
        assert l[6] == m["flag"], (name, n, l, m["flag"])
    # the totals row is the sum of the rows above it, in both tables
    for tbl in (plan, log):
        for c in range(1, 4 if tbl is plan else 6):
            assert near(num(tbl["Everyone"][c]), sum(num(tbl[n][c]) for n in NAMES), .25), (name, c, tbl["Everyone"])


@pytest.mark.parametrize("name", list(SCEN))
def test_identities_hold_in_every_scenario(ctx_factory, mock, name):
    """original estimate = hours burned + remaining estimate; logged = burned + over; used + left = capacity"""
    pg, M, info = load(ctx_factory, mock, name)
    for n, m in M.items():
        assert near(m["E"], m["burned"] + m["remain"]) or m["remain"] == 0 and m["burned"] >= m["E"], (name, n)
        assert near(m["logged"], m["burned"] + m["over"]), (name, n)
        assert near(m["cap"], m["used"] + m["left"]) or m["left"] == 0, (name, n)
    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#capper"); b = bars(pg, "#capper")
    cap = sum(m["cap"] for m in M.values()); used = sum(m["used"] for m in M.values()); left = sum(m["left"] for m in M.values()); remain = sum(m["remain"] for m in M.values())
    assert near(b["Capacity used"][0], used, .1) and near(b["Capacity left"][0], left, .1) and near(b["Remaining estimate"][0], remain, .1), (name, b)
    for k in b: assert near(b[k][1], cap, .1), (name, k, b[k][1], cap)
    assert near(b["Capacity used"][0] + b["Capacity left"][0], b["Capacity used"][1], .15), "used + left must equal the capacity"
    for k in b: assert b[k][2] == round(b[k][0] / b[k][1] * 100) or abs(b[k][2] - b[k][0] / b[k][1] * 100) <= 1, (name, k, b[k])


@pytest.mark.parametrize("name", list(SCEN))
def test_overall_bars_and_the_working_out_agree(ctx_factory, mock, name):
    pg, M, info = load(ctx_factory, mock, name); pg.wait_for_selector("#capov"); b = bars(pg, "#capov"); t = pg.locator("#capov .calc").inner_text()
    cap = sum(m["cap"] for m in M.values()); used = sum(m["used"] for m in M.values()); left = sum(m["left"] for m in M.values()); remain = sum(m["remain"] for m in M.values()); lv = sum(m["leave"] for m in M.values())
    assert near(b["Capacity used"][0], used, .1) and near(b["Capacity left"][0], left, .1) and near(b["Remaining estimate"][0], remain, .1)
    assert "(3 people) × (64 hours each) = 192 hours" in t and "(8 working days) × (8 hours a day) = 64 hours" in t
    if lv > .05:
        assert re.search(rf"\(192 hours\) − \({re.escape(f'{lv:g}')} hours of leave\) = {re.escape(f'{cap:g}')} hours", t), t
    else: assert "Leave taken off" not in t
    m = re.search(r"\(([\d.]+) hours\) − \(([\d.]+) hours used\) = ([\d.]+) hours", t)
    assert m and near(float(m.group(1)) - float(m.group(2)), float(m.group(3)), .15), t           # the sum shown in words is itself correct
    fits = remain <= left + .05
    assert ("to spare" in b["Remaining estimate"][3]) == fits and ("more than the time left" in b["Remaining estimate"][3]) == (not fits)
    assert pg.locator("#capov .meter3 i").nth(2).get_attribute("class") == ("a" if fits else "r")


def line_points(pg, sel):
    pts = pg.evaluate("s => document.querySelector(s).getAttribute('points').trim().split(' ').map(p => p.split(',').map(Number))", sel)
    box = pg.evaluate("() => { const v = document.querySelector('#cw svg').viewBox.baseVal; return [v.width, v.height] }")
    return pts, box


@pytest.mark.parametrize("name", ["baseline", "overtime", "under_logging", "leave", "not_achievable"])
def test_chart_lines_follow_the_model(ctx_factory, mock, name):
    pg, M, info = load(ctx_factory, mock, name); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    sumE = sum(m["E"] for m in M.values()); top = max(16, -(-sumE // 16) * 16)
    pts, (W, H) = line_points(pg, "#actline"); L, R, Tp, B = 60, 16, 16, 76; ph = H - Tp - B
    val = lambda y: (Tp + ph - y) / ph * top
    ys = [val(y) for _, y in pts]
    assert all(b <= a + .05 for a, b in zip(ys, ys[1:])), f"the remaining estimate must never go up: {ys}"
    assert near(ys[-1], sum(m["remain"] for m in M.values()), .2), (name, ys[-1])
    label = pg.text_content("#nowlbl"); assert label.startswith("Now ·") and near(num(label.split("·")[1]), ys[-1], .06), label
    ip, _ = line_points(pg, "#idealline"); iv = [val(y) for _, y in ip]
    assert near(iv[0], sumE, .2) and near(iv[1], sumE, .2) and near(iv[-1], 0, .2), (name, iv)
    assert all(b <= a + .05 for a, b in zip(iv, iv[1:])), f"the ideal pace must never go up: {iv}"
    # one dot only on the line: the latest Jira pull, labelled Now
    assert pg.locator("#cw svg circle:visible").count() == 1


@pytest.mark.parametrize("name,k", [("baseline", 3), ("overtime", 3), ("leave", 3), ("leave", 4), ("under_logging", 2), ("not_achievable", 3)])
def test_hover_numbers_match_the_model(ctx_factory, mock, name, k):
    from test_burndown import hover_slot
    pg, M, info = load(ctx_factory, mock, name); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    txt = hover_slot(pg, k)
    n = k - 2 + 1                                              # working day number: sprint day 3 is working day 1
    h = min(n * DH, info["el"]); ideal = ideal_at(M, h); rem = remaining_at(M, h, info["ad"], info["el"])
    rows = pg.evaluate("() => [...document.querySelectorAll('#tip .mt')[0].querySelectorAll('tr')].map(r => [...r.cells].map(c => c.innerText.trim()))")
    got = {r[0].split(chr(10))[0]: num(r[1]) for r in rows}
    assert near(got["Ideal pace"], ideal, .06) and near(got["Remaining estimate"], rem, .06), (name, k, got, ideal, rem)
    diff = ideal - rem
    if abs(diff) < .05: assert "On ideal pace" in txt
    elif diff > 0: assert f"{diff:.1f} h ahead".replace(".0 h", " h") in txt.replace("\n", " ") or "ahead of the ideal pace" in txt, txt
    else: assert "behind the ideal pace" in txt and near(num(re.search(r"([\d.]+) h behind", txt).group(1)), -diff, .06), (txt, diff)
    ticket = pg.evaluate("() => [...document.querySelectorAll('#tip .mt')[1].querySelectorAll('tbody tr')].map(r => r.cells[0].innerText)")
    assert ticket == ["Epics", "User stories", "Sub-tasks"]


def test_verdict_and_gap_wording(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "not_achievable"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tplan")
    row = [r for r in pg.locator("#tplan tbody tr").all() if r.inner_text().startswith("Nikita")][0].inner_text()
    assert "Not achievable" in row and f"Short by {M['Nikita']['gap']:.1f} h" in row
    row = [r for r in pg.locator("#tplan tbody tr").all() if r.inner_text().startswith("Sumit")][0].inner_text()
    assert "Achievable" in row and "Room of" in row


def test_overtime_shows_the_extra_hours_and_does_not_hide_open_work(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "overtime"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    log = {r[0]: r for r in cells(pg, "#tlog")}; plan = {r[0]: r for r in cells(pg, "#tplan")}
    assert num(log["Nikita"][1]) == 30 and num(log["Nikita"][2]) == 12 and num(plan["Nikita"][2]) == 0       # 30 h logged on 18 h of tasks: 12 h over, nothing left
    assert num(plan["Sumit"][2]) == 24 and num(log["Sumit"][2]) == 0                                        # Sumit's open work is untouched by Nikita's extra hours


def test_sprint_over_uses_completed_wording(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "sprint_over"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tplan")
    plan = {r[0]: r for r in cells(pg, "#tplan")}
    assert plan["Nikita"][4].startswith("Completed") and plan["Sumit"][4].startswith("Not completed") and "Achievable" not in pg.locator("#tplan").inner_text()
    assert pg.locator("#nowlbl").text_content().startswith("End ·")


def test_before_the_sprint_starts_nothing_is_used(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "not_started"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
    log = cells(pg, "#tlog"); assert all(r[6] == "Not started" and num(r[3]) == 0 and num(r[4]) == 0 for r in log if r[0] != "Everyone")
    b = bars(pg, "#capper"); assert b["Capacity used"][0] == 0 and near(b["Capacity left"][0], 192, .1)


def test_leave_changes_capacity_expected_log_and_time_left(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "leave"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#leavep")
    t = pg.locator("#leavep").inner_text()
    for who, date in (("Sumit", "Thu 12 Nov"), ("Sumit", "Fri 13 Nov"), ("Aditi", "Wed 11 Nov")): assert who in t and date in t, t
    cap = {r[0]: r[1:] for r in cells(pg, "#leavecap")}; assert cap == {"Sumit": ["64", "2", "10", "54"], "Aditi": ["64", "3", "24", "40"]}, cap
    pg.select_option("#bdwho", "Sumit"); b = bars(pg, "#capper")
    assert near(b["Capacity used"][1], 54) and "(64 hours) − (10 hours of leave) = 54 hours" in pg.locator("#capper .calc").inner_text()
    pg.select_option("#bdwho", "Aditi"); log = cells(pg, "#tlog")[0]
    assert near(num(log[3]), 0) and near(num(log[5]), 24)         # three full days off, so no log is expected from the days that have passed


def test_empty_or_missing_leave_file_is_fine(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "baseline"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#leavep")
    assert "No leave in Sprint 24" in pg.locator("#leavep").inner_text() and not pg.errors
    pg2 = ctx_factory(); pg2.route("**/data/leave.json*", lambda r: r.fulfill(status=404, body="")); pg2.goto(mock.url + "/index.html"); pg2.wait_for_selector("#map .card"); pg2.click('[data-tab="bd"]'); pg2.click('[data-bdview="person"]')
    pg2.wait_for_selector("#leavep"); assert "No leave in Sprint 24" in pg2.locator("#leavep").inner_text() and not [e for e in pg2.errors if "404" not in e]


def test_no_sideways_scroll_in_the_burndown_tables(ctx_factory, mock):
    for w in (1280, 1024, 820):
        pg, M, info = load(ctx_factory, mock, "leave", width=w); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog")
        bad = pg.evaluate("() => [...document.querySelectorAll('#v-bd table')].filter(t => t.scrollWidth > t.parentElement.clientWidth + 1).length")
        assert bad == 0 and pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1, w
        assert pg.evaluate("() => !document.querySelector('#tlog').closest('.scroll')"), "no horizontal scroll container around the logging table"


def test_logic_page_is_gone(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg")
    assert page.locator(".seg button").all_inner_texts() == ["Overall", "Per person"] and "Rules behind every number" not in page.locator("#v-bd").inner_text() and page.locator("#lgchk").count() == 0


def test_estimate_column_lines_up_across_the_three_sections(ctx_factory, mock):
    from test_burndown import click_slot
    pg, M, info = load(ctx_factory, mock, "baseline"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg"); click_slot(pg, 4); pg.wait_for_selector("#dayd:not([hidden])"); pg.click('[data-dtab="open"]')
    assert pg.locator("#dayd table.dtab").count() == 1, "one table for epics, user stories and sub-tasks, so the columns line up"
    xs = pg.evaluate("() => [...document.querySelectorAll('#dayd .dtab td.num')].map(c => Math.round(c.getBoundingClientRect().right))"); assert len(set(xs)) == 1, xs
    txt = pg.locator("#dayd").inner_text(); assert "Sub-tasks" in txt and "original estimate (h)" in txt.lower() and "hour original estimate" not in txt


def test_expected_log_is_the_estimate_chunk_per_capacity_day(ctx_factory, mock):
    """The rule: the original estimate is divided by the capacity days; every capacity day should log that chunk. Someone with 51 h is NOT expected to log 8 h a day."""
    pg, M, info = load(ctx_factory, mock, "chunk")
    assert info["el"] == 32                                             # 4 capacity days passed (Wed, Thu, Fri, Mon), 8 h each
    assert round(M["Nikita"]["exp"], 4) == 25.5 and round(M["Aditi"]["exp"], 4) == 25.5 and round(M["Sumit"]["exp"], 3) == round(48 / 7 * 3, 3) == 20.571
    assert M["Nikita"]["flag"] == "On track" and M["Aditi"]["flag"] == "Time log missing" and M["Sumit"]["flag"] == "Behind on logging"      # 26 h >= 25.5 h; 9.5 h short; 0.57 h short
    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog"); log = {r[0]: r for r in cells(pg, "#tlog")}
    assert [num(log[n][3]) for n in ("Nikita", "Aditi", "Sumit")] == [25.5, 25.5, 20.6] and [log[n][6] for n in ("Nikita", "Aditi", "Sumit")] == ["On track", "Time log missing", "Behind on logging"]
    assert near(num(log["Aditi"][4]), 9.5) and num(log["Nikita"][4]) == 0 and near(num(log["Sumit"][4]), 20.571 - 20, .06)
    gb = pg.evaluate("() => [...document.querySelectorAll('.gb svg text')].map(t => t.textContent)") if False else None
    pg.click('[data-bdview="overall"]'); pg.wait_for_selector(".gb svg"); gb = pg.evaluate("() => [...document.querySelectorAll('.gb svg text')].map(t => t.textContent)")
    for n, want in (("Nikita", "25.5"), ("Aditi", "25.5"), ("Sumit", "20.6")): assert gb[gb.index(n) - 1] == want, (n, gb)


def test_on_track_means_logged_is_equal_to_or_more_than_expected(ctx_factory, mock):
    SCEN["edge"] = dict(asof="2026-11-16T13:30:00Z", people=people(A=(48, {"2026-11-11": 24}, {"2026-11-11": 24}), B=(48, {"2026-11-11": 23.9}, {"2026-11-11": 23.9}), C=(48, {"2026-11-11": 40}, {"2026-11-11": 40})))
    try:
        pg, M, info = load(ctx_factory, mock, "edge"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tlog"); log = {r[0]: r for r in cells(pg, "#tlog")}      # 48 h / 8 days x 4 days = 24 h expected
        assert log["A"][6] == "On track" and log["C"][6] == "On track" and log["B"][6] == "Behind on logging" and near(num(log["B"][4]), .1, .06)
    finally: SCEN.pop("edge", None)


def test_ideal_pace_is_the_chunk_per_capacity_day(ctx_factory, mock):
    """10 h over 5 capacity days is 2 h a day; the ideal pace line is the estimate minus the expected log."""
    pg, M, info = load(ctx_factory, mock, "chunk"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    for k, h in ((2, 8), (3, 16), (4, 24), (5, 32)):
        from test_burndown import hover_slot
        hover_slot(pg, k); got = pg.evaluate("() => +document.querySelectorAll('#tip .mt')[0].querySelectorAll('tr')[0].cells[1].innerText.replace(' h', '')")
        want = sum(m["E"] - m["E"] * m["used_at"](h) / m["cap"] for m in M.values()); assert near(got, want, .06), (k, got, want)


def test_leave_in_the_future_lowers_time_left_but_not_the_log_expected_now(ctx_factory, mock):
    sc = dict(people=BASE, leave=[{"name": "Nikita", "date": "2026-11-18", "hours": 8}, {"name": "Nikita", "date": "2026-11-19", "hours": 4}])
    SCEN["future_leave"] = sc
    try:
        pg, M, info = load(ctx_factory, mock, "future_leave"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#tplan")
        plan = {r[0]: r for r in cells(pg, "#tplan")}; log = {r[0]: r for r in cells(pg, "#tlog")}
        assert near(num(log["Nikita"][3]), 18 * 21.5667 / 52, .06) and near(num(log["Nikita"][5]), 12)         # 12 h of future leave leave 52 h of capacity, so each capacity day covers a bigger chunk
        assert near(num(plan["Nikita"][3]), 64 - 12 - 21.57, .06)                                  # 12 h of future leave come off the time left
    finally: SCEN.pop("future_leave", None)
