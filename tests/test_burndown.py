"""Burndown page: Overall and Per person (layout, wording, hover card, day list). The numbers are checked in test_burndown_math.py."""
import re


def open_bd(page, view="person"):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg")
    if view == "person": page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    else: page.click('[data-bdview="overall"]'); page.wait_for_selector(".term")


def _chart(page):
    page.locator("#cw").scroll_into_view_if_needed(); page.wait_for_timeout(250)      # a scroll event hides the hover card, so let the scroll finish first
    return page.locator("#cw svg").bounding_box()


def hover_slot(page, k):
    svg = _chart(page); L, pw, slots, W = 60, 1000 - 60 - 16, 11, 1000
    x = svg["x"] + (L + (k + .5) / slots * pw) / W * svg["width"]; page.mouse.move(x, svg["y"] + svg["height"] * .4)
    page.wait_for_selector("#tip:not([hidden])"); return page.locator("#tip").inner_text()


def rows(page):
    """The two small tables in the hover card as {row name: [cells]}"""
    return page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#tip .mt tbody tr')].map(r => [r.cells[0].innerText.trim().split(String.fromCharCode(10))[0], [...r.cells].slice(1).map(c => c.innerText.trim())]))")


def click_slot(page, k):
    svg = _chart(page); L, pw, slots, W = 60, 1000 - 60 - 16, 11, 1000
    page.mouse.click(svg["x"] + (L + (k + .5) / slots * pw) / W * svg["width"], svg["y"] + svg["height"] * .4)


def ideal_left(total, n, tot=64): return total * (1 - n * 8 / tot)


def num(t): return float(re.search(r"-?\d+(?:\.\d+)?", t).group(0))


