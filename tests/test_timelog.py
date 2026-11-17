"""Time logging: the flag rules against an independent model, the report pages, bulk handling, filters, and the daily grid"""
import datetime as dt, json, re
import pytest

pytestmark = [pytest.mark.guard, pytest.mark.math]

TODAY = dt.date(2026, 11, 13)                 # the fixture's pull: Friday 13 Nov 2026, 4:34 PM IST
HR = 16 + 34 / 60 - 11                        # hours of the working day that have passed (working time starts at 11:00)
FRAC = HR / 8
START = "2026-11-09"
WDAYS = [dt.date(2026, 11, d) for d in (11, 12, 13, 16, 17, 18, 19, 20)]
WORKING = {"In Progress", "Code_Review", "In Testing", "ACTIVE", "Reopened"}
CLOSED = {"Technical Review", "Done", "Fixed", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Invalid", "Deferred"}
DH = 8


def status_at(t, d):
    """status at the end of day d (independent implementation)"""
    ds = d.isoformat()
    if not t.get("h"): return t["st"] if (not t.get("sd") or ds >= t["sd"]) else None
    st = t.get("h0")
    for dd, to in t["h"]:
        if dd <= ds: st = to
    return st


def active(t, d): return status_at(t, d - dt.timedelta(days=1)) in WORKING or status_at(t, d) in WORKING


def model(tasks, today=TODAY, frac=FRAC, leave=()):
    days = [d for d in WDAYS if d <= today]
    live = [t for t in tasks if not t.get("y") and t.get("a") and t.get("st") is not None]
    n = {}
    for t in live:
        for d in days:
            if active(t, d): n[(t["a"], d)] = n.get((t["a"], d), 0) + 1
    out = {}
    for t in live:
        E, lg = t.get("e") or 0, t.get("lg") or 0
        closed, working = t["st"] in CLOSED, t["st"] in WORKING
        if not E or not (closed or working): continue
        if closed and not (t.get("d") and t["d"] >= START): continue
        cum, pick = 0.0, None
        for d in days:
            if not active(t, d): continue
            pick = pick or d
            lv = sum(x["hours"] for x in leave if x["name"] == t["a"] and x["date"] == d.isoformat())
            cum += max(0, DH - lv) / n[(t["a"], d)] * (1 if d < today else frac)
        if not pick and not closed: continue
        exp = E if closed else min(E, cum); gap = exp - lg
        if gap < min(2, .5 * E) - 1e-9: continue
        out[t["k"]] = ("closed" if closed else "none" if lg <= 0 else "behind", round(exp, 1), round(lg, 1), round(gap, 1))
    return out


def T(k, a, e, st, h0, h, lg=0, ll=None, d=None, wl=None, **kw):
    return {"k": k, "a": a, "e": e, "d": d, "s": f"Task {k}", "st": st, "sd": (h[-1][0] if h else None), "h0": h0, "h": h, "lg": lg, "ll": ll, "wl": wl or {}, "ty": "Sub-task", **kw}


EXTRA = [
    T("PROD-9111", "Nikita", 8, "In Progress", "Backlog", [["2026-11-11", "In Progress"]], 6.5, "2026-11-12", wl={"2026-11-11": 3.5, "2026-11-12": 3}),                # gap 1.5: under the 2 h line
    T("PROD-9112", "Nikita", 4, "Deployed to UAT", "Backlog", [["2026-11-11", "In Progress"], ["2026-11-12", "Deployed to UAT"]], 4, "2026-11-12", d="2026-11-12", wl={"2026-11-12": 4}),
    T("PROD-9113", "Nikita", 6, "In Progress", "Backlog", [["2026-11-10", "In Progress"]]),                                                                                       # none: capped at the 6 h estimate
    T("PROD-9121", "Sumit", 16, "In Testing", "Backlog", [["2026-11-09", "In Progress"], ["2026-11-12", "In Testing"]], 16, "2026-11-12", wl={"2026-11-11": 8, "2026-11-12": 8}),
    T("PROD-9122", "Aditi", 12, "Done", "In Progress", [["2026-11-13", "Done"]], d="2026-11-13"),                                                                               # closed under-logged: 12 h
    T("PROD-9141", "Aditi", 8, "In Progress", "Backlog", [["2026-11-09", "In Progress"]], 5, "2026-11-10", wl={"2026-11-10": 5}),                                                  # behind: 3 h
    T("PROD-9142", "Sumit", 4, "Code_Review", "Backlog", [["2026-11-13", "Code_Review"]]),                                                                                       # started today: gap under the line
    T("PROD-9143", "Abhishek", 5, "In Progress", "Backlog", [["2026-11-12", "In Progress"]]),                                                                                    # none: 5 h
    T("PROD-9144", "Abhishek", 9, "In Progress", "Backlog", [["2026-11-11", "In Progress"]], 9, "2026-11-12", wl={"2026-11-11": 5, "2026-11-12": 4}),                           # fully logged
    T("PROD-9145", "Sumit", 0, "In Progress", "Backlog", [["2026-11-10", "In Progress"]]),                                                                                       # no estimate: counts as busy, never flagged
    T("PROD-9146", "Aditi", 5, "Backlog", "Backlog", []),
    T("PROD-9147", "Aditi", 5, "Done", "In Progress", [["2026-11-05", "Done"]], d="2026-11-05"),                                                                                # closed before the sprint
    T("PROD-9148", "Aditi", 0, "Done", "In Progress", [["2026-11-12", "Done"]], d="2026-11-12"),
    T("PROD-9149", "Sumit", 4, "Code_Review", "Backlog", [["2026-11-11", "Code_Review"]], 2, "2026-11-11", wl={"2026-11-11": 2}),                                                # behind: 2 h (exactly on the line)
    {"k": "PROD-9150", "a": None, "e": 3, "d": None, "s": "Unassigned", "st": "In Progress", "sd": "2026-11-09", "h0": "Backlog", "h": [["2026-11-09", "In Progress"]], "lg": 0, "ll": None, "wl": {}},
    T("PROD-9103", "Aditi", 4, "In Progress", "Backlog", [["2026-11-09", "In Progress"]], y=1),
]


def load(ctx_factory, mock, tasks=None, width=1440, height=900, touch=False, leave=None):
    pg = ctx_factory(width=width, height=height, touch=touch)
    if tasks is not None:
        def bd(route):
            r = route.fetch(); d = r.json(); d["S24"]["tasks"] = tasks; route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
        pg.route("**/data/burndown.json*", bd)
    if leave is not None:
        pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": leave}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("[data-tab=tlog]", state="attached"); pg.wait_for_timeout(500)
    pg.evaluate("document.querySelector('[data-tab=tlog]').click()"); pg.wait_for_selector("#v-tlog .tls"); return pg


def page_flags(pg):
    return pg.evaluate("""() => { const c = tlCtx(); return c.all.map(f => [f.t.k, f.r, f.exp, f.lg, f.gap]); }""")


def same(got, exp):
    got = {k: (r, e, l, g) for k, r, e, l, g in got}; assert set(got) == set(exp), (sorted(got), sorted(exp))
    for k, (r, e, l, g) in exp.items():
        assert got[k][0] == r and abs(got[k][1] - e) <= .11 and abs(got[k][2] - l) <= .11 and abs(got[k][3] - g) <= .11, (k, got[k], exp[k])


def test_rules_match_the_independent_model(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); exp = model(EXTRA); same(page_flags(pg), exp)
    assert set(exp) == {"PROD-9113", "PROD-9122", "PROD-9141", "PROD-9143", "PROD-9149"}, exp
    assert exp["PROD-9113"] == ("none", 6.0, 0.0, 6.0) and exp["PROD-9122"] == ("closed", 12.0, 0.0, 12.0) and exp["PROD-9141"][0] == "behind" and exp["PROD-9143"] == ("none", 5.0, 0.0, 5.0)


def test_the_two_hour_line_and_small_tickets(ctx_factory, mock):
    tasks = [T("PROD-1", "Nikita", 1, "In Progress", "Backlog", [["2026-11-11", "In Progress"]]),           # 1 h ticket, nothing logged: line is half the estimate
             T("PROD-2", "Sumit", 40, "In Progress", "Backlog", [["2026-11-12", "In Progress"]], 12, "2026-11-13", wl={"2026-11-12": 8, "2026-11-13": 4}),   # big ticket, 13.6 h expected, 12 logged: under the line
             T("PROD-3", "Aditi", 40, "In Progress", "Backlog", [["2026-11-11", "In Progress"]], 2, "2026-11-11", wl={"2026-11-11": 2})]    # 21 h expected, 2 logged: flagged
    pg = load(ctx_factory, mock, tasks); exp = model(tasks); same(page_flags(pg), exp); assert "PROD-1" in exp and "PROD-2" not in exp and "PROD-3" in exp


def test_fair_share_between_tickets_of_one_person(ctx_factory, mock):
    one = [T("PROD-1", "Nikita", 40, "In Progress", "Backlog", [["2026-11-11", "In Progress"]])]
    two = one + [T("PROD-2", "Nikita", 40, "In Progress", "Backlog", [["2026-11-11", "In Progress"]])]
    e1 = model(one)["PROD-1"][1]; e2 = model(two)["PROD-1"][1]
    assert abs(e1 - (8 + 8 + 8 * FRAC)) < .11 and abs(e2 - e1 / 2) < .11, (e1, e2)       # two tickets share the same hours
    for tasks in (one, two):
        pg = load(ctx_factory, mock, tasks); same(page_flags(pg), model(tasks))


def test_leave_lowers_the_hours_available(ctx_factory, mock):
    tasks = [T("PROD-1", "Nikita", 40, "In Progress", "Backlog", [["2026-11-11", "In Progress"]])]; lv = [{"name": "Nikita", "date": "2026-11-12", "hours": 6}]
    pg = load(ctx_factory, mock, tasks, leave=lv); same(page_flags(pg), model(tasks, leave=lv)); assert abs(model(tasks, leave=lv)["PROD-1"][1] - model(tasks)["PROD-1"][1] + 6) < .11


def test_a_closed_ticket_with_its_estimate_logged_is_fine_and_one_closed_before_the_sprint_is_ignored(ctx_factory, mock):
    tasks = [T("PROD-1", "Nikita", 8, "Done", "In Progress", [["2026-11-12", "Done"]], 8, "2026-11-12", d="2026-11-12", wl={"2026-11-12": 8}), T("PROD-2", "Nikita", 8, "Done", "In Progress", [["2026-10-30", "Done"]], d="2026-10-30")]
    pg = load(ctx_factory, mock, tasks); assert page_flags(pg) == [] and model(tasks) == {}


def test_ordering_is_closed_then_no_time_then_behind_each_by_gap(ctx_factory, mock):
    got = page_flags(load(ctx_factory, mock, EXTRA)); order = {"closed": 0, "none": 1, "behind": 2}
    assert [order[x[1]] for x in got] == sorted(order[x[1]] for x in got)
    for r in order:
        g = [x[4] for x in got if x[1] == r]; assert g == sorted(g, reverse=True), (r, g)


def test_summary_cards_and_groups_show_the_model_numbers(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); exp = model(EXTRA); by = {}
    for k, v in exp.items(): by.setdefault(next(t["a"] for t in EXTRA if t["k"] == k), []).append(v)
    fmt = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")
    cards = [x.replace("\n", " ") for x in pg.locator(".tlstats .tls").all_inner_texts()]
    assert str(len(exp)) in cards[0] and f"{len(by)} of 4" in cards[1] and fmt(sum(v[3] for v in exp.values())) in cards[2], cards
    for h in pg.locator(".tlgh").all_inner_texts():
        n = h.split("\n")[1]; mine = by[n]; assert f"{len(mine)} ticket" in h and fmt(sum(v[3] for v in mine)) + " h gap" in h, (n, h)


def test_row_shows_should_be_logged_logged_gap_and_the_difference_adds_up(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); exp = model(EXTRA)
    for row in pg.locator(".tlt2 tbody tr").all():
        c = row.locator("td").all_inner_texts(); k = c[0]; r, e, l, g = exp[k]
        assert c[3] == f"{e:g} h" and c[4] == f"{l:g} h" and c[5] == f"{g:g} h" and abs(float(c[3][:-2]) - float(c[4][:-2]) - float(c[5][:-2])) < .11, (k, c)
        assert c[6] == {"none": "No time logged", "behind": "Behind on logging", "closed": "Closed under-logged"}[r]
        assert row.locator("a.link").get_attribute("href") == "https://canaryai.atlassian.net/browse/" + k


def test_no_story_or_epic_is_ever_listed(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); txt = pg.inner_text("#v-tlog"); assert "PROD-9103" not in txt and "PROD-9150" not in txt


def open_ticket(pg, who, key):
    if not pg.locator(f".tlt2 tr:has-text('{key}')").count(): pg.click(f".tlgh:has-text('{who}')")
    pg.click(f".tlt2 tr:has-text('{key}') [data-tlwhy]"); pg.wait_for_selector(".tlwhy")


def test_why_button_opens_a_ticket_page_with_reasoning_and_the_calculation(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); open_ticket(pg, "Abhishek", "PROD-9143"); why = pg.inner_text(".tlwhy"); exp = model(EXTRA)["PROD-9143"]
    assert "Picked up on Thu 12 Nov" in why and f"{exp[1]:g} h should be logged" in why and "Nothing has been logged on it." in why and f"The gap is {exp[3]:g} h." in why and "Abhishek had" in why, why
    cards = [x.replace("\n", " ") for x in pg.locator(".tl4 .tls").all_inner_texts()]; assert "5 h" in cards[0] and "5 h" in cards[1] and "nothing yet" in cards[2] and "5 h" in cards[3], cards
    rows = pg.locator(".tlc2 tbody tr").all(); assert len(rows) == 2                          # Thursday and Friday
    r0 = rows[0].locator("td").all_inner_texts(); assert r0[0] == "Thu 12 Nov" and r0[1] == "2" and "(8) / (2) × (1) = 4 h" in r0[4] and r0[5] == "4 h"
    r1 = rows[1].locator("td").all_inner_texts(); assert r1[0] == "Fri 13 Nov" and "× (0.7)" in r1[4] and r1[5] == "5 h"                   # 4 + 8/2 x 0.696 = 6.8, capped at the 5 h estimate
    assert "(5 h should be logged) − (0 h logged) = 5 h" in pg.inner_text("#v-tlog") and pg.locator("svg.tlchart path").count() == 2
    pg.click("[data-tlback]"); assert pg.locator(".tlstats .tls").count() == 3


def test_closed_ticket_page_explains_the_full_estimate_rule(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); open_ticket(pg, "Aditi", "PROD-9122")
    why = pg.inner_text(".tlwhy"); assert "Closed on Fri 13 Nov in Done" in why and "full estimate of 12 h" in why and "(12 h) − (0 h) = 12 h" in pg.inner_text("#v-tlog")


def test_person_report_lists_every_ticket_with_pages(ctx_factory, mock):
    bulk = [T(f"PROD-{7000 + i}", "Nikita", 4, "Done", "In Progress", [["2026-11-12", "Done"]], d="2026-11-12") for i in range(40)]
    pg = load(ctx_factory, mock, bulk); exp = model(bulk); assert len(exp) == 40
    pg.click("[data-tlperson=Nikita]"); pg.wait_for_selector(".tlp"); assert pg.locator(".tlp tbody tr").count() == 15 and "Page 1 of 3" in pg.inner_text(".tlpg")
    s = pg.inner_text(".tlstats").replace("\n", " "); assert "40" in s and f"{sum(v[1] for v in exp.values()):g} h" in s
    pg.click("[data-tlpg='1']"); pg.click("[data-tlpg='1']"); assert pg.locator(".tlp tbody tr").count() == 10 and pg.locator("[data-tlpg='1']").is_disabled()
    pg.locator(".tlp tbody tr").first.locator("[data-tlwhy]").click(); pg.wait_for_selector(".tlwhy"); pg.click("[data-tlback]"); assert pg.locator(".tlp").count() == 1, "back from a ticket returns to the person report"


def test_bulk_sixty_tickets_one_person_is_paged_and_counts_match(ctx_factory, mock):
    bulk = [T(f"PROD-{7000 + i}", "Nikita", 4, "Done", "In Progress", [["2026-11-12", "Done"]], d="2026-11-12") for i in range(60)] + [T("PROD-8000", "Sumit", 6, "Done", "In Progress", [["2026-11-12", "Done"]], d="2026-11-12")]
    pg = load(ctx_factory, mock, bulk); exp = model(bulk); assert len(exp) == 61 and exp["PROD-7000"][1] == 4.0
    assert pg.locator(".tlt2 tbody tr").count() == 10 and "Show 20 more of 50" in pg.locator(".more").inner_text()
    pg.click(".more"); pg.click(".more"); pg.click(".more"); assert pg.locator(".tlt2 tbody tr").count() == 60 and pg.locator(".more").count() == 0
    assert "60 tickets" in pg.locator(".tlgh").first.inner_text() and "240 h gap" in pg.locator(".tlgh").first.inner_text()
    pg.click(".tlgh:has-text('Sumit')"); assert pg.locator(".tlgh[aria-expanded=true]").count() == 1


def test_filters_by_reason_person_and_search(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); exp = model(EXTRA)
    pg.click("[data-tlr=behind]"); shown = sum(int(re.search(r"(\d+) ticket", h).group(1)) for h in pg.locator(".tlgh").all_inner_texts()); assert shown == sum(1 for v in exp.values() if v[0] == "behind")
    pg.click("[data-tlr=all]"); pg.select_option("#tlwho", "Sumit"); heads = pg.locator(".tlgh").all_inner_texts(); assert len(heads) == 1 and "Sumit" in heads[0]
    pg.select_option("#tlwho", "All"); pg.fill("#tlq", "9143"); assert pg.locator(".tlgh").count() == 1 and "Abhishek" in pg.locator(".tlgh").first.inner_text()
    pg.fill("#tlq", "no-such-ticket"); assert pg.locator(".tle").count() == 1 and "No ticket matches" in pg.locator(".tle").inner_text()


def test_nothing_to_chase_is_said_plainly(ctx_factory, mock):
    ok = [T("PROD-9111", "Nikita", 8, "In Progress", "Backlog", [["2026-11-11", "In Progress"]], 8, "2026-11-12", wl={"2026-11-12": 8})]; pg = load(ctx_factory, mock, ok)
    assert "Nothing to chase" in pg.locator(".tle").inner_text() and pg.locator(".tls b").first.inner_text() == "0"


def test_copy_reminder_has_the_numbers(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); pg.evaluate("window.__c = null; navigator.clipboard.writeText = t => { window.__c = t; return Promise.resolve(); }")
    pg.click("[data-tlcopy]"); pg.wait_for_function("window.__c"); txt = pg.evaluate("window.__c"); who = pg.locator("[data-tlcopy]").get_attribute("data-tlcopy"); exp = model(EXTRA)
    mine = [k for k in exp if next(t["a"] for t in EXTRA if t["k"] == k) == who]
    assert txt.startswith(f"Hi {who}, these tickets need time logged for Sprint 24 ({len(mine)}):") and all(k in txt for k in mine)
    k = mine[0]; r, e, l, g = exp[k]; assert f"{k} Task {k}: should be {e:g} h, logged {l:g} h, gap {g:g} h" in txt and "Please log the time today" in txt


def test_info_boxes_show_a_calculation_with_the_real_ticket(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); pg.locator(".tls .ibtn").first.hover(); pg.wait_for_selector("#gtip:not([hidden])"); assert "No time logged" in pg.inner_text("#gtip") and pg.locator("#gtip .tag").count() == 3
    pg.mouse.move(2, 2); pg.locator(".tlt2 th:has-text('Should be logged') .ibtn").first.hover(); pg.wait_for_selector("#gtip:not([hidden])"); x = pg.inner_text("#gtip").lower()
    assert "calculation" in x and "example" not in x and re.search(r"\(8 h\) / \(\d\) × \(", x), x
    pg.mouse.move(2, 2); pg.locator(".tlt2 th:has-text('Gap') .ibtn").first.hover(); pg.wait_for_selector("#gtip:not([hidden])"); x = pg.inner_text("#gtip").lower(); assert "calculation" in x and re.search(r"\(([\d.]+) h\) − \(([\d.]+) h\) = ([\d.]+) h", x)


def test_laptop_and_phone_have_no_sideways_scroll_or_cut_text(ctx_factory, mock):
    probe = """() => [...document.querySelectorAll('#v-tlog *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1) && !e.closest('.scroll'); }).map(e => e.className).slice(0, 5)"""
    for w, h, touch in ((1440, 900, False), (1100, 800, False), (390, 844, True), (360, 700, True)):
        pg = load(ctx_factory, mock, EXTRA, w, h, touch); pg.wait_for_timeout(300)
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), w
        assert not pg.evaluate(probe), (w, pg.evaluate(probe))
        if w < 500: assert pg.locator(".tlt2 thead").is_hidden() and pg.locator(".tlt2 tbody tr").first.locator("td").first.get_attribute("data-l") == "Ticket"
        pg.locator("[data-tlwhy]").first.evaluate("e => e.click()"); pg.wait_for_selector(".tlwhy"); pg.wait_for_timeout(250)
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), ("ticket page", w)
        assert not pg.evaluate(probe), ("ticket page", w, pg.evaluate(probe))


