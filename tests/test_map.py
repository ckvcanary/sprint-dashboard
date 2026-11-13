"""Map page and ticket drawer"""
import re


def test_cards_show_story_points_only_never_hours(page):
    for c in page.locator("#map .card").all():
        txt = c.inner_text()
        assert not re.search(r"\b\d+(\.\d+)?\s*h\b", txt), f"hours on a card: {txt!r}"
    s = page.locator('#map .card[data-s="PROD-9101"]'); assert "8 pts" in s.inner_text()
    assert "1 pt" in page.locator('#map .card[data-s="PROD-9102"]').inner_text() and not re.search(r"(?<!\d)1 pts", page.locator("#map").inner_text())


def test_story_without_points_shows_no_estimate_pill(page):
    assert page.locator('#map .card[data-s="PROD-9103"] .pill.n').count() == 0


def test_epic_card_sums_points_and_uses_correct_plural(page):
    e = page.locator('#map .card.epic[data-e="PROD-9001"]').inner_text()   # S22 to S24 selected: 8 + 3
    assert "11 pts total" in e and " h" not in e
    assert page.locator('#map .card.epic[data-e="PROD-9001"] .pill.n').get_attribute("title") == "Total story points of all the user stories in this epic"


def test_story_drawer_shows_hours_and_highlights_facts(page):
    page.click('#map .card[data-s="PROD-9101"]'); d = page.locator("#drawer.on"); d.wait_for()
    facts = d.locator(".fact"); assert facts.count() == 4
    hi = d.locator(".fact.hi"); assert hi.count() == 2
    assert "18 h" in hi.nth(0).inner_text() and "original estimate" in hi.nth(0).inner_text().lower() and "8" in hi.nth(1).inner_text()
    assert "Nikita" in facts.nth(0).inner_text() and "Sprint 24" in d.inner_text()


def test_drawer_lists_attachment_names_only(page):
    page.click('#map .card[data-s="PROD-9101"]'); d = page.locator("#drawer.on")
    att = d.locator(".att"); assert att.inner_text().count("\n") >= 1
    assert "Technical approach.pdf" in att.inner_text() and "Screenshot 2026-11-12.png" in att.inner_text()
    assert att.locator("a").count() == 0, "files must not be linked or stored"
    assert "attachments (2)" in d.inner_text().lower() and "File names only" in d.inner_text()


def test_drawer_comment_history_newest_first_with_links(page):
    page.click('#map .card[data-s="PROD-9101"]'); cm = page.locator("#drawer.on .cm")
    assert cm.count() == 2 and "Latest comment" in cm.nth(0).inner_text() and "First comment" in cm.nth(1).inner_text()
    assert "Nikita" in cm.nth(0).inner_text() and "12 Nov" in cm.nth(0).inner_text()
    assert cm.nth(0).locator("a[href='https://example.com']").count() == 1


def test_task_drawer_shows_hours_status_comments_and_empty_attachments(page):
    page.click('#map .card[data-s="PROD-9101"]'); page.click('#drawer [data-t="PROD-9111"]')
    d = page.locator("#drawer.on"); assert "8 h" in d.inner_text() and "In Progress" in d.inner_text()
    assert "No files attached" in d.inner_text() and "Started the work" in d.inner_text()


def test_ticket_with_nothing_attached_says_so(page):
    page.click('#map .card[data-s="PROD-9102"]'); t = page.locator("#drawer.on").inner_text()
    assert "No files attached in Jira" in t and "No comments in Jira" in t


def test_epic_drawer_has_highlighted_facts(page):
    page.click('#map .card.epic[data-e="PROD-9002"]'); d = page.locator("#drawer.on")
    assert "total of its user stories" in d.inner_text().lower() and d.locator(".fact.hi").count() >= 1 and "Shared Microservices" in d.inner_text()


def test_drawer_closes_with_escape_and_close_button(page):
    page.click('#map .card[data-s="PROD-9101"]'); page.keyboard.press("Escape"); page.wait_for_selector("#drawer:not(.on)")
    page.click('#map .card[data-s="PROD-9101"]'); page.click("#drawer [data-close]"); page.wait_for_selector("#drawer:not(.on)")


def test_legend_has_clear_gap_from_the_sprint_headings(page):
    lg = page.locator("#legend").bounding_box(); hd = page.locator("#map .colh").first.bounding_box()
    assert hd["y"] - (lg["y"] + lg["height"]) >= 12, "legend must not sit tight above the sprint headings"


def test_sprint_selector_offers_only_sprints_20_to_24(page):
    page.click("#ddbtn"); assert [o.strip() for o in page.locator(".ddopt").all_inner_texts()] == [f"Sprint {n}" for n in range(20, 25)]


def test_no_dates_in_the_sprint_selector(page):
    page.click("#ddbtn"); assert not re.search(r"\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", page.locator("#ddpop").inner_text())
