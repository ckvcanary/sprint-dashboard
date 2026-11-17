"""Pull log page"""
import pytest

pytestmark = pytest.mark.guard
import re


def open_log(page):
    page.click('[data-tab="log"]'); page.wait_for_selector(".sched3")


def test_schedule_and_next_pull_are_clear(page):
    open_log(page); t = page.locator("#v-log").inner_text()
    assert "timers" in t.lower() and "Every day, twice a day" in t and "10:50 AM and 6:50 PM IST" in t and "10:45" not in t and "6:45" not in t
    tl = t.lower(); assert "next scheduled pull" in tl and "13 Nov, 6:50 PM IST" in t and "in 2 h 10 min" in t
    assert "latest scheduled pull" in tl and "13 Nov, 10:46 AM IST" in t and "not yet run" not in t.lower()


def test_counts_for_the_selected_sprint(page):
    open_log(page); c = {l.locator(".fl").evaluate("e => e.innerText").strip().rstrip("i").strip().title(): int(l.locator("b").inner_text()) for l in page.locator(".cnt .stat").all()}
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
    open_log(page); page.select_option("#plsel", "S22"); page.wait_for_selector(".plt"); assert page.locator(".plt").first.locator(".chip.na").count() == page.locator(".plt").first.locator(".chip").count() and "Scheduled pulls began" not in page.locator("#v-log").inner_text()


def test_fourteen_day_grid_is_gone_and_manual_runs_are_not_counted(page):
    open_log(page); t = page.locator("#v-log").inner_text()
    assert "next 14 days" not in t and page.locator(".cal").count() == 0 and "Manual refreshes" not in t
    assert "All sprints" not in t and page.locator(".plt").count() == 1, "one sprint at a time, chosen from the drop-down"


def test_next_pull_countdown_follows_the_clock_and_updates_every_minute(page):
    open_log(page); assert "in 2 h 10 min" in page.locator("#v-log").inner_text()
    page.clock.run_for(5 * 60 * 1000); page.wait_for_function("document.querySelector('#v-log').innerText.includes('in 2 h')")
    assert "in 2 h" in page.locator("#v-log").inner_text() and "in 2 h 10 min" not in page.locator("#v-log").inner_text()
    page.clock.run_for(2 * 3600 * 1000); page.wait_for_function("document.querySelector('#v-log').innerText.includes('Missed') || document.querySelector('#v-log').innerText.includes('min')")
    assert "in 2 h" not in page.locator("#v-log").inner_text()


def test_a_scheduled_pull_that_started_a_few_minutes_early_still_counts_for_its_slot(ctx_factory, mock):
    import json
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    for r in runs:
        if r["trigger"] == "schedule": r["at"] = "2026-11-13T05:12:06Z"      # 13 minutes before the 10:50 AM slot, as GitHub really did
    d.write_text(json.dumps(runs)); pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="log"]'); pg.wait_for_selector(".plt")
    assert "Pulled · 10:42 AM" in pg.locator(".plt").first.inner_text() and pg.locator(".cnt .stat.warn b").inner_text() == "0", "must not be shown as Missed"


def test_sprint_dropdown_lists_sprints_and_shows_one_at_a_time(page):
    open_log(page); sel = page.locator("#plsel"); opts = sel.locator("option").all_inner_texts()
    assert opts == ["Sprint 24", "Sprint 23", "Sprint 22", "Sprint 21", "Sprint 20"] and sel.input_value() == "S24"
    assert page.locator("#fsprint").is_hidden(), "the page has its own sprint drop-down, so the shared one is hidden here"
    assert "Sprint 24: scheduled pulls by working day" in page.locator("#v-log").inner_text()
    page.select_option("#plsel", "S23"); page.wait_for_selector(".plt"); t = page.locator("#v-log").inner_text()
    assert "Sprint 23: scheduled pulls by working day" in t and "Sprint 24: scheduled" not in t and page.locator("#plsel").input_value() == "S23"
    page.click('[data-tab="cap"]'); assert page.locator("#ddlab").inner_text() == "Sprint 23", "the choice is remembered across pages"


