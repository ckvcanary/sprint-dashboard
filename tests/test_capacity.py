"""Capacity page"""


def open_cap(page):
    page.click('[data-tab="cap"]'); page.wait_for_selector(".capgrid")


def test_no_sprint_heading_and_clear_legend(page):
    open_cap(page); t = page.locator("#v-cap").inner_text()
    assert "original estimate against capacity" not in t.lower()
    assert "Original estimate" in t and "Capacity: 64 h per person, less leave" in t


def test_capacity_number_is_printed_on_every_green_bar(page):
    open_cap(page); labels = page.locator("#v-cap svg text", has_text="64")
    assert labels.count() >= 1
    names = page.locator("#v-cap tbody tr:not(.tot)").count(); assert page.evaluate("[...document.querySelectorAll('#v-cap svg text')].filter(t=>t.textContent==='64').length") == names


def test_chart_and_table_panels_have_equal_height(ctx_factory, mock):
    page = ctx_factory(width=1700, height=1000); page.goto(mock.url + "/index.html"); page.wait_for_selector("#map .card"); page.click('[data-tab="cap"]'); page.wait_for_selector("#v-cap tbody tr"); a = page.locator(".capl").bounding_box(); b = page.locator(".capr").bounding_box()
    assert abs(a["height"] - b["height"]) <= 1, f"{a['height']} vs {b['height']}"
    assert a["height"] > 300, "the chart must not be shrunk"


def test_table_totals(page):
    open_cap(page); rows = {r.locator("td").nth(0).inner_text(): r.locator("td").all_inner_texts() for r in page.locator("#v-cap tbody tr").all()}
    assert rows["Nikita"][1] == "18" and rows["Sumit"][1] == "16" and rows["Team"][1] == "50" and rows["Team"][2] == "0" and rows["Team"][3] == "384"
    assert [x.upper().rstrip("I").strip() for x in page.locator("#v-cap thead th").all_inner_texts()] == ["NAME", "ORIGINAL ESTIMATE (H)", "LEAVE (H)", "CAPACITY (H)", "OVER (+) / UNDER (−) (H)"]


def test_leave_lowers_capacity_and_the_over_under_uses_it(ctx_factory, mock):
    import json
    pg = ctx_factory(); pg.route("**/data/leave.json*", lambda r: r.fulfill(body=json.dumps({"S24": [{"name": "Sumit", "date": "2026-11-13", "hours": 6}, {"name": "Sumit", "date": "2026-11-12", "hours": 3}, {"name": "Nikita", "date": "2026-11-10", "hours": 8}]}), content_type="application/json"))
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); open_cap(pg)
    rows = {r.locator("td").nth(0).inner_text(): r.locator("td").all_inner_texts() for r in pg.locator("#v-cap tbody tr").all()}
    assert rows["Sumit"][2] == "9" and rows["Sumit"][3] == "55" and rows["Sumit"][4].replace("\u2212", "-") == "-39 under capacity", rows["Sumit"]          # 64 h minus 9 h of leave; 16 h of work against 55 h of capacity
    assert rows["Nikita"][2] == "0" and rows["Nikita"][3] == "64", "leave on a planning day is not capacity leave"
    assert rows["Aditi"][2] == "0" and rows["Team"][2] == "9" and rows["Team"][3] == "375"
    labels = pg.evaluate("[...document.querySelectorAll('#v-cap svg text')].map(t => t.textContent)"); assert "55" in labels and labels.count("64") >= 5


def test_over_and_under_say_so_in_words(page):
    page.click('[data-tab="cap"]'); page.wait_for_selector("#v-cap tbody tr")
    cells = page.locator("#v-cap tbody td:last-child").all_inner_texts()
    assert cells and all(("over capacity" in c and c.strip().startswith("+")) or ("under capacity" in c and c.strip().startswith("\u2212")) or ("at capacity" in c and c.strip().startswith("0")) for c in cells), cells
