"""Every status-like label has an (i) that lists all the values it can show, laid out as short rows or chips"""
import pytest

pytestmark = pytest.mark.guard
import re


def hover(page, loc):
    loc.scroll_into_view_if_needed(); page.mouse.move(2, 2); page.wait_for_timeout(120); loc.hover(); tip = page.locator("#gtip"); tip.wait_for(); return tip


def arith_ok(text):
    import re
    found = re.findall(r"\(([\d.]+)(?: h)?\) [−-] \(([\d.]+)(?: h)?\) = ([\d.]+)", text); assert found, text
    return all(abs(float(a) - float(b) - float(c)) < .06 for a, b, c in found)


def names(tip): return [n.strip() for n in tip.locator(".ttn").all_inner_texts()]


def test_burndown_flag_column_lists_every_flag_and_covers_what_is_shown(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    tip = hover(page, page.locator("th:has-text('Flag') .ibtn")); flags = names(tip)
    assert flags == ["Not started", "On pace", "Behind pace", "Well behind pace"] and tip.locator(".tth").inner_text() == "Flag"
    for tag in page.locator("#tlog tbody .tag").all_inner_texts(): assert tag in flags, tag


def test_burndown_number_columns_explain_themselves(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    t = hover(page, page.locator("th:has-text('Pace gap') .ibtn")); assert names(t) == ["Up to 8 h", "More than 8 h"] and "Behind pace" in t.inner_text() and "(pace target) − (logged)" in t.inner_text()
    t = hover(page, page.locator("th:has-text('Pace target by now') .ibtn")); x = t.inner_text(); assert "Pace target = (E / D) × d" in x and "7.5 = 8 − 0.5" in x and "6.4 h" in x and "25.6 h" in x and "good to know" not in x.lower() and "half a day" not in x
    t = hover(page, page.locator("th:has-text('Verdict') .ibtn")); assert names(t) == ["Achievable", "Not achievable", "Completed", "Not completed"] and "(remaining estimate) − (time left)" in t.inner_text() and "calculation" in t.inner_text().lower() and arith_ok(t.inner_text())
    t = hover(page, page.locator("th:has-text('Leave') .ibtn")); assert "Lowers capacity only" in t.inner_text() and arith_ok(t.inner_text())


def test_hours_by_person_has_an_info_button_for_expected_log_by_now(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".gb svg")
    key = page.locator(".gb").locator("xpath=preceding-sibling::div[contains(@class,'key')]"); assert "Pace target by now (h)" in key.inner_text()
    t = hover(page, key.locator(".ibtn")); x = t.inner_text()
    assert t.locator(".tth").inner_text() == "Pace target by now (h)" and "Hours the original estimate predicts should be logged by now." in x and "Pace target = (E / D) × d" in x
    assert "7.5 = 8 − 0.5" in x and "6.4 h" in x and "25.6 h" in x and "good to know" not in x.lower() and "half a day" not in x


def test_sprint_day_and_capacity_day_widgets_explain_themselves(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector("#daywidgets")
    t = hover(page, page.locator("#wsprint .ibtn")); assert names(t) == ["Not started", "Day N of 10", "Complete"] and "The first 2 are Sprint Planning" in t.inner_text()
    t = hover(page, page.locator("#wcap .ibtn")); x = t.inner_text(); assert "(sprint day) − (planning days)" in x and "calculation" in x.lower() and arith_ok(x)


def test_pull_log_columns_and_tiles_list_every_status(page):
    page.click('[data-tab="log"]'); page.wait_for_selector(".plt")
    for col in ("10:50 AM", "6:50 PM"):
        tip = hover(page, page.locator(f".plt th:has-text('{col}') .ibtn").first); assert names(tip) == ["Pulled", "Failed", "Missed", "Upcoming", "Not scheduled"], col
    shown = {re.sub(r"\s·.*", "", c) for c in page.locator(".plt tbody .chip").all_inner_texts()}; assert shown <= set(names(tip)), shown
    for tile in ("Pulled", "Failed", "Missed", "Upcoming", "Latest scheduled pull", "Next scheduled pull"):
        t = hover(page, page.locator(f".stat .fl:has-text('{tile}') .ibtn")); assert t.locator(".tth").inner_text() == tile and len(t.inner_text()) < 120


def open_day(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg"); page.locator("#cw").scroll_into_view_if_needed(); page.wait_for_timeout(250)
    svg = page.locator("#cw svg").bounding_box(); page.mouse.click(svg["x"] + (60 + 4.5 / 11 * 924) / 1000 * svg["width"], svg["y"] + svg["height"] * .4); page.wait_for_selector("#dayd:not([hidden])"); page.get_by_role("tab", name="Still open").click()


def test_status_pop_up_has_two_buttons_with_the_real_jira_statuses(page):
    """Statuses taken from the PROD project's workflows in Jira; the second button lists what counts as closed."""
    open_day(page); tip = hover(page, page.locator("#dayd th:has-text('Status') .ibtn").first)
    assert tip.locator(".tth").inner_text() == "Jira status" and tip.locator(".jtabs button").all_inner_texts() == ["Statuses", "Counted as closed"]
    assert tip.locator(".jtabs button[aria-selected=true]").inner_text() == "Statuses"
    g = tip.locator(".ttg"); assert g.count() == 4
    heads = [x.strip().lower() for x in g.locator(".ttgl").all_inner_texts()]; assert heads == ["epic", "user story", "sub-task, story sub-task, new feature sub-task", "bug sub-task"], heads
    chips = lambda i: g.nth(i).locator(".tchip").all_inner_texts()
    assert chips(0) == ["Backlog", "In Progress", "In Testing", "In Documentation", "Done"]
    story = ["Backlog", "Research", "Spec_Completed", "Accepted by Developer", "Ready for Development", "In Progress", "Code_Review", "In Testing", "Technical Review", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Done", "On-Hold"]
    assert chips(1) == story and chips(2) == story and len(chips(3)) == 13 and {"New", "Triaged", "Fixed", "Invalid", "Deferred", "Won't Fix"} <= set(chips(3))
    assert "stays open" not in tip.inner_text().lower() and tip.locator("p").count() == 0, "no explanatory paragraphs"
    # the pop-up stays open while the pointer moves into it, and the second button shows what counts as closed
    box = tip.bounding_box(); page.mouse.move(box["x"] + 30, box["y"] + 20); page.wait_for_timeout(300); assert tip.is_visible()
    tip.locator(".jtabs button", has_text="Counted as closed").click(); page.wait_for_timeout(100); assert tip.is_visible()
    g = tip.locator(".ttg"); assert g.count() == 3 and tip.locator(".jtabs button[aria-selected=true]").inner_text() == "Counted as closed"
    assert g.nth(0).locator(".tchip").all_inner_texts() == ["Done"] and g.nth(1).locator(".tchip").all_inner_texts() == ["Deployed to UAT", "Deployed to Prod"]
    assert g.nth(2).locator(".tchip").all_inner_texts() == ["Technical Review", "Done", "Fixed", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Invalid", "Deferred"]
    tip.locator(".jtabs button", has_text="Statuses").click(); assert tip.locator(".ttg").count() == 4
    page.keyboard.press("Escape"); assert not tip.is_visible()


def test_every_status_on_the_page_is_one_the_popup_lists(page):
    open_day(page); tip = hover(page, page.locator("#dayd th:has-text('Status') .ibtn").first)
    known = set(tip.locator(".tchip").all_inner_texts())
    sts = page.evaluate("[...document.querySelectorAll('#dayd table.dtab')].flatMap(t => { const i = [...t.querySelectorAll('th')].findIndex(h => h.innerText.toUpperCase().startsWith('STATUS')); return [...t.querySelectorAll('tbody tr:not(.dgrp):not(.rnone)')].map(r => r.cells[i].innerText) })")
    for st in sts: assert st in known or st == "–", st
    t = hover(page, page.locator("#dayd th:has-text('Type') .ibtn").first); assert names(t) == ["Epic", "User story", "Sub-task"] and "Sub-task, Story sub-task, Bug sub-task, New Feature sub-task" in t.inner_text()


def test_the_closed_tip_next_to_the_day_has_no_sentences(page):
    open_day(page); t = hover(page, page.locator("#dayd .dh .ibtn")); assert t.locator(".tth").inner_text() == "Counted as closed" and t.locator("p").count() == 0 and t.locator(".ttnote").count() == 1 and "Technical Review is the last stage only for Jira management, U.S. team demos, reporting and documentation" in t.inner_text()
    assert [x.strip().lower() for x in t.locator(".ttgl").all_inner_texts()] == ["epic", "user story", "sub-task, story sub-task, bug sub-task, new feature sub-task"] and "first entered" not in t.inner_text()


def test_ticket_drawer_explains_status_where_it_appears(page):
    page.click('#map .card[data-s="PROD-9101"]'); page.wait_for_selector("#drawer.on")
    t = hover(page, page.locator("#drawer .lb:has-text('Tasks') .ibtn")); assert t.locator(".tth").inner_text() == "Jira status"
    page.mouse.move(5, 5); page.click('#drawer [data-t="PROD-9111"]'); t = hover(page, page.locator("#drawer .fact span:has-text('Status') .ibtn")); assert t.locator(".ttg").count() == 4


def test_last_refreshed_and_renewal_columns_have_their_info(page):
    t = hover(page, page.locator(".rfcard .ibtn")); assert t.locator(".tth").inner_text() == "Refresh limit" and "Green" in t.inner_text()
    page.mouse.move(5, 5); page.click('[data-tab="how"]'); page.click("summary:has-text('Accounts and renewal')"); t = hover(page, page.locator("th:has-text('Renew by') .ibtn"))
    assert names(t) == ["No expiry", "A date"]


def test_no_tooltip_is_an_unformatted_wall_of_text(page):
    """Every status tooltip is structured (heading plus rows or chips); any plain tooltip is a short sentence or two."""
    page.click('[data-tab="how"]'); page.wait_for_selector(".hw"); page.click("summary:has-text('Accounts and renewal')"); page.click("summary:has-text('Refresh limits')")
    seen = 0
    for i in range(page.locator("[data-tip]").count()):
        b = page.locator("[data-tip]").nth(i)
        if not b.is_visible(): continue
        tip = hover(page, b); seen += 1
        assert tip.locator(".tth").count() == 1 or len(tip.inner_text()) < 230, tip.inner_text()
        assert tip.locator(".ttr, .ttg, .ttp").count() >= 1
        for p in tip.locator(".ttp, .ttd").all_inner_texts(): assert len(p) <= 190, f"too long to scan: {p!r}"
    assert seen >= 9