def test_refresh_budget_is_explained_in_plain_words(page):
    open_log(page); b = page.locator("#budget"); t = b.inner_text()
    assert page.inner_text("#bleft") == "92" and "refreshes left of 95" in t
    assert "Used 3" in t and "Left 92" in t and "Last 24 hours" in t and b.locator(".stopm").count() == 0
    assert abs(float(b.locator(".meter2 .u").get_attribute("style").split(":")[1].rstrip("%;")) - 3 / 95 * 100) < .05
    assert "Team refreshes" not in t and "Refresh stops at" not in t and "black marker" not in t and "Every pull publishes" not in t, "no paragraphs on the card"
    b.locator(".ibtn").hover(); g = page.locator("#gtip").inner_text(); assert "Button stops at" in g and "100 pulls in 24 hours" in g and "(95) − (pulls in 24 hours)" in g and "(95) − (3) = 92" in g


def test_the_accounts_behind_the_timers_are_named_with_their_owner_email(page):
    open_log(page); s = page.locator(".sched3 .stat").nth(3); t = s.inner_text()
    assert "GitHub and cron-job.org" in t and "Owner: chetan@canaryai.com" in t
    s.locator(".ibtn").hover(); g = page.locator("#gtip").inner_text(); assert "chetan@canaryai.com" in g and "No Claude job" in g and "cron-job.org" in g


def test_the_budget_counts_every_refresh_from_every_person(ctx_factory, mock):
    import json
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    for _ in range(21): runs.append({"at": "2026-11-13T10:00:00Z", "trigger": "manual", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": "ckvcanary"})
    d.write_text(json.dumps(runs)); pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="log"]'); pg.wait_for_selector("#budget")
    t = pg.locator("#budget").inner_text(); assert pg.inner_text("#bleft") == "71" and "Used 24" in t and "Left 71" in t


def test_status_dots_tell_upcoming_and_not_scheduled_apart(page):
    open_log(page); page.hover(".plt th:has-text('10:50 AM') .ibtn"); tip = page.locator("#gtip"); tip.wait_for()
    dots = page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#gtip .ttr')].map(r => { const d = r.querySelector('.td'), c = getComputedStyle(d); return [r.querySelector('.ttn').innerText.trim(), [d.className.replace('td ', ''), c.backgroundColor, c.borderTopWidth]] }))")
    assert dots["Upcoming"][0] == "up" and dots["Upcoming"][2] == "2px" and dots["Upcoming"][1] == "rgba(0, 0, 0, 0)", "Upcoming is a ring"
    assert dots["Not scheduled"][0] == "nil" and dots["Not scheduled"][2] == "0px" and dots["Not scheduled"][1] != "rgba(0, 0, 0, 0)", "Not scheduled is a grey dot"
    assert len({dots[k][1] for k in ("Pulled", "Failed", "Missed", "Not scheduled")}) == 4


def test_pull_log_cards_use_clean_accent_colours(page):
    open_log(page); cards = page.locator(".sched3 .stat")
    bg = cards.evaluate_all("els => els.map(e => getComputedStyle(e).backgroundImage + '|' + getComputedStyle(e).backgroundColor)")
    assert "linear-gradient" in bg[1] and all("linear-gradient" not in b for i, b in enumerate(bg) if i != 1), bg
    assert page.evaluate("getComputedStyle(document.querySelector('.sched3 .s2 b')).color") == "rgb(255, 255, 255)", "white text on the gradient card"
    tops = cards.evaluate_all("els => els.map(e => getComputedStyle(e).borderTopColor)"); assert len(set(tops)) >= 3


def test_open_pull_log_updates_when_a_new_pull_is_recorded(page, mock):
    """a pull taken while the Pull log is open (scheduled or not) shows up without reloading the page"""
    import json
    open_log(page); before = page.locator("#v-log").inner_text()
    f = mock.site / "data" / "runs.json"; runs = json.loads(f.read_text())
    runs.append({"at": "2026-11-13T11:08:00Z", "trigger": "schedule", "ok": False, "issues": 0, "sprint": "Sprint 24", "error": "Jira not reachable"}); f.write_text(json.dumps(runs))
    page.clock.run_for(61000); page.wait_for_timeout(600)
    after = page.locator("#v-log").inner_text(); assert after != before, "the Pull log did not change after a new run was recorded"