def test_the_tab_is_in_the_left_panel(ctx_factory, mock):
    pg = load(ctx_factory, mock, EXTRA); assert pg.locator("#tabs [data-tab=tlog]").is_visible() and pg.locator("[data-tab=tlog][aria-selected=true]").count() == 1
    pg.click("[data-tab=map]"); pg.click("[data-tab=tlog]"); pg.wait_for_selector("#v-tlog .tls"); assert not pg.errors


def test_old_data_without_statuses_asks_for_a_refresh(ctx_factory, mock):
    pg = ctx_factory()

    def bd(route):
        r = route.fetch(); d = r.json(); d["S24"]["tasks"] = [{"k": t["k"], "a": t["a"], "e": t["e"], "d": t["d"]} for t in d["S24"]["tasks"]]
        route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
    pg.route("**/data/burndown.json*", bd); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("[data-tab=tlog]", state="attached"); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('[data-tab=tlog]').click()"); pg.wait_for_selector("#v-tlog .empty"); assert "Press Refresh" in pg.inner_text("#v-tlog")


def grid_model(logs, E, cap_days, sd, wd0, ad):
    out, daily = {}, (E / cap_days if cap_days else 0)
    for d in sd:
        if d < wd0 or d > ad: out[d] = "na"
        else:
            lg = logs.get(d, 0); out[d] = "ok" if lg + .05 >= daily else "now" if d == ad else "warn" if lg > 0 else "bad"
    return out


