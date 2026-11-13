"""Every status-like label has an (i) that lists all the values it can show, laid out as short rows or chips"""
import re


def hover(page, loc):
    loc.scroll_into_view_if_needed(); page.mouse.move(2, 2); page.wait_for_timeout(120); loc.hover(); tip = page.locator("#gtip"); tip.wait_for(); return tip


def names(tip): return [n.strip() for n in tip.locator(".ttn").all_inner_texts()]


def test_burndown_flag_column_lists_every_flag_and_covers_what_is_shown(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    tip = hover(page, page.locator("th:has-text('Flag') .ibtn")); flags = names(tip)
    assert flags == ["Not started", "Time log missing", "Behind on logging", "Cannot finish in time", "On track"] and tip.locator(".tth").inner_text() == "Flag"
    for tag in page.locator("#v-bd tbody .tag").all_inner_texts(): assert tag in flags, tag


def test_burndown_number_columns_explain_themselves(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    t = hover(page, page.locator("th:has-text('Missing log') .ibtn")); assert names(t) == ["Orange", "Red"] and "More than 8 h" in t.inner_text()
    t = hover(page, page.locator("th:has-text('Expected logged by now') .ibtn")); assert "11:00 to 19:00 IST" in t.inner_text()


def test_sprint_day_row_lists_its_values(page):
    page.click('[data-tab="bd"]'); page.wait_for_selector(".term"); t = hover(page, page.locator(".tk:has-text('Sprint day') .ibtn")); assert names(t) == ["Not started", "N of 10", "Sprint complete"]


def test_pull_log_columns_and_tiles_list_every_status(page):
    page.click('[data-tab="log"]'); page.wait_for_selector(".plt")
    for col in ("10:45 AM", "6:45 PM"):
        tip = hover(page, page.locator(f".plt th:has-text('{col}') .ibtn").first); assert names(tip) == ["Pulled", "Failed", "Missed", "Upcoming", "Not scheduled"], col
    shown = {re.sub(r"\s·.*", "", c) for c in page.locator(".plt tbody .chip").all_inner_texts()}; assert shown <= set(names(tip)), shown
    for tile in ("Pulled", "Failed", "Missed", "Upcoming", "Latest scheduled pull", "Next scheduled pull"):
        t = hover(page, page.locator(f".stat .fl:has-text('{tile}') .ibtn")); assert t.locator(".tth").inner_text() == tile and len(t.inner_text()) < 220


def test_day_panel_status_and_type_columns_list_all_values(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#cw svg")
    svg = page.locator("#cw svg").bounding_box(); page.mouse.click(svg["x"] + (60 + 4.5 / 11 * 924) / 1000 * svg["width"], svg["y"] + svg["height"] * .4); page.get_by_role("tab", name="Still open").click()
    tip = hover(page, page.locator("#dayd th:has-text('Status') .ibtn").first); g = tip.locator(".ttg")
    assert tip.locator(".tth").inner_text() == "Jira status" and g.count() == 4
    epics = g.nth(0).locator(".tchip").all_inner_texts(); stories = g.nth(1).locator(".tchip").all_inner_texts(); closed_tasks = g.nth(2).locator(".tchip").all_inner_texts(); opened = g.nth(3).locator(".tchip").all_inner_texts()
    assert epics == ["Done"] and stories == ["Deployed to UAT", "Deployed to Prod"] and closed_tasks == ["Technical Review", "Done", "Fixed", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Invalid", "Deferred"]
    assert not set(opened) & set(closed_tasks) and {"Triaged", "Reopened", "ACTIVE", "Ready for Development", "Duplicate", "Won't Fix"} <= set(opened), "every workflow status is either closed or listed as open"
    sts = page.evaluate("[...document.querySelectorAll('#dayd table')].flatMap(t => { const i = [...t.querySelectorAll('th')].findIndex(h => h.innerText.toUpperCase().startsWith('STATUS')); return [...t.querySelectorAll('tbody tr')].map(r => r.cells[i].innerText) })")
    for st in sts: assert st in epics + stories + closed_tasks + opened + ["–"], st
    t = hover(page, page.locator("#dayd th:has-text('Type') .ibtn").first); assert names(t) == ["Epic", "Story", "Task"]


def test_ticket_drawer_explains_status_where_it_appears(page):
    page.click('#map .card[data-s="PROD-9101"]'); page.wait_for_selector("#drawer.on")
    t = hover(page, page.locator("#drawer .lb:has-text('Tasks') .ibtn")); assert t.locator(".tth").inner_text() == "Jira status"
    page.mouse.move(5, 5); page.click('#drawer [data-t="PROD-9111"]'); t = hover(page, page.locator("#drawer .fact span:has-text('Status') .ibtn")); assert t.locator(".ttg").count() == 4


def test_last_refreshed_and_renewal_columns_have_their_info(page):
    t = hover(page, page.locator(".rfcard .ibtn")); assert t.locator(".tth").inner_text() == "Refresh limit" and "Green" in t.inner_text()
    page.mouse.move(5, 5); page.click('[data-tab="how"]'); page.click("summary:has-text('Accounts and renewal')"); t = hover(page, page.locator("th:has-text('Renew by') .ibtn"))
    assert names(t) == ["Never, Does not expire, No expiry", "A date"]


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