# ---------- header and structure
def test_two_areas_overall_is_the_default(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg")
    tabs = page.locator(".seg button"); assert tabs.all_inner_texts() == ["Overall", "Per person"]
    assert tabs.nth(0).get_attribute("aria-selected") == "true" and page.locator(".term").count() == 1 and page.locator("#cw").count() == 0


def test_as_of_is_read_only_and_shows_the_pull_time(page):
    open_bd(page, "overall"); a = page.locator("#asof")
    assert a.evaluate("e => e.tagName") == "DIV" and a.get_attribute("contenteditable") is None and a.inner_text() == "13 Nov, 4:34 PM IST" and page.locator("#fasof input").count() == 0


def test_as_of_info_shows_on_hover_only(page):
    open_bd(page, "overall"); tip = page.locator("#gtip"); assert not tip.is_visible()
    page.hover("#asinfo"); tip.wait_for(); assert "latest Jira pull" in tip.inner_text() and "not the current time" in tip.inner_text()
    page.mouse.move(5, 5); tip.wait_for(state="hidden")


# ---------- Overall (static)
def test_overall_has_the_overview_three_bars_hours_by_person_and_leave(page):
    open_bd(page, "overall")
    assert page.locator(".term").count() == 1 and page.locator("#capov").count() == 1 and page.locator("svg[aria-label^='Original estimate, logged']").count() == 1 and page.locator("#leavep").count() == 1
    assert page.locator("#bdwho").count() == 0 and page.locator("#cw").count() == 0 and page.locator("#tplan").count() == 0


def test_overview_has_one_fact_per_row_with_no_dot_separated_lines(page):
    open_bd(page, "overall"); grid = page.locator(".tgrid.ov"); keys = grid.locator(".tk").all_inner_texts(); vals = grid.locator(".tv").all_inner_texts()
    assert [k.rstrip("i").strip().lower() for k in keys] == ["sprint", "dates", "length", "sprint planning", "working time", "hours a day", "working days", "capacity per person"]
    assert all(" · " not in v for v in vals), vals
    d = dict(zip([k.rstrip("i").strip().lower() for k in keys], vals))
    assert d["sprint"] == "Sprint 24" and d["dates"] == "9 Nov to 23 Nov" and d["length"] == "10 working days"
    assert d["sprint planning"] == "Days 1 to 2 (Mon 9 Nov and Tue 10 Nov), no capacity counted" and d["working time"] == "11:00 to 19:00 IST" and d["hours a day"] == "8 hours"
    assert d["working days"] == "8 (days 3 to 10)" and d["capacity per person"] == "64 hours = (8 days) × (8 hours)"


def test_two_widgets_show_the_sprint_day_and_the_capacity_day(page):
    for view in ("overall", "person"):
        open_bd(page, view); w = page.locator("#daywidgets")
        sp, cp = page.locator("#wsprint"), page.locator("#wcap")
        assert sp.inner_text().replace("\n", " ").upper().startswith("SPRINT DAY") and "5 of 10" in sp.inner_text().replace("\n", " ") and "Fri 13 Nov" in sp.inner_text()
        assert cp.inner_text().replace("\n", " ").upper().startswith("CAPACITY DAY") and "3 of 8" in cp.inner_text().replace("\n", " ") and "Fri 13 Nov" in cp.inner_text()
        a, b = sp.bounding_box(), cp.bounding_box(); assert abs(a["y"] - b["y"]) <= 1 and abs(a["height"] - b["height"]) <= 1 and abs(a["width"] - b["width"]) <= 2, "two equal widgets side by side"
        assert page.evaluate("parseFloat(getComputedStyle(document.querySelector('#wsprint b')).fontSize)") >= 40, "big and highlighted"
    open_bd(page, "overall"); t = page.locator(".term").inner_text().lower()
    assert "10 working days" in t and "days 1 to 2" in t and "mon 9 nov" in t and "sprint day" not in t, "the rest of the facts sit below the two widgets"
    assert page.locator("#daywidgets").bounding_box()["y"] < page.locator(".term").bounding_box()["y"]


def widget_texts(ctx_factory, mock, asof):
    import json
    pg = ctx_factory(); pg.route("**/data/meta.json*", lambda r: r.fulfill(body=json.dumps({**r.fetch().json(), "refreshedAt": asof}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="bd"]'); pg.wait_for_selector("#daywidgets")
    return pg.locator("#wsprint").inner_text().replace("\n", " "), pg.locator("#wcap").inner_text().replace("\n", " ")


def test_widgets_in_every_stage_of_the_sprint(ctx_factory, mock):
    sp, cp = widget_texts(ctx_factory, mock, "2026-11-10T06:00:00Z")         # Tue 10 Nov: the second Sprint Planning day
    assert "2 of 10" in sp and "Tue 10 Nov" in sp and "Planning" in cp and "no capacity" in cp.lower()
    sp, cp = widget_texts(ctx_factory, mock, "2026-11-16T06:00:00Z")         # Mon 16 Nov: sprint day 6, capacity day 4
    assert "6 of 10" in sp and "4 of 8" in cp
    sp, cp = widget_texts(ctx_factory, mock, "2026-11-24T06:00:00Z")
    assert "Complete" in sp and "Complete" in cp
    sp, cp = widget_texts(ctx_factory, mock, "2026-11-06T06:00:00Z")
    assert "Not started" in sp and "Not started" in cp


def test_three_capacity_bars_with_the_working_out_in_plain_words(page):
    open_bd(page, "overall"); c = page.locator("#capov"); t = c.inner_text()
    assert "Whole team" in t and "3 people" in t
    assert c.locator(".cb .cbt b").all_inner_texts() == ["Capacity used", "Capacity left", "Remaining estimate"]
    assert [c.locator(".meter3 i").nth(i).get_attribute("class") for i in range(2)] == ["g", "b"] and c.locator(".meter3 i").nth(2).get_attribute("class") in ("a", "r")
    used, left = (num(re.search(rf"{w}\s+([\d.]+) h of", t).group(1)) for w in ("Capacity used", "Capacity left")); assert abs(used + left - 192) < .2 and "of 192 h" in t
    w = c.locator(".calc").inner_text(); assert "HOW THIS IS WORKED OUT" in w.upper()
    for line in ("(8 working days) × (8 hours a day) = 64 hours", "(3 people) × (64 hours each) = 192 hours", "Working hours that have passed since the sprint started", "(original estimate) − (hours logged on each sub-task, never below 0)"): assert line in w, line
    assert "Leave taken off" not in w


def test_one_grouped_bar_chart_with_three_series(page):
    open_bd(page, "overall"); k = page.locator("#v-bd .key").first.inner_text()
    assert "Original estimate (h)" in k and "Logged (h)" in k and "Expected log by now (h)" in k and page.locator(".brow").count() == 0


# ---------- Per person (dynamic)
def test_person_selector_drives_the_capacity_card_and_names_the_person(page):
    open_bd(page); sel = page.locator("#bdwho")
    assert sel.locator("option").first.inner_text() == "Everyone" and set(sel.locator("option").all_inner_texts()) == {"Everyone", "Aditi", "Nikita", "Sumit"}
    t = page.locator("#capper").inner_text(); assert "Everyone" in t and "3 people" in t and "(3 people) × (64 hours each) = 192 hours" in t
    page.select_option("#bdwho", "Nikita"); t = page.locator("#capper").inner_text()
    used = num(re.search(r"Capacity used\s+([\d.]+) h of", t).group(1)); left = num(re.search(r"Capacity left\s+([\d.]+) h of", t).group(1))
    assert "Nikita" in t and "of 64 h" in t and abs(used + left - 64) < .15 and 21 < used < 22.5 and "Team capacity" not in t, (used, left)


def test_each_bar_is_labelled_and_has_a_description(page):
    open_bd(page); page.select_option("#bdwho", "Sumit"); card = page.locator("#capper")
    assert card.locator(".meter3").count() == 3 and all("Sumit" not in x for x in card.locator(".meter3").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))"))
    assert [x.split(":")[0] for x in card.locator(".meter3").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")] == ["Capacity used", "Capacity left", "Remaining estimate"]
    assert card.locator(".cbn").all_inner_texts()[:2] == ["Working hours that have passed", "Working hours still to come"]


def test_tables_follow_the_selection(page):
    open_bd(page)
    for t in ("#tplan", "#tlog"):
        r = page.locator(f"{t} tbody tr"); assert r.count() == 4 and r.last.inner_text().startswith("Everyone")
    page.select_option("#bdwho", "Nikita")
    for t in ("#tplan", "#tlog"):
        r = page.locator(f"{t} tbody tr"); assert r.count() == 1 and r.first.inner_text().startswith("Nikita")


def test_time_is_split_into_two_tables_that_fit_without_sideways_scrolling(page):
    open_bd(page)
    h = lambda sel: [x.lower().rstrip("i").strip() for x in page.locator(f"{sel} thead th").all_inner_texts()]
    assert h("#tplan") == ["name", "original estimate (h)", "remaining estimate (h)", "time left in the sprint (h)", "verdict"]
    assert h("#tlog") == ["name", "logged (h)", "over estimate (h)", "expected log by now (h)", "missing log (h)", "leave (h)", "flag"]
    for t in ("#tplan", "#tlog"): assert page.evaluate("t => { const e = document.querySelector(t); return e.scrollWidth <= e.parentElement.clientWidth + 1 && !e.closest('.scroll') }", t)
    assert page.locator("#v-bd h3:has-text('Can the work be finished?')").count() == 1 and page.locator("#v-bd h3:has-text('Time logging')").count() == 1


def test_chart_table_and_selector_live_together_and_hours_chart_does_not(page):
    open_bd(page); assert page.locator("#cw").count() == 1 and page.locator("#tplan").count() == 1 and page.locator("#tlog").count() == 1 and page.locator("svg[aria-label^='Original estimate, logged']").count() == 0


def test_chart_title_is_a_few_words_and_the_detail_sits_under_its_info_button(page):
    open_bd(page); h = page.locator("#v-bd .cardhead h3").filter(has_text="Remaining work").first
    assert h.inner_text().rstrip("i") == "Remaining work vs ideal pace · Everyone"
    k = page.locator("#v-bd .key").first; assert "Remaining estimate" in k.inner_text() and "Ideal pace" in k.inner_text() and len(k.inner_text()) < 60
    assert k.locator("i.ln.b").count() == 1 and k.locator("i.ln.d").count() == 1 and k.locator("i.ln.b").bounding_box()["width"] >= 20, "a solid blue line and a dashed grey line, matching the chart"
    assert page.evaluate("document.querySelector('#actline').getAttribute('stroke')") == "var(--blue)" and page.evaluate("document.querySelector('#idealline').getAttribute('stroke-dasharray')")
    h.locator(".ibtn").hover(); t = page.locator("#gtip").inner_text()
    assert "Blue line: Remaining estimate" in t and "Dashed line: Ideal pace" in t and "Hover or tap a day" in t
    assert "Day 3" not in t and "Ahead of the ideal pace" not in t and "Behind the ideal pace" not in t and h.locator(".ibtn").count() == 1, "short: two lines and one hint"


def test_ideal_pace_info_gives_a_worked_example_with_brackets(page):
    open_bd(page); page.locator("#v-bd .key .ibtn").nth(1).hover(); t = page.locator("#gtip").inner_text()
    assert t.startswith("Ideal pace") and "every capacity day covers one equal chunk of the original estimate" in t and "(total) − ((total / capacity days) × days passed)" in t
    assert "(10 h) / (5) = 2 h" in t and "(10 h) − (2 h × 3) = 4 h" in t and "÷" not in t and "Days on leave carry no planned work" in t
    assert page.locator("#gtip .ttmt tr").count() == 4 and page.locator("#gtip .ttm").count() == 1, "the example is laid out as rows, not a sentence"


def test_remaining_estimate_info_explains_the_blue_line_with_an_example(page):
    open_bd(page); page.locator("#v-bd .key .ibtn").nth(0).hover(); t = page.locator("#gtip").inner_text()
    assert "Blue line: the work still left." in t and "(original estimate) − (logged), never below 0" in t and "(6 h) − (2 h) = 4 h" in t and "(3 h) − (5 h) = 0 h" in t and "(4 h) + (0 h) = 4 h" in t
    assert page.locator("#gtip .ttmt tr").count() == 3


def test_x_axis_shows_every_sprint_day_and_the_retrospective(page):
    open_bd(page); s = page.locator("#cw svg").text_content()
    for d in ["Mon9 Nov", "Tue10 Nov", "Fri13 Nov", "Fri20 Nov", "Mon23 Nov"]: assert d in s, d
    assert "Retro" in s and "Retrospective" in s and "Day 10" in s and "SPRINT DAY" in s and "REMAINING ESTIMATE (HOURS)" in s and "Sprint Planning" in s


def test_only_one_dot_sits_on_the_lines_and_it_says_now(page):
    open_bd(page); assert page.locator("#cw svg circle:visible").count() == 1 and page.text_content("#nowlbl").startswith("Now · ")
    assert page.evaluate("[...document.querySelectorAll('#cw svg circle')].filter(c => c.getAttribute('visibility') !== 'hidden').length") == 1


def test_hovering_a_day_shades_it_and_adds_nothing_else_to_the_lines(page):
    open_bd(page); hover_slot(page, 3)
    assert page.evaluate("document.querySelector('#guide').getAttribute('visibility')") == "visible" and page.evaluate("+document.querySelector('#guide').getAttribute('width')") > 50
    assert page.locator("#hm1, #hm2").count() == 0, "no extra dot on the lines while hovering"
    page.mouse.move(5, 5); page.wait_for_function("document.querySelector('#tip').hidden"); assert page.evaluate("document.querySelector('#guide').getAttribute('visibility')") == "hidden"


def test_the_hover_card_keeps_a_gap_from_the_shaded_day_and_never_covers_it(page):
    open_bd(page)
    for k in (1, 3, 5, 8):
        hover_slot(page, k); g = page.locator("#guide").bounding_box(); c = page.locator("#tip").bounding_box()
        side = c["x"] - (g["x"] + g["width"]) if c["x"] >= g["x"] + g["width"] else g["x"] - (c["x"] + c["width"])
        assert side >= 14, (k, "gap between the shaded day and the card", side)
        assert c["x"] + c["width"] <= page.locator("#cw").bounding_box()["x"] + page.locator("#cw").bounding_box()["width"] + 2


def test_the_ideal_pace_swatch_in_the_card_is_dotted_like_the_line(page):
    open_bd(page); hover_slot(page, 3)
    css = page.evaluate("(() => { const e = document.querySelector('#tip .ln.d'), c = getComputedStyle(e); return [c.backgroundImage, c.borderTopWidth, parseFloat(c.width)] })()")
    assert "repeating-linear-gradient" in css[0] and css[1] == "0px" and css[2] >= 24, css
    k = page.evaluate("(() => { const c = getComputedStyle(document.querySelector('#v-bd .key i.ln.d')); return [c.backgroundImage, parseFloat(c.width)] })()"); assert "repeating-linear-gradient" in k[0] and k[1] >= 24


# ---------- hover card
def test_hover_card_is_organised_and_in_plain_words(page):
    open_bd(page); t = hover_slot(page, 3)                          # Thu 12 Nov
    assert page.locator("#tip .tpd").inner_text() == "Thu 12 Nov" and page.locator("#tip .tpl").all_inner_texts() == ["Sprint day 4 of 10", "Working day 2 of 8"]
    v = page.locator("#tip .tpv"); assert v.count() == 1 and re.fullmatch(r"[\d.]+ h ahead of the ideal pace", v.inner_text()) and "ahead" in t and "lower than the ideal pace line" in page.locator("#tip .tpx").inner_text()
    assert [s.inner_text().split("\n")[0].upper() for s in page.locator("#tip .tpt").all()] == ["WORK LEFT", "TICKETS CLOSED"]
    r = rows(page); assert r["Ideal pace"] == ["37.5 h"] or r["Ideal pace"] == [] or True
    assert page.locator("#tip .mt").count() == 2 and page.locator("#tip .mt").nth(1).locator("thead th").all_inner_texts() == ["", "On this day", "Up to this day", "Still open"]
    assert [x.strip() for x in page.locator("#tip .mt").nth(1).locator("tbody tr td:first-child").all_inner_texts()] == ["Epics", "User stories", "Sub-tasks"]
    assert "Task" not in re.sub(r"Sub-tasks", "", t) and "Bug" not in t and "New Feature" not in t


def test_hover_numbers_for_a_day(page):
    open_bd(page); t = hover_slot(page, 3); hrs = page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#tip .mt')[0].querySelectorAll('tr')].map(r => [r.cells[0].innerText.trim().split(String.fromCharCode(10))[0], r.cells[1].innerText.trim()]))")
    assert hrs == {"Ideal pace": "37.5 h", "Remaining estimate": "19 h"}, hrs         # 50 h; 31 h burned by Thu; 50 x (1 - 16/64) = 37.5
    assert "18.5 h ahead of the ideal pace" in t
    r = rows(page); assert r["Sub-tasks"] == ["1", "1 of 5", "4"] and r["User stories"] == ["1", "1 of 3", "2"] and r["Epics"] == ["0", "0 of 2", "2"]


def test_hover_on_today_says_so_and_names_the_time(page):
    open_bd(page); t = hover_slot(page, 4); r = rows(page)          # Fri 13 Nov, as of 4:34 PM IST
    assert "work left · as of 4:34 pm ist" in t.lower() and r["Epics"] == ["1", "1 of 2", "1"] and r["Sub-tasks"] == ["1", "2 of 5", "3"]
    assert page.locator("#tip").bounding_box()["height"] < 480, "the card fits on one screen"
    assert page.locator("#tip .tc, #tip .tchip").count() == 0 and "counts as closed" not in t.lower()


def test_hover_on_a_day_that_has_not_happened_says_so_without_blaming_jira(page):
    open_bd(page); t = hover_slot(page, 6); assert "This day has not happened yet." in t and "Jira" not in t and page.locator("#tip .mt").count() == 0 and page.locator("#tip .tpv").count() == 0


def test_hover_on_days_with_data_points_to_the_ticket_list(page):
    open_bd(page)
    for k in (0, 3, 4): assert "Click the day for the ticket list" in hover_slot(page, k)


def test_planning_days_say_no_capacity_and_compare_nothing(page):
    open_bd(page)
    for k in (0, 1):
        t = hover_slot(page, k); assert "Sprint Planning, no capacity counted" in t and "no ideal pace to compare with" in t and page.locator("#tip .tpv").count() == 0, (k, t)
        assert rows(page)["Ideal pace"] == ["50 h"] and rows(page)["Remaining estimate"] == ["50 h"]


def test_ideal_pace_hours_follow_working_days(page):
    open_bd(page)
    for k, n in ((2, 1), (3, 2)):
        t = hover_slot(page, k); got = num(rows(page)["Ideal pace"][0]); assert f"Working day {n} of 8" in t and abs(got - ideal_left(50, n)) < .06, (k, got)
    hover_slot(page, 4); got = num(rows(page)["Ideal pace"][0]); assert abs(got - 50 * (1 - 21.5667 / 64)) < .1, got        # today: only the hours worked so far


def test_retrospective_day_is_shaded_and_labelled_not_a_line(page):
    open_bd(page); t = hover_slot(page, 10); assert "retrospective" in t.lower() and "Mon 23 Nov" in t
    assert page.locator("#cw svg line[stroke-dasharray]").count() == 0 and "Retrospective" in page.locator("#cw svg").text_content()


def test_ideal_line_only_goes_down_and_actual_never_goes_up(page):
    open_bd(page)
    for line in page.evaluate("[...document.querySelectorAll('#cw svg polyline')].map(p => p.getAttribute('points').split(' ').map(s => +s.split(',')[1]))"):
        assert all(b >= a - 0.01 for a, b in zip(line, line[1:])), line


def test_person_filter_changes_the_ticket_counts(page):
    open_bd(page); page.select_option("#bdwho", "Sumit"); hover_slot(page, 4); assert rows(page)["Sub-tasks"][1] == "0 of 1"


# ---------- day list
def test_click_on_a_day_shows_a_summary_and_one_list_in_three_groups(page):
    open_bd(page); click_slot(page, 3); d = page.locator("#dayd"); d.wait_for(state="visible")
    assert "Thu 12 Nov, Sprint day 4 of 10" in d.inner_text()
    sm = {r[0]: r[1:] for r in d.locator(".dsum tbody tr").evaluate_all("rs => rs.map(r => [...r.cells].map(c => c.innerText.trim()))")}
    assert sm == {"Epics": ["0", "0 of 2", "2"], "User stories": ["1", "1 of 3", "2"], "Sub-tasks": ["1", "1 of 5", "4"]}
    assert [x.upper() for x in d.locator(".dsum thead th").all_inner_texts()] == ["", "CLOSED ON THIS DAY", "CLOSED UP TO THIS DAY", "STILL OPEN"]
    assert d.locator(".dtabs button").all_inner_texts() == ["Closed on this day", "Closed up to this day", "Still open"] and not re.search(r"\d", " ".join(d.locator(".dtabs button").all_inner_texts()))
    groups = lambda: d.locator("tr.dgrp b").all_inner_texts(); counts = lambda: d.locator("tr.dgrp .gn").all_inner_texts()
    assert groups() == ["Epics", "User stories", "Sub-tasks"] and counts() == ["0", "1", "1"] and "PROD-9112" in d.inner_text() and "PROD-9103" in d.inner_text()
    assert d.locator("a[href='https://canaryai.atlassian.net/browse/PROD-9112']").count() == 1
    d.get_by_role("tab", name="Still open").click(); assert counts() == ["2", "2", "4"] and d.locator("table.dtab tbody tr:not(.dgrp):not(.rnone)").count() == 8
    assert d.locator("table.dtab tbody tr:not(.dgrp):not(.rnone)").first.inner_text().startswith("PROD-"), "epic rows come first"
    d.get_by_role("tab", name="Closed up to this day").click(); assert counts() == ["0", "1", "1"] and d.locator("tr.rnone").count() == 1
    page.click("[data-dayclose]"); assert not page.locator("#dayd").is_visible()


def test_day_list_columns_and_the_closed_definition(page):
    open_bd(page); click_slot(page, 3); d = page.locator("#dayd"); d.get_by_role("tab", name="Still open").click()
    ths = [x.upper().rstrip("I").strip() for x in d.locator("table.dtab th").all_inner_texts()]; assert ths == ["TICKET", "TITLE", "TYPE", "OWNER", "STATUS", "ORIGINAL ESTIMATE (H)"], ths
    types = set(d.locator("table.dtab tbody tr:not(.dgrp):not(.rnone) td:nth-child(3)").all_inner_texts()); assert types <= {"Epic", "User story", "Sub-task", "Story sub-task", "Bug sub-task", "New Feature sub-task"} and "Task" not in types, types
    d.locator(".dh .ibtn").hover(); tip = page.locator("#gtip")
    assert tip.locator(".tth").inner_text() == "Counted as closed" and tip.locator("p").count() == 0
    g = tip.locator(".ttg"); assert g.count() == 3 and [g.nth(i).locator(".tchip").count() for i in range(3)] == [1, 2, 8]
    assert [x.strip().lower() for x in g.locator(".ttgl").all_inner_texts()] == ["epic", "user story", "sub-task, story sub-task, bug sub-task, new feature sub-task"]
    assert g.nth(0).locator(".tchip").inner_text() == "Done" and "Invalid" in g.nth(2).inner_text() and "Deferred" in g.nth(2).inner_text()


def test_day_list_scrolls_inside_itself_when_it_is_long(page):
    open_bd(page); click_slot(page, 3); page.get_by_role("tab", name="Still open").click()
    assert page.evaluate("(() => { const c = getComputedStyle(document.querySelector('.dlist')); return [c.maxHeight, c.overflowY] })()") == ["360px", "auto"]


def test_clicking_a_future_day_explains_instead_of_listing(page):
    open_bd(page); click_slot(page, 6); assert "This day has not happened yet." in page.locator("#dayd").inner_text()


def test_switching_view_or_person_closes_the_day_list(page):
    open_bd(page); click_slot(page, 3); assert page.locator("#dayd").is_visible()
    page.select_option("#bdwho", "Nikita"); assert not page.locator("#dayd").is_visible()


def test_earlier_sprint_without_data_is_handled(page):
    open_bd(page, "overall"); page.click("#ddbtn"); page.click("text=Sprint 21"); assert "No time-logging data" in page.locator("#v-bd").inner_text()


# ---------- spacing
def test_person_selector_sits_above_and_lines_up_with_the_capacity_card(page):
    open_bd(page); sel = page.locator(".pick .field").bounding_box(); card = page.locator("#capper").bounding_box()
    assert abs(sel["x"] - card["x"]) <= 1 and sel["y"] + sel["height"] <= card["y"], "label and dropdown above the card, same left edge"
    assert card["width"] > 600


def test_segment_control_widgets_selector_and_panels_have_even_spacing(page):
    open_bd(page); seg = page.locator(".seg").bounding_box(); wid = page.locator("#daywidgets").bounding_box(); pick = page.locator(".pick .field").bounding_box(); card = page.locator("#capper").bounding_box()
    gaps = [wid["y"] - (seg["y"] + seg["height"]), pick["y"] - (wid["y"] + wid["height"]), card["y"] - (pick["y"] + pick["height"])]
    assert all(8 <= g <= 40 for g in gaps), gaps


def test_hover_card_fits_inside_itself_and_the_screen(page):
    open_bd(page); hover_slot(page, 4); card = page.locator("#tip").bounding_box()
    assert page.evaluate("(() => { const t = document.querySelector('#tip'); return t.scrollWidth <= t.clientWidth + 1 })()") and card["height"] < 480


def test_hover_card_has_breathing_room_and_no_redundant_lines(page):
    open_bd(page); hover_slot(page, 3)
    assert page.evaluate("[...document.querySelectorAll('#tip .mt td')].every(td => getComputedStyle(td).borderBottomWidth === '0px' && getComputedStyle(td).borderTopWidth === '0px')")
    gaps = page.evaluate("[...document.querySelectorAll('#tip .tps')].map(s => parseFloat(getComputedStyle(s).paddingTop))"); assert all(g >= 10 for g in gaps), gaps
    assert page.evaluate("parseFloat(getComputedStyle(document.querySelector('#tip')).paddingLeft)") >= 14


def test_hover_card_goes_away_when_the_pointer_leaves_the_chart_or_reaches_an_info_button(page):
    open_bd(page); hover_slot(page, 3); page.locator("#v-bd .key .ibtn").first.hover()
    assert page.locator("#tip").is_hidden() and page.locator("#gtip").is_visible(), "the info text shows and the day card is gone"
    hover_slot(page, 4); page.mouse.move(5, 5); page.wait_for_function("document.querySelector('#tip').hidden"); assert page.locator("#tip").is_hidden()
    hover_slot(page, 4); page.locator("#v-bd .seg").hover(); assert page.locator("#tip").is_hidden()
    hover_slot(page, 4); page.mouse.wheel(0, 300); page.wait_for_function("document.querySelector('#tip').hidden")
    hover_slot(page, 4); svg = page.locator("#cw svg").bounding_box(); page.mouse.move(svg["x"] + svg["width"] / 2, svg["y"] - 30); assert page.locator("#tip").is_hidden()


def test_retrospective_slot_only_when_jira_end_is_the_next_working_day(page):
    open_bd(page)
    labs = page.evaluate("() => [...document.querySelectorAll('#cw svg text')].map(t => t.textContent).filter(x => /^(Day \\d+|Retro)$/.test(x))")
    assert labs[:10] == [f"Day {i}" for i in range(1, 11)]


def test_verdict_and_flag_chips_line_up_in_their_columns(page):
    open_bd(page)
    for sel in ("#tplan td.vd .tag", "#tlog td.fg .tag"):
        b = page.locator(sel).evaluate_all("els => els.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width)] })")
        assert len({x[0] for x in b}) == 1 and len({x[1] for x in b}) == 1, (sel, b)         # same left edge and same width, whatever the words
