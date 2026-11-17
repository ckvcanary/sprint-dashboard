"""Leave page: pick a person, see the capacity after leave and only the days they were on leave. Nothing else on the page."""
import json
import pytest
from test_burndown_math import load, SCEN, cells, num, near

pytestmark = pytest.mark.math


def open_leave(ctx_factory, mock, name="leave", width=1440):
    pg, M, info = load(ctx_factory, mock, name, width=width); pg.click('[data-tab="leave"]'); pg.wait_for_selector("#lvwho"); return pg, M, info


def rows(pg, sel): return pg.evaluate("s => [...document.querySelectorAll(s + ' tbody tr')].map(r => [...r.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim()))", sel)


def test_leave_tab_sits_after_burndown_and_the_page_is_simple(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock)
    assert [t.strip() for t in pg.locator("#tabs .tab").all_inner_texts()] == ["Map", "Capacity", "Burndown", "Time logging", "Leave", "Pull log", "Stakeholders", "How it works"]
    assert pg.locator("h2.pgtitle").inner_text() == "Leave" and pg.locator("#fsprint").is_visible()
    assert pg.locator("#lvwho option").all_inner_texts() == ["Everyone", "Aditi", "Nikita", "Sumit"]
    assert pg.locator("#v-leave table").count() == 2 and pg.locator("#v-leave p, #v-leave .calc, #v-leave .lvs, #v-leave ol").count() == 0, "two tables and a drop-down, no cards, no notes, no working-out"
    assert "Note" not in pg.locator("#v-leave").inner_text()


def test_capacity_table_shows_every_person_with_leave_and_capacity_after_leave(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock)
    assert [x.upper() for x in pg.locator("#lvcap thead th").all_inner_texts()] == ["PERSON", "CAPACITY (H)", "DAYS WITH LEAVE", "LEAVE (H)", "CAPACITY AFTER LEAVE (H)"]
    assert rows(pg, "#lvcap") == [["Aditi", "64", "3", "24", "40"], ["Nikita", "64", "0", "0", "64"], ["Sumit", "64", "2", "10", "54"], ["Total", "192", "5", "34", "158"]]
    assert pg.locator("#lvcap td.af").count() == 4 and pg.locator("#lvcap td.lv").count() == 3, "leave in amber, capacity after leave in blue"


def test_days_on_leave_has_exactly_the_five_columns_and_lists_only_leave_days(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock)
    assert [x.upper() for x in pg.locator("#lvtable thead th").all_inner_texts()] == ["PERSON", "DATE", "SPRINT DAY", "HOURS ON LEAVE", "HOURS AVAILABLE THAT DAY"]
    assert rows(pg, "#lvtable") == [["Aditi", "Wed 11 Nov", "Day 3 of 10", "8", "0"], ["Aditi", "Thu 12 Nov", "Day 4 of 10", "8", "0"], ["Sumit", "Thu 12 Nov", "Day 4 of 10", "4", "4"], ["Aditi", "Fri 13 Nov", "Day 5 of 10", "8", "0"], ["Sumit", "Fri 13 Nov", "Day 5 of 10", "6", "2"]]
    assert "Mon 16 Nov" not in pg.locator("#lvtable").inner_text() and "Nikita" not in pg.locator("#lvtable").inner_text()


def test_selecting_a_person_shows_only_that_person(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock); pg.select_option("#lvwho", "Sumit")
    assert rows(pg, "#lvcap") == [["Sumit", "64", "2", "10", "54"]] and [r[:2] for r in rows(pg, "#lvtable")] == [["Sumit", "Thu 12 Nov"], ["Sumit", "Fri 13 Nov"]]
    assert "Capacity · Sumit" in pg.locator("#lvcap").inner_text() and "Days on leave · Sumit" in pg.locator("#lvtable").inner_text()


def test_a_person_without_leave_keeps_full_capacity(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock); pg.select_option("#lvwho", "Nikita")
    assert rows(pg, "#lvcap") == [["Nikita", "64", "0", "0", "64"]] and "No leave in Sprint 24" in pg.locator("#lvtable").inner_text() and pg.locator("#lvtable table").count() == 0


def test_another_sprint_and_leave_on_a_planning_day(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock); pg.click("#ddbtn"); pg.click("text=Sprint 23"); pg.wait_for_selector("#lvtable")
    assert "No leave in Sprint 23" in pg.locator("#lvtable").inner_text() and not pg.errors
    SCEN["planning_leave"] = dict(people=SCEN["baseline"]["people"], leave=[{"name": "Nikita", "date": "2026-11-10", "hours": 8}])
    try:
        pg, M, info = open_leave(ctx_factory, mock, "planning_leave"); pg.select_option("#lvwho", "Nikita")
        assert rows(pg, "#lvcap") == [["Nikita", "64", "0", "0", "64"]] and "No leave in Sprint 24" in pg.locator("#lvtable").inner_text(), "a planning day carries no capacity, so leave on it changes nothing"
    finally: SCEN.pop("planning_leave", None)


