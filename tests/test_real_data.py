"""Smoke and consistency checks on real data. Run with:  DASH_DATA=/path/to/folder-with-data python -m pytest tests/test_real_data.py
Skipped when DASH_DATA is not set."""
import json, os, pathlib, re, shutil, tempfile
import pytest
from conftest import ROOT
import mockserver

SRC = os.environ.get("DASH_DATA")
pytestmark = pytest.mark.skipif(not SRC, reason="set DASH_DATA to run against real data")
TABS = ["map", "cap", "bd", "log", "who", "how"]


@pytest.fixture(scope="module")
def real(browser):
    site = pathlib.Path(tempfile.mkdtemp()); pristine = pathlib.Path(tempfile.mkdtemp()) / "data"; shutil.copytree(pathlib.Path(SRC) / "data", pristine)
    (site / "index.html").write_text(re.sub(r"const REFRESH_URL = '[^']*';", "const REFRESH_URL = '/api/refresh';", (ROOT / "index.html").read_text(), 1))
    m = mockserver.Mock(site, pristine); m.reset(); yield m; m.srv.shutdown()


def data(real, n): return json.loads((real.site / "data" / f"{n}.json").read_text())


def test_data_files_agree_with_each_other(real):
    m, b, meta = data(real, "map"), data(real, "burndown"), data(real, "meta")
    assert m["asOf"] == meta["refreshedAt"], "map.json and meta.json must carry the same pull stamp"
    s24 = [s for s in m["stories"] if s["sprint"] == "S24"]; mt = {t["key"]: t for s in s24 for t in s["tasks"]}
    bt = {t["k"]: t for t in b["S24"]["tasks"]}
    assert set(mt) == set(bt), "every Sprint 24 task is in both the map and the burndown"
    assert abs(sum(t["h"] for t in mt.values()) - sum(t["e"] for t in bt.values())) < 0.01
    assert all(t["d"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["d"]) for t in bt.values())
    assert b["S24"]["start"] < b["S24"]["end"]


def test_closed_tickets_match_the_agreed_status_lists(real):
    m, b = data(real, "map"), data(real, "burndown")
    task_done = {"Technical Review", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Fixed", "Done"}; story_done = {"Deployed to UAT", "Deployed to Prod"}
    tstat = {t["key"]: t["s"] for s in m["stories"] for t in s["tasks"]}; sstat = {s["key"]: s.get("s") for s in m["stories"]}; estat = {e["key"]: e.get("s") for e in m["epics"]}
    for t in b["S24"]["tasks"]:
        st = tstat.get(t["k"], sstat.get(t["k"])); ok = st in (story_done if t.get("y") else task_done)
        assert bool(t["d"]) == ok, (t, st)
    for s in b["S24"]["stories"]: assert bool(s["d"]) == (sstat.get(s["k"]) in story_done), (s, sstat.get(s["k"]))
    for e in b["S24"]["epics"]: assert bool(e["d"]) == (estat.get(e["k"]) in story_done), (e, estat.get(e["k"]))


def test_every_page_loads_with_real_data_without_errors(ctx_factory, real):
    pg = ctx_factory(now=None); pg.goto(real.url + "/index.html"); pg.wait_for_selector("#map .card")
    for t in TABS: pg.click(f'[data-tab="{t}"]'); pg.wait_for_timeout(200)
    pg.click('[data-tab="map"]'); pg.click("#map .card.story >> nth=0"); pg.wait_for_selector("#drawer.on")
    assert not pg.errors, pg.errors


def test_no_card_shows_hours_with_real_data(ctx_factory, real):
    pg = ctx_factory(now=None); pg.goto(real.url + "/index.html"); pg.wait_for_selector("#map .card")
    for c in pg.locator("#map .card").all(): assert not re.search(r"\b\d+(\.\d+)?\s*h\b", c.inner_text()), c.inner_text()


def test_burndown_capacity_numbers_are_consistent(ctx_factory, real):
    pg = ctx_factory(now=None); pg.goto(real.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="bd"]'); pg.wait_for_selector(".capb")
    for view in ("overall", "person"):
        pg.click(f'[data-bdview="{view}"]'); pg.wait_for_selector(".capb"); t = pg.locator(".capb").first.inner_text()
        used = float(re.search(r"Used\s+([\d.]+) h", t).group(1)); left = float(re.search(r"Left\s+([\d.]+) h", t).group(1)); cap = float(re.search(r"of ([\d.]+) h", t).group(1))
        assert abs(used + left - cap) < 0.2, (view, t)
