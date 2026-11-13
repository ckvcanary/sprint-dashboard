"""Pull log page"""
import re


def open_log(page):
    page.click('[data-tab="log"]'); page.wait_for_selector(".sched3")


def test_schedule_and_next_pull_are_clear(page):
    open_log(page); t = page.locator("#v-log").inner_text()
    assert "Twice every weekday" in t and "10:45 AM and 6:45 PM IST" in t
    tl = t.lower(); assert "next scheduled pull" in tl and "13 Nov, 6:45 PM IST" in t and "in 2 h 5 min" in t
    assert "latest scheduled pull" in tl and "13 Nov, 10:46 AM IST" in t and "not yet run" not in t.lower()


def test_counts_for_the_selected_sprint(page):
    open_log(page); c = {l.locator(".fl").evaluate("e => e.firstChild.textContent").strip().title(): int(l.locator("b").inner_text()) for l in page.locator(".cnt .stat").all()}
    assert c == {"Pulled": 1, "Failed": 0, "Missed": 0, "Upcoming": 13}, c      # 14 planned slots from Fri 13 Nov to Mon 23 Nov


def test_rows_are_weekdays_of_the_sprint_only(page):
    open_log(page); rows = page.locator(".plt").first.locator("tbody tr")
    days = [r.locator("td").nth(0).inner_text() for r in rows.all()]
    assert days == ["Mon", "Tue", "Wed", "Thu", "Fri", "Mon", "Tue", "Wed", "Thu", "Fri", "Mon"] and "Sat" not in days and "Sun" not in days


def test_every_status_is_a_chip_including_not_scheduled(page):
    open_log(page); cells = page.locator(".plt").first.locator("tbody td:nth-child(n+3)")
    assert cells.count() == 22 and page.locator(".plt").first.locator("tbody .chip").count() == 22
    assert page.locator(".chip.na").count() == 8 and "Not scheduled" in page.locator(".chip.na").first.inner_text()


def test_status_chips_use_plain_professional_words(page):
    open_log(page); t = page.locator(".plt").first.inner_text()
    assert "Pulled · 10:46 AM" in t and "Upcoming" in t and "Not scheduled" in t
    assert not re.search(r"Before the schedule|grumpy|✓", t)


def test_selecting_an_earlier_sprint_explains_there_were_no_scheduled_pulls(page):
    open_log(page); page.click("#ddbtn"); page.click("text=Sprint 22"); assert "Scheduled pulls began on 13 Nov" in page.locator("#v-log").inner_text()


def test_fourteen_day_grid_is_gone_and_manual_runs_are_not_counted(page):
    open_log(page); t = page.locator("#v-log").inner_text()
    assert "next 14 days" not in t and page.locator(".cal").count() == 0 and "Manual refreshes from the Refresh button are not counted" in t
    assert page.locator(".plt").nth(1).inner_text().count("Sprint 24") == 1


def test_next_pull_countdown_follows_the_clock_and_updates_every_minute(page):
    open_log(page); assert "in 2 h 5 min" in page.locator("#v-log").inner_text()
    page.clock.run_for(5 * 60 * 1000); page.wait_for_function("document.querySelector('#v-log').innerText.includes('in 2 h')")
    assert "in 2 h" in page.locator("#v-log").inner_text() and "in 2 h 5 min" not in page.locator("#v-log").inner_text()
    page.clock.run_for(2 * 3600 * 1000); page.wait_for_function("document.querySelector('#v-log').innerText.includes('Missed') || document.querySelector('#v-log').innerText.includes('min')")
    assert "in 2 h" not in page.locator("#v-log").inner_text()


def test_a_scheduled_pull_that_started_a_few_minutes_early_still_counts_for_its_slot(ctx_factory, mock):
    import json
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    for r in runs:
        if r["trigger"] == "schedule": r["at"] = "2026-11-13T05:08:06Z"      # 7 minutes before the 10:45 AM slot, as GitHub really did
    d.write_text(json.dumps(runs)); pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="log"]'); pg.wait_for_selector(".plt")
    assert "Pulled · 10:38 AM" in pg.locator(".plt").first.inner_text() and pg.locator(".cnt .stat.warn b").inner_text() == "0", "must not be shown as Missed"
