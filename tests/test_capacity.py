"""Capacity page"""


def open_cap(page):
    page.click('[data-tab="cap"]'); page.wait_for_selector(".capgrid")


def test_no_sprint_heading_and_clear_legend(page):
    open_cap(page); t = page.locator("#v-cap").inner_text()
    assert "original estimate against capacity" not in t.lower()
    assert "Original estimate" in t and "Capacity: 64 h per person (8 days × 8 hours)" in t


def test_capacity_number_is_printed_on_every_green_bar(page):
    open_cap(page); labels = page.locator("#v-cap svg text", has_text="64")
    assert labels.count() >= 1
    names = page.locator("#v-cap tbody tr:not(.tot)").count(); assert page.evaluate("[...document.querySelectorAll('#v-cap svg text')].filter(t=>t.textContent==='64').length") == names


def test_chart_and_table_panels_have_equal_height(page):
    open_cap(page); a = page.locator(".capl").bounding_box(); b = page.locator(".capr").bounding_box()
    assert abs(a["height"] - b["height"]) <= 1, f"{a['height']} vs {b['height']}"
    assert a["height"] > 300, "the chart must not be shrunk"


def test_table_totals(page):
    open_cap(page); rows = {r.locator("td").nth(0).inner_text(): r.locator("td").all_inner_texts() for r in page.locator("#v-cap tbody tr").all()}
    assert rows["Nikita"][1] == "18" and rows["Sumit"][1] == "16" and rows["Team"][1] == "50" and rows["Team"][2] == "384"