def open_person_view(ctx_factory, mock):
    pg = ctx_factory(width=1440, height=900); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("[data-tab=bd]", state="attached"); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('[data-tab=bd]').click()"); pg.click("[data-bdview=person]"); pg.wait_for_selector("#dgrid"); return pg


def test_daily_grid_cells_match_the_model(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock)
    data = pg.evaluate("() => { const s = BD.S24; return {sd: sprintDays(s), wd: workDays(s.win), people: s.people, ad: asOfIST().slice(0, 10)}; }")
    for r in pg.locator("#dgrid .dgr:not(.dgh)").all():
        name = r.locator(".dgn").inner_text().strip(); p = data["people"][name]; cells = r.locator(".dgc").all()
        exp = grid_model(p["logs"], p["E"], len(data["wd"]), data["sd"], data["wd"][0], data["ad"])
        for d, c in zip(data["sd"], cells):
            cls = c.get_attribute("class").split()[1]; assert cls == exp[d], (name, d, cls, exp[d])
            if cls in ("ok", "warn", "bad"): assert c.inner_text() == f"{round(p['logs'].get(d, 0), 1):g}", (name, d, c.inner_text())
        assert r.locator(".dgt").inner_text() == f"{round(sum(h for d, h in p['logs'].items() if d <= data['ad']), 1):g}"


def test_daily_grid_legend_uses_the_same_tags(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock)
    pg.locator("#dgrid .ibtn").scroll_into_view_if_needed(); pg.wait_for_timeout(400); pg.locator("#dgrid .ibtn").hover(); pg.wait_for_selector("#gtip:not([hidden])"); t = pg.inner_text("#gtip").lower(); assert "at or above the daily target" in t and "nothing logged on a working day" in t and "calculation" in t
    assert pg.locator("#gtip .tag").count() == 3 and pg.locator("#dgrid .dgr:not(.dgh)").count() >= 3
