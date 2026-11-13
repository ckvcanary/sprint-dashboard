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


def click_slot(page, k):
    svg = page.locator("#cw svg").bounding_box(); L, pw, slots, W = 60, 1000 - 60 - 16, 11, 1000
    page.mouse.click(svg["x"] + (L + (k + .5) / slots * pw) / W * svg["width"], svg["y"] + svg["height"] * .4)


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


def test_ideal_pace_says_when_work_formally_started_in_one_clear_line(page):
    open_bd(page); n = page.locator("#v-bd .panel .note").first.inner_text()
    assert n == "Ideal pace runs from Day 3 (Wed 11 Nov), when work formally started, to Day 10 (Fri 20 Nov). Days 1 to 2 were Sprint Planning."
    k = page.locator("#v-bd .key").first.inner_text(); assert "Remaining estimate (h)" in k and "Ideal pace" in k and len(k) < 60, "the legend stays short"
    page.locator("#v-bd .key .ibtn").nth(1).hover(); assert "even pace" in page.locator("#gtip").inner_text()


def test_x_axis_shows_every_sprint_day_and_the_retrospective(page):
    open_bd(page); s = page.locator("#cw svg").text_content()
    for d in ["Mon9 Nov", "Tue10 Nov", "Fri13 Nov", "Fri20 Nov", "Mon23 Nov"]: assert d in s, d
    assert "Retro" in s and "Retrospective" in s and "Day 10" in s and "SPRINT DAY" in s and "REMAINING ESTIMATE (HOURS)" in s and "Sprint Planning" in s


def test_hover_shows_tasks_closed_and_open_for_a_day(page):
    open_bd(page); t = hover_slot(page, 3)
    assert "Thu 12 Nov" in t and "Day 4 of 10" in t and "Tasks closed this day\n1" in t
    assert "Tasks closed so far\n1 of 5" in t and "Tasks still open\n4" in t and "User stories closed so far\n1 of 3" in t and "Epics closed so far\n0 of 2" in t and "Ideal pace" in t


def test_hover_says_what_closed_means_and_counts_epics_by_day(page):
    open_bd(page); t = hover_slot(page, 4)     # Fri 13 Nov: epic PROD-9002 reached Deployed to UAT
    assert "Epics closed so far\n1 of 2" in t and "Tasks closed so far\n2 of 5" in t
    tc = page.locator("#tip .tc"); groups = tc.locator(".tchips").all()
    assert [c.inner_text() for c in groups[0].locator(".tchip").all()] == ["Technical Review", "Done", "Fixed", "In Documentation", "Deployed to UAT", "Deployed to Prod"]
    assert [c.inner_text() for c in groups[1].locator(".tchip").all()] == ["Deployed to UAT", "Deployed to Prod"] and "story sub-tasks and bug sub-tasks" in tc.inner_text()


def test_info_button_beside_the_chart_title_defines_closed(page):
    open_bd(page); page.hover(".cardhead .ibtn"); tip = page.locator("#gtip"); tip.wait_for(); g = tip.locator(".ttg")
    assert tip.locator(".tth").inner_text() == "What counts as closed" and g.count() == 2 and g.nth(0).locator(".tchip").count() == 6 and g.nth(1).locator(".tchip").count() == 2
    assert "story sub-tasks and bug sub-tasks" in tip.inner_text()


def test_hover_on_a_day_that_has_not_happened_says_so_without_blaming_jira(page):
    open_bd(page); t = hover_slot(page, 6); assert "has not happened yet" in t and "Jira" not in t and "Tasks closed" not in t


def test_hover_on_days_with_data_names_the_pull_time(page):
    open_bd(page)
    for k in (0, 3, 4): assert "data as of 13 Nov, 4:34 PM IST" in hover_slot(page, k)


def test_retrospective_day_is_shaded_and_labelled_not_a_line(page):
    open_bd(page); t = hover_slot(page, 10); assert "Sprint retrospective" in t and "Mon 23 Nov" in t
    assert page.locator("#cw svg line[stroke-dasharray]").count() == 0 and "Retrospective" in page.locator("#cw svg").text_content()


def test_ideal_line_only_goes_down_and_actual_never_goes_up(page):
    open_bd(page)
    for line in page.evaluate("[...document.querySelectorAll('#cw svg polyline')].map(p => p.getAttribute('points').split(' ').map(s => +s.split(',')[1]))"):
        assert all(b >= a - 0.01 for a, b in zip(line, line[1:])), line


def test_person_filter_changes_the_task_counts(page):
    open_bd(page); page.select_option("#bdwho", "Sumit"); assert "Tasks closed so far\n0 of 1" in hover_slot(page, 4)


def test_click_on_a_day_lists_every_ticket_in_tabs(page):
    open_bd(page); click_slot(page, 3); d = page.locator("#dayd"); d.wait_for(state="visible")
    assert "Thu 12 Nov" in d.inner_text() and "Closed this day" in d.inner_text()
    assert d.locator("tbody tr").count() == 2 and "PROD-9112" in d.inner_text() and "PROD-9103" in d.inner_text()
    assert d.locator("a[href='https://canaryai.atlassian.net/browse/PROD-9112']").count() == 1
    d.get_by_role("tab", name="Still open").click(); tiles = {x.locator("span").inner_text(): x.locator("b").inner_text() for x in d.locator(".tile:not(.hrs)").all()}
    assert d.locator("tbody tr").count() == 8 and tiles == {"Epics open": "2", "User stories open": "2", "Tasks open": "4"}, tiles
    assert d.locator(".tc .tchip").count() == 8 and "tasks count as closed in" in d.inner_text().lower() and d.locator("tbody tr").first.inner_text().split("\t")[2] == "Epic", "epics are listed first"
    d.get_by_role("tab", name="Closed so far").click(); assert d.locator("tbody tr").count() == 2
    assert {x.locator("span").inner_text(): x.locator("b").inner_text() for x in d.locator(".tile:not(.hrs)").all()} == {"Epics closed": "0", "User stories closed": "1", "Tasks closed": "1"}
    page.click("[data-dayclose]"); assert not page.locator("#dayd").is_visible()


def test_day_panel_scrolls_inside_itself_when_the_list_is_long(page):
    open_bd(page); click_slot(page, 3); page.get_by_role("tab", name="Still open").click()
    assert page.evaluate("(() => { const c = getComputedStyle(document.querySelector('.dlist')); return [c.maxHeight, c.overflowY] })()") == ["360px", "auto"]


def test_clicking_a_future_day_explains_instead_of_listing(page):
    open_bd(page); click_slot(page, 6); assert "has not happened yet" in page.locator("#dayd").inner_text()


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
