"""Refresh progress card: a Claude-style word with an icon, one countdown with a buffer, never a second countdown"""
import pytest

pytestmark = pytest.mark.guard
import re
from conftest import ctl

WORDS = ['Tinkering', 'Clauding', 'Pondering', 'Brewing', 'Untangling', 'Noodling', 'Percolating', 'Simmering', 'Wrangling', 'Conjuring', 'Mulling', 'Synthesizing']


def test_default_countdown_has_a_buffer_of_75_seconds(ctx_factory, mock):
    pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    assert pg.evaluate("RF.expect") == 75


def test_word_icon_and_one_countdown_that_never_restarts(ctx_factory, mock):
    ctl(mock, "ok", 9); pg = ctx_factory(rf="{poll: 250, max: 20000, expect: 4}"); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn")
    pg.wait_for_selector("#rfprog", state="visible")
    assert pg.locator(".rfw .spark").is_visible() and pg.locator(".rfw .spark").bounding_box()["width"] > 8
    b = pg.locator("#rfprog").bounding_box(); assert b["x"] > 1440 / 2, "the card sits at the top right"
    seen, words = [], set()
    for _ in range(30):
        seen.append(pg.inner_text("#rfpt")); words.add(pg.inner_text("#rfptxt")); pg.wait_for_timeout(250)
        if not pg.locator("#rfprog").is_visible(): break
    assert words <= set(WORDS) and len(words) >= 2, words
    pg.wait_for_selector("#rfprog", state="hidden", timeout=20000)          # let the pretend refresh finish, so it cannot spill into the next test
    left = [int(re.match(r"(\d+) s left", x).group(1)) for x in seen if re.match(r"\d+ s left", x)]
    assert left == sorted(left, reverse=True), f"the countdown only goes down: {left}"
    if "Finishing up" in seen:
        after = seen[seen.index("Finishing up"):]; assert all(x in ("Finishing up", "") for x in after), f"no second countdown after it runs out: {after}"
    assert not any("longer" in x or re.search(r"\d+ s$", x) and "left" not in x for x in seen), seen


def test_status_line_after_the_buffer_is_calm(ctx_factory, mock):
    ctl(mock, "ok", 9); pg = ctx_factory(rf="{poll: 250, max: 20000, expect: 3}"); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click("#rfbtn")
    seen = []
    for _ in range(40):
        vis = pg.locator("#rfprog").is_visible(); txt = pg.inner_text("#rfpt") if vis else None; seen.append(txt)
        if txt == "Finishing up": break
        pg.wait_for_timeout(250)
    assert "Finishing up" in seen, seen
    assert "Still reading Jira" in pg.inner_text("#rfps") and int(pg.get_attribute("#rfpbarwrap", "aria-valuenow")) <= 95
