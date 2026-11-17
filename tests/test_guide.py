"""Guided tour: a Guide button, steps that move through the pages, and a way to leave that returns the user to where they were"""
import pytest

pytestmark = pytest.mark.guard


def start(page):
    page.wait_for_function("D.stories.length > 0"); page.click("#guidebtn"); page.wait_for_selector("#gd #gdp")


def step(page): return page.locator("#gdp .gdn").inner_text().replace("\n", " ").capitalize()


def test_guide_button_opens_step_one_with_leave_back_and_next(page):
    assert page.locator("#guidebtn").inner_text() == "Guide"; start(page)
    assert step(page) == "Step 1 of 14" and page.locator("#gdp h4").inner_text() == "Welcome"
    assert page.locator("#gdp [data-gd]").all_inner_texts() == ["Leave guide", "Back", "Next"] and page.locator("#gdp [data-gd=back]").is_disabled()
    assert page.locator("#gdp .gdd i").count() == 14 and page.locator("#gdp .gdd i.on").count() == 1


def test_every_step_shows_its_page_highlights_it_and_keeps_the_card_inside_the_screen(page):
    start(page); seen = []
    for i in range(14):
        page.wait_for_timeout(150); assert step(page) == f"Step {i + 1} of 14"; seen.append(page.locator("#gdp h4").inner_text())
        card = page.locator("#gdp").bounding_box(); assert card["x"] >= 0 and card["y"] >= 0 and card["x"] + card["width"] <= 1440 and card["y"] + card["height"] <= 900, (i, card)
        if i:
            h = page.locator("#gdh").bounding_box(); assert h["width"] > 20 and h["height"] > 20 and h["x"] >= 0 and h["y"] >= 0, (i, h)
            assert len(page.locator("#gdp p").inner_text()) <= 140, "one or two short lines per step"
        if i < 13: page.click("#gdp [data-gd=next]")
    assert len(set(seen)) == 14 and page.locator("#gdp [data-gd=next]").inner_text() == "Done"
    pages = {"Map": "map", "Capacity": "cap", "Leave": "leave", "Pull log": "log", "How it works": "how"}
    for title, tab in pages.items():
        assert title in seen


def test_back_goes_to_the_earlier_step_and_page(page):
    start(page); page.click("#gdp [data-gd=next]"); page.click("#gdp [data-gd=next]"); page.click("#gdp [data-gd=next]"); page.click("#gdp [data-gd=next]"); page.wait_for_timeout(150)
    assert step(page) == "Step 5 of 14" and page.locator('[data-tab="map"]').get_attribute("aria-selected") == "true"
    page.click("#gdp [data-gd=next]"); page.wait_for_timeout(150); assert page.locator('[data-tab="cap"]').get_attribute("aria-selected") == "true"
    page.click("#gdp [data-gd=back]"); page.wait_for_timeout(150); assert step(page) == "Step 5 of 14" and page.locator('[data-tab="map"]').get_attribute("aria-selected") == "true"


def test_leaving_returns_to_the_page_the_view_and_the_person(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_selector("#tlog"); page.select_option("#bdwho", "Nikita"); start(page)
    for _ in range(6): page.click("#gdp [data-gd=next]"); page.wait_for_timeout(120)
    assert page.locator('[data-tab="leave"]').get_attribute("aria-selected") != "true" and page.locator('[data-tab="cap"]').get_attribute("aria-selected") != "true"
    page.click("#gdp [data-gd=leave]"); page.wait_for_timeout(250)
    assert page.locator("#gd").count() == 0 and page.locator('[data-tab="bd"]').get_attribute("aria-selected") == "true" and page.locator('[data-bdview="person"]').get_attribute("aria-selected") == "true"
    assert page.locator("#bdwho").input_value() == "Nikita"
    page.click('[data-tab="cap"]'); page.wait_for_selector(".capgrid"), "the page is fully usable again"


def test_escape_leaves_and_the_last_step_done_also_returns(page):
    start(page); page.keyboard.press("ArrowRight"); page.wait_for_timeout(100); assert step(page) == "Step 2 of 14"; page.keyboard.press("ArrowLeft"); page.wait_for_timeout(100); assert step(page) == "Step 1 of 14"
    page.keyboard.press("Escape"); page.wait_for_timeout(150); assert page.locator("#gd").count() == 0 and page.locator('[data-tab="map"]').get_attribute("aria-selected") == "true"
    start(page)
    for _ in range(13): page.click("#gdp [data-gd=next]"); page.wait_for_timeout(100)
    page.click("#gdp [data-gd=next]"); page.wait_for_timeout(200); assert page.locator("#gd").count() == 0 and page.locator('[data-tab="map"]').get_attribute("aria-selected") == "true" and not page.errors


def test_the_page_behind_the_guide_cannot_be_clicked(page):
    start(page); assert page.evaluate("(() => { const e = document.elementFromPoint(300, 60); return !!e.closest('#gd') })()"), "the overlay covers the page, so a stray click does nothing"
    page.click("#gdp [data-gd=leave]")


def test_the_guide_on_a_phone_is_a_sheet_with_big_buttons(ctx_factory, mock):
    pg = ctx_factory(width=390, height=844, touch=True); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#tabs"); pg.wait_for_function("D.stories.length > 0")
    b = pg.locator("#guidebtn").bounding_box(); assert b["width"] >= 44 and b["height"] >= 44 and b["x"] + b["width"] <= 390
    pg.click("#guidebtn"); pg.wait_for_selector("#gdp")
    for i in range(14):
        pg.wait_for_timeout(150); c = pg.locator("#gdp").bounding_box(); assert c["x"] >= 0 and c["x"] + c["width"] <= 390 and c["y"] + c["height"] <= 844 and c["y"] >= 0, (i, c)
        for btn in pg.locator("#gdp .btn").all():
            if btn.is_visible(): assert btn.bounding_box()["height"] >= 36, (i, btn.inner_text())
        assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1, i
        if i < 13: pg.click("#gdp [data-gd=next]")
    pg.click("#gdp [data-gd=leave]"); pg.wait_for_timeout(200); assert pg.locator("#gd").count() == 0
