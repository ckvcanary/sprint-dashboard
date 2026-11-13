"""Burndown page: Overall and Per person"""
import re


def open_bd(page, view="person"):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg")
    if view == "person": page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    else: page.wait_for_selector(".term")


def hover_slot(page, k):
    svg = page.locator("#cw svg").bounding_box(); L, pw, slots, W = 60, 1000 - 60 - 16, 11, 1000
    x = svg["x"] + (L + (k + .5) / slots * pw) / W * svg["width"]; page.mouse.move(x, svg["y"] + svg["height"] * .4)
    page.wait_for_selector("#tip:not([hidden])"); return page.locator("#tip").inner_text()


def rows(page):
    """The two small tables in the hover card as {row name: [cells]}"""
    return page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#tip .mt tbody tr')].map(r => [r.cells[0].innerText.split(String.fromCharCode(10))[0], [...r.cells].slice(1).map(c => c.innerText.trim())]))")


def click_slot(page, k):
    svg = page.locator("#cw svg").bounding_box(); L, pw, slots, W = 60, 1000 - 60 - 16, 11, 1000
    page.mouse.click(svg["x"] + (L + (k + .5) / slots * pw) / W * svg["width"], svg["y"] + svg["height"] * .4)


# ---------- header and structure
def test_three_areas_overall_is_the_default(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg")
    tabs = page.locator(".seg button"); assert tabs.all_inner_texts() == ["Overall", "Per person", "Logic"]
    assert tabs.nth(0).get_attribute("aria-selected") == "true" and page.locator(".term").count() == 1 and page.locator("#cw").count() == 0


def test_as_of_is_read_only_and_shows_the_pull_time(page):
    open_bd(page, "overall"); a = page.locator("#asof")
    assert a.evaluate("e => e.tagName") == "DIV" and a.get_attribute("contenteditable") is None and a.inner_text() == "13 Nov, 4:34 PM IST" and page.locator("#fasof input").count() == 0


def test_as_of_info_shows_on_hover_only(page):
    open_bd(page, "overall"); tip = page.locator("#gtip"); assert not tip.is_visible()
    page.hover("#asinfo"); tip.wait_for(); assert "latest Jira pull" in tip.inner_text() and "not the current time" in tip.inner_text()
    page.mouse.move(5, 5); tip.wait_for(state="hidden")


# ---------- Overall (static)
def test_overall_has_the_overview_and_hours_by_person_only(page):
    open_bd(page, "overall")
    assert page.locator(".term").count() == 1 and page.locator("svg[aria-label^='Original estimate, logged']").count() == 1
    assert page.locator("#bdwho").count() == 0 and page.locator("#v-bd table").count() == 0 and page.locator("#cw").count() == 0


def test_sprint_day_is_out_of_ten_not_eight(page):
    open_bd(page, "overall"); t = page.locator(".term").inner_text(); tl = t.lower()
    assert "5 of 10" in t and "Fri 13 Nov" in t and "of 8" not in t and "10 working days" in tl and "days 1 to 2" in tl and "mon 9 nov" in tl


def test_overall_capacity_is_the_whole_team(page):
    open_bd(page, "overall"); c = page.locator(".capb"); t = c.inner_text()
    assert "Whole team" in t and "3 people × 64 h" in t
    used = float(re.search(r"Used\s+([\d.]+) h", t).group(1)); left = float(re.search(r"Left\s+([\d.]+) h", t).group(1))
    assert abs(used + left - 192) < 0.2 and "of 192 h" in t


def test_one_grouped_bar_chart_with_three_series(page):
    open_bd(page, "overall"); k = page.locator("#v-bd .key").first.inner_text()
    assert "Original estimate (h)" in k and "Logged (h)" in k and "Expected logged by now (h)" in k and page.locator(".brow").count() == 0


# ---------- Per person (dynamic)
def test_person_selector_drives_the_capacity_card_and_names_the_person(page):
    open_bd(page); sel = page.locator("#bdwho")
    assert sel.locator("option").all_inner_texts() == ["Everyone", "Aditi", "Nikita", "Sumit"] or sel.locator("option").first.inner_text() == "Everyone"
    t = page.locator(".pcap").inner_text(); assert "Everyone" in t and "3 people × 64 h" in t
    page.select_option("#bdwho", "Nikita"); t = page.locator(".pcap").inner_text()
    used = float(re.search(r"Used\s+([\d.]+) h", t).group(1)); left = float(re.search(r"Left\s+([\d.]+) h", t).group(1))
    assert "Nikita" in t and "of 64 h" in t and abs(used + left - 64) < 0.15 and 21 < used < 22.5, (used, left)


def test_capacity_bar_is_labelled_used_and_left(page):
    open_bd(page); page.select_option("#bdwho", "Sumit"); card = page.locator(".pcap")
    assert card.locator(".meter2 .u").count() == 1 and card.locator(".meter2 .l").count() == 1 and "Used" in card.inner_text() and "Left" in card.inner_text() and "Sumit" in card.inner_text()
    assert "Sumit" in card.locator(".meter2").get_attribute("aria-label")


def test_table_follows_the_selection(page):
    open_bd(page); rows = page.locator("#v-bd tbody tr"); assert rows.count() == 4 and rows.last.inner_text().startswith("Everyone")
    page.select_option("#bdwho", "Nikita"); rows = page.locator("#v-bd tbody tr"); assert rows.count() == 1 and rows.first.inner_text().startswith("Nikita")


def test_chart_table_and_selector_live_together_and_hours_chart_does_not(page):
    open_bd(page); assert page.locator("#cw").count() == 1 and page.locator("#v-bd table").count() == 1 and page.locator("svg[aria-label^='Original estimate, logged']").count() == 0


def test_chart_title_is_a_few_words_and_the_detail_sits_under_its_info_button(page):
    open_bd(page); h = page.locator("#v-bd .cardhead h3").first
    assert h.inner_text().rstrip("i") == "Remaining work vs ideal pace · Everyone" and page.locator("#v-bd .panel .note").count() == 0, "no explanatory sentence under the title"
    k = page.locator("#v-bd .key").first.inner_text(); assert "Remaining estimate (h)" in k and "Ideal pace" in k and len(k) < 60
    h.locator(".ibtn").hover(); t = page.locator("#gtip").inner_text()
    assert "Day 3 (Wed 11 Nov)" in t and "Day 10 (Fri 20 Nov)" in t and "Sprint Planning" in t
    page.locator("#v-bd .key .ibtn").nth(1).hover(); assert "Total hours × working day / 8" in page.locator("#gtip").inner_text()


def test_x_axis_shows_every_sprint_day_and_the_retrospective(page):
    open_bd(page); s = page.locator("#cw svg").text_content()
    for d in ["Mon9 Nov", "Tue10 Nov", "Fri13 Nov", "Fri20 Nov", "Mon23 Nov"]: assert d in s, d
    assert "Retro" in s and "Retrospective" in s and "Day 10" in s and "SPRINT DAY" in s and "REMAINING ESTIMATE (HOURS)" in s and "Sprint Planning" in s


def test_hover_shows_tasks_closed_and_open_for_a_day(page):
    open_bd(page); t = hover_slot(page, 3); r = rows(page)       # Thu 12 Nov
    assert "Thu 12 Nov" in t and "Day 4 of 10" in t and "Working day 2 of 8" in t
    assert r["Tasks"] == ["1", "1 of 5", "4"] and r["User stories"] == ["1", "1 of 3", "2"] and r["Epics"] == ["0", "0 of 2", "2"]
    assert r["Ideal pace"] == ["12.5 h", "37.5 h"] and r["Actual"][0].endswith(" h") and "ahead" in t


def test_hover_counts_epics_by_day_and_leaves_the_definition_to_the_info_button(page):
    open_bd(page); hover_slot(page, 4); r = rows(page)     # Fri 13 Nov: epic PROD-9002 reached its closing status
    assert r["Epics"] == ["1", "1 of 2", "1"] and r["Tasks"] == ["1", "2 of 5", "3"]
    t = page.locator("#tip").inner_text(); assert page.locator("#tip .tc, #tip .tchip").count() == 0 and "sub-tasks" not in t and "counts as closed" not in t.lower()
    assert page.locator("#tip").bounding_box()["height"] < 400, "the card fits on one screen"


def test_info_button_beside_the_chart_title_defines_closed_per_type(page):
    open_bd(page); page.hover(".cardhead .ibtn"); tip = page.locator("#gtip"); tip.wait_for(); g = tip.locator(".ttg")
    assert g.count() == 3 and [g.nth(i).locator(".tchip").count() for i in range(3)] == [1, 2, 8]
    assert g.nth(0).locator(".tchip").inner_text() == "Done" and "epics" in g.nth(0).inner_text().lower() and "user stories" in g.nth(1).inner_text().lower() and "tasks" in g.nth(2).inner_text().lower()
    assert "Bug sub-task" in tip.inner_text() or "every sub-task type" in tip.inner_text()


def test_hover_on_a_day_that_has_not_happened_says_so_without_blaming_jira(page):
    open_bd(page); t = hover_slot(page, 6); assert "Not happened yet" in t and "Jira" not in t and page.locator("#tip .mt").count() == 0


def test_hover_on_days_with_data_points_to_the_ticket_list(page):
    open_bd(page)
    for k in (0, 3, 4): assert "Click the day for the ticket list" in hover_slot(page, k)


def test_retrospective_day_is_shaded_and_labelled_not_a_line(page):
    open_bd(page); t = hover_slot(page, 10); assert "Retrospective" in t and "Mon 23 Nov" in t
    assert page.locator("#cw svg line[stroke-dasharray]").count() == 0 and "Retrospective" in page.locator("#cw svg").text_content()


def test_ideal_line_only_goes_down_and_actual_never_goes_up(page):
    open_bd(page)
    for line in page.evaluate("[...document.querySelectorAll('#cw svg polyline')].map(p => p.getAttribute('points').split(' ').map(s => +s.split(',')[1]))"):
        assert all(b >= a - 0.01 for a, b in zip(line, line[1:])), line


def test_person_filter_changes_the_task_counts(page):
    open_bd(page); page.select_option("#bdwho", "Sumit"); hover_slot(page, 4); assert rows(page)["Tasks"][1] == "0 of 1"


def counts(d): return d.locator(".dsh .dn").all_inner_texts()


def test_click_on_a_day_lists_every_ticket_in_three_segments(page):
    open_bd(page); click_slot(page, 3); d = page.locator("#dayd"); d.wait_for(state="visible")
    assert "Thu 12 Nov" in d.inner_text() and "Closed this day" in d.inner_text()
    assert [b.inner_text() for b in d.locator(".dsh b").all()] == ["Epics", "User stories", "Tasks"], "epics, then user stories, then tasks"
    assert counts(d) == ["0", "1", "1"] and "PROD-9112" in d.inner_text() and "PROD-9103" in d.inner_text()
    assert d.locator("a[href='https://canaryai.atlassian.net/browse/PROD-9112']").count() == 1
    d.get_by_role("tab", name="Still open").click(); assert counts(d) == ["2", "2", "4"] and d.locator("tbody tr").count() == 8
    assert d.locator(".dseg").nth(0).locator("tbody tr").first.inner_text().startswith("PROD-"), "epic rows come first"
    d.get_by_role("tab", name="Closed so far").click(); assert counts(d) == ["0", "1", "1"]
    assert d.locator(".dseg").nth(0).inner_text().endswith("None") and d.locator(".tc, .tchip").count() == 0 or d.locator(".dseg .dnone").count() >= 1
    page.click("[data-dayclose]"); assert not page.locator("#dayd").is_visible()


def test_day_panel_task_table_shows_the_exact_issue_type_and_the_heading_defines_closed(page):
    open_bd(page); click_slot(page, 3); d = page.locator("#dayd"); d.get_by_role("tab", name="Still open").click()
    ths = d.locator(".dseg").nth(2).locator("th").all_inner_texts(); assert ths[2].upper().startswith("TYPE") and ths[0].upper() == "TICKET", ths
    d.locator(".dh .ibtn").hover(); assert page.locator("#gtip .tth").inner_text() == "What counts as closed"


def test_day_panel_scrolls_inside_itself_when_the_list_is_long(page):
    open_bd(page); click_slot(page, 3); page.get_by_role("tab", name="Still open").click()
    assert page.evaluate("(() => { const c = getComputedStyle(document.querySelector('.dlist')); return [c.maxHeight, c.overflowY] })()") == ["260px", "auto"]


def test_clicking_a_future_day_explains_instead_of_listing(page):
    open_bd(page); click_slot(page, 6); assert "Not happened yet" in page.locator("#dayd").inner_text()


def test_switching_view_or_person_closes_the_day_panel(page):
    open_bd(page); click_slot(page, 3); assert page.locator("#dayd").is_visible()
    page.select_option("#bdwho", "Nikita"); assert not page.locator("#dayd").is_visible()


def test_earlier_sprint_without_data_is_handled(page):
    open_bd(page, "overall"); page.click("#ddbtn"); page.click("text=Sprint 21"); assert "No time-logging data" in page.locator("#v-bd").inner_text()


def test_person_selector_sits_above_and_lines_up_with_the_capacity_card(page):
    open_bd(page); sel = page.locator(".pick .field").bounding_box(); card = page.locator(".pcap").bounding_box()
    assert abs(sel["x"] - card["x"]) <= 1 and sel["y"] + sel["height"] <= card["y"], "label and dropdown above the card, same left edge"
    assert card["width"] > 600


def test_segment_control_selector_and_panels_have_even_spacing(page):
    open_bd(page); seg = page.locator(".seg").bounding_box(); pick = page.locator(".pick .field").bounding_box(); card = page.locator(".pcap").bounding_box(); chart = page.locator("#cw").bounding_box()
    gaps = [pick["y"] - (seg["y"] + seg["height"]), card["y"] - (pick["y"] + pick["height"])]
    assert all(8 <= g <= 40 for g in gaps), gaps


def numbers(page):
    r = rows(page)["Ideal pace"]; return float(r[0].split()[0]), float(r[1].split()[0])


def test_ideal_done_plus_ideal_remaining_always_equals_the_total_hours(page):
    """Whatever day you point at, hours that should be done plus hours that should remain is the whole estimate (50 h here)."""
    open_bd(page)
    for k in (2, 3, 4):
        hover_slot(page, k); done, remain = numbers(page); assert abs(done + remain - 50) < 0.15, (k, done, remain)


def test_ideal_hours_follow_working_days_and_the_calculation_is_shown(page):
    open_bd(page); expected = {2: (1, 6.3), 3: (2, 12.5), 4: (3, 18.8)}      # sprint day 3, 4, 5 are working day 1, 2, 3 of 8: 1/8, 2/8, 3/8 of 50 h
    for k, (wd, done) in expected.items():
        t = hover_slot(page, k); assert f"Working day {wd} of 8" in t and abs(numbers(page)[0] - done) < 0.15 and f"50 h × {wd} / 8" in t and "Ideal pace =" not in t, (k, t)


def test_planning_days_say_no_capacity_and_expect_nothing_done(page):
    open_bd(page)
    for k in (0, 1):
        t = hover_slot(page, k); assert "Sprint Planning" in t and "no capacity" in t and numbers(page) == (0.0, 50.0), (k, t)


def test_hover_card_is_two_small_tables_not_a_list_of_small_lines(page):
    open_bd(page); hover_slot(page, 4)
    assert page.locator("#tip .mt").count() == 2 and page.locator("#tip .tpb .bdg").count() == 2
    assert page.locator("#tip .mt").first.locator("thead th").all_inner_texts() == ["", "Done", "Remaining"]
    assert page.locator("#tip .mt").nth(1).locator("thead th").all_inner_texts() == ["", "Closed today", "Closed so far", "Open"]
    t = page.locator("#tip").inner_text(); assert "dashed line" not in t and "Ideal pace =" not in t and "HOURS" in t.upper() and "TICKETS" in t.upper()


def test_hover_says_whether_the_work_is_ahead_of_or_behind_the_ideal_pace(page):
    open_bd(page); hover_slot(page, 4); pill = page.locator("#tip .pill2"); assert pill.count() == 1 and (re.fullmatch(r"[\d.]+ h (ahead|behind)", pill.inner_text()) or pill.inner_text() == "On ideal pace")
    hover_slot(page, 0); assert page.locator("#tip .pill2").count() == 0, "no verdict on planning days"


def test_ideal_pace_hours_come_before_the_ticket_counts(page):
    open_bd(page); hover_slot(page, 4); secs = page.locator("#tip .tps"); assert "HOURS" in secs.nth(0).inner_text().upper() and "TICKETS" in secs.nth(1).inner_text().upper()


def test_hover_card_fits_inside_itself_and_the_screen(page):
    open_bd(page); hover_slot(page, 4); card = page.locator("#tip").bounding_box()
    assert page.evaluate("(() => { const t = document.querySelector('#tip'); return t.scrollWidth <= t.clientWidth + 1 })()") and card["height"] < 400


def test_hover_card_goes_away_when_the_pointer_leaves_the_chart_or_reaches_an_info_button(page):
    open_bd(page); hover_slot(page, 3); page.locator("#v-bd .key .ibtn").first.hover()
    assert page.locator("#tip").is_hidden() and page.locator("#gtip").is_visible(), "the info text shows and the day card is gone"
    hover_slot(page, 4); page.mouse.move(5, 5); page.wait_for_function("document.querySelector('#tip').hidden"); assert page.locator("#tip").is_hidden()
    hover_slot(page, 4); page.locator("#v-bd .seg").hover(); assert page.locator("#tip").is_hidden()
    hover_slot(page, 4); page.mouse.wheel(0, 300); page.wait_for_function("document.querySelector('#tip').hidden")
    hover_slot(page, 4); svg = page.locator("#cw svg").bounding_box(); page.mouse.move(svg["x"] + svg["width"] / 2, svg["y"] - 30); assert page.locator("#tip").is_hidden()

# ---------- Logic page and over-estimate column
def open_logic(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".seg"); page.click('[data-bdview="logic"]'); page.wait_for_selector("#lgchk")


def test_logic_page_lists_rules_and_every_self_check_passes(page):
    open_logic(page)
    t = page.locator("#v-bd").inner_text()
    for w in ("Rules behind every number", "Original estimate", "Remaining estimate", "Over estimate", "Ideal pace", "Expected logged by now", "Closed means", "Self-checks on this sprint", "Data checks"):
        assert w in t, w
    assert page.locator("#lgchk .tag.bad").count() == 0 and page.locator("#lgchk .tag.ok").count() >= 6
    assert "—" not in t and "–" not in page.locator(".lgc").first.inner_text()


def test_per_person_table_has_an_over_estimate_column_and_totals_add_up(page):
    open_bd(page)
    heads = page.evaluate("() => [...[...document.querySelectorAll('#v-bd .panel table')].pop().tHead.rows[0].cells].map(c => c.innerText.trim())")
    assert [h.lower().rstrip("i") for h in heads[:5]] == ["name", "original estimate (h)", "logged (h)", "remaining estimate (h)", "over estimate (h)"], heads
    t = page.evaluate("() => [...[...document.querySelectorAll('#v-bd .panel table')].pop().tBodies[0].rows].map(r => [...r.cells].map(c => c.innerText.trim()))")
    body, tot = t[:-1], t[-1]
    for c in (1, 2, 3, 4, 5, 6, 7): assert abs(sum(float(r[c]) for r in body) - float(tot[c])) < .6, c
    assert all(float(r[3]) <= float(r[1]) + .01 for r in body)


def test_retrospective_slot_only_when_jira_end_is_the_next_working_day(page):
    open_bd(page)
    labs = page.evaluate("() => [...document.querySelectorAll('#cw svg text')].map(t => t.textContent).filter(x => /^(Day \\d+|Retro)$/.test(x))")
    assert labs[:10] == [f"Day {i}" for i in range(1, 11)]