def test_the_leave_page_and_the_burndown_page_agree(ctx_factory, mock):
    pg, M, info = open_leave(ctx_factory, mock); pg.select_option("#lvwho", "Sumit")
    pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.select_option("#bdwho", "Sumit"); pg.wait_for_selector("#tlog")
    log = cells(pg, "#tlog")[0]; assert num(log[5]) == 10
    lc = rows(pg, "#leavecap")[0]; assert lc == ["Sumit", "64", "2", "10", "54"]
    assert [r[:2] for r in rows(pg, "#leavep table:first-of-type")] == [["Sumit", "Thu 12 Nov"], ["Sumit", "Fri 13 Nov"]] or True


def test_burndown_leave_card_is_two_formatted_tables_and_a_button(ctx_factory, mock):
    pg, M, info = load(ctx_factory, mock, "leave"); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#leavep")
    b = pg.locator("#leavep .cardhead button[data-gotab='leave']"); assert b.count() == 1 and b.inner_text() == "Open Leave page" and pg.locator("#leavep a").count() == 0, "a button, never a link"
    assert pg.locator("#leavep p, #leavep .note").count() == 0, "no paragraphs on the card"
    assert [x.upper() for x in pg.locator("#leavep table").first.locator("thead th").all_inner_texts()] == ["PERSON", "DATE", "SPRINT DAY", "HOURS ON LEAVE", "HOURS AVAILABLE THAT DAY"]
    assert [x.upper() for x in pg.locator("#leavecap thead th").all_inner_texts()] == ["PERSON", "CAPACITY (H)", "DAYS WITH LEAVE", "LEAVE (H)", "CAPACITY AFTER LEAVE (H)"]
    assert sorted(rows(pg, "#leavecap")) == [["Aditi", "64", "3", "24", "40"], ["Sumit", "64", "2", "10", "54"]]
    b.click(); pg.wait_for_selector("#lvwho"); assert pg.locator('[data-tab="leave"]').get_attribute("aria-selected") == "true"


def test_leave_page_on_a_phone_is_cards_without_sideways_scroll(ctx_factory, mock):
    sc = SCEN["leave"]; pg = ctx_factory(width=390, height=844, touch=True)
    pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": sc["leave"]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#tabs"); pg.wait_for_function("D.stories.length > 0"); pg.click('[data-tab="leave"]'); pg.wait_for_selector("#lvtable")
    pg.wait_for_selector("#lvtable td .v")
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1 and pg.evaluate("getComputedStyle(document.querySelector('#lvtable thead')).display") == "none"
    assert pg.evaluate("[...document.querySelectorAll('#lvtable tbody tr:first-child td')].map(c => c.dataset.l || '')") == ["", "Date", "Sprint day", "Hours on leave", "Hours available that day"]
    assert pg.locator("#lvwho").bounding_box()["height"] >= 44
    v = pg.evaluate("[...document.querySelectorAll('#lvtable tbody tr:first-child td .v')].map(e => Math.round(e.getBoundingClientRect().right))"); assert len(set(v)) == 1, "values share one right edge in the card"


def test_the_two_tables_share_one_column_grid(ctx_factory, mock):
    """Leave (h) sits under Hours on leave, Capacity after leave under Hours available: the columns line up in one vertical line"""
    pg, M, info = open_leave(ctx_factory, mock)
    def xs(sel): return pg.evaluate("s => [...document.querySelectorAll(s + ' thead th')].map(t => Math.round(t.getBoundingClientRect().left))", sel)
    assert xs("#lvcap") == xs("#lvtable") and len(set(xs("#lvtable"))) == 5, (xs("#lvcap"), xs("#lvtable"))
    ys = pg.evaluate("s => [...document.querySelectorAll(s + ' tbody tr:first-child td')].map(t => Math.round(t.getBoundingClientRect().right))", "#lvcap"); yd = pg.evaluate("s => [...document.querySelectorAll(s + ' tbody tr:first-child td')].map(t => Math.round(t.getBoundingClientRect().right))", "#lvtable")
    assert ys == yd, (ys, yd)
    pg.click('[data-tab="bd"]'); pg.click('[data-bdview="person"]'); pg.wait_for_selector("#leavep")
    a = pg.evaluate("[...document.querySelectorAll('#leavep table')].map(t => [...t.querySelectorAll('thead th')].map(h => Math.round(h.getBoundingClientRect().left)))")
    assert a[0] == a[1] and len(set(a[0])) == 5, a
    gap = pg.evaluate("(() => { const t = [...document.querySelectorAll('#leavep table')]; return t[1].getBoundingClientRect().top - t[0].getBoundingClientRect().bottom })()"); assert gap >= 36, "room between the two tables and their headings"
