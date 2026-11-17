"""Time logged each day (Burndown, Per person): cells against an independent model, date labels, the weekend column, the legend"""
import json
import pytest

pytestmark = [pytest.mark.guard, pytest.mark.math]
DH = 8


def grid_model(logs, E, cap_days, sd, wd0, ad):
    out, daily = {}, (E / cap_days if cap_days else 0)
    for d in sd:
        if d < wd0 or d > ad: out[d] = "na"
        else:
            lg = logs.get(d, 0); out[d] = "ok" if lg + .05 >= daily else "now" if d == ad else "warn" if lg > 0 else "bad"
    return out


def open_person_view(ctx_factory, mock, weekend=False, width=1440, touch=False):
    pg = ctx_factory(width=width, height=900 if width > 500 else 844, touch=touch)
    if weekend:
        def bd(route):
            r = route.fetch(); d = r.json(); d["S24"]["people"]["Nikita"]["logs"]["2026-11-07"] = 3.0; d["S24"]["people"]["Sumit"]["logs"]["2026-11-08"] = 8.0
            route.fulfill(response=r, body=json.dumps(d), content_type="application/json")
        pg.route("**/data/burndown.json*", bd)
    pg.goto(mock.url + "/index.html"); pg.wait_for_selector("[data-tab=bd]", state="attached"); pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('[data-tab=bd]').click()"); pg.click("[data-bdview=person]"); pg.wait_for_selector("#dgrid"); return pg


def test_cells_match_the_model(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock)
    data = pg.evaluate("() => { const s = BD.S24; return {sd: sprintDays(s), wd: workDays(s.win), people: s.people, ad: asOfIST().slice(0, 10)}; }")
    for r in pg.locator("#dgrid .dgr:not(.dgh)").all():
        name = r.locator(".dgn").inner_text().strip(); p = data["people"][name]; cells = r.locator(".dgc").all()
        exp = grid_model(p["logs"], p["E"], len(data["wd"]), data["sd"], data["wd"][0], data["ad"])
        for d, c in zip(data["sd"], cells):
            cls = c.get_attribute("class").split()[1]; assert cls == exp[d], (name, d, cls, exp[d])
            if cls in ("ok", "warn", "bad"): assert c.inner_text() == f"{round(p['logs'].get(d, 0), 1):g}", (name, d, c.inner_text())
        assert r.locator(".dgt").inner_text() == f"{round(sum(h for d, h in p['logs'].items() if d <= data['ad']), 1):g}"


def test_day_labels_are_weekday_and_date_not_letters(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock); heads = [h.replace("\n", " ") for h in pg.locator("#dgrid .dgh span").all_inner_texts()]
    assert heads[1:11] == ["Mon 9 Nov", "Tue 10 Nov", "Wed 11 Nov", "Thu 12 Nov", "Fri 13 Nov", "Mon 16 Nov", "Tue 17 Nov", "Wed 18 Nov", "Thu 19 Nov", "Fri 20 Nov"], heads
    assert heads[-1] == "Total logged"


def test_weekend_logs_have_their_own_labelled_column_and_the_total_still_adds_up(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock, weekend=True); heads = [h.replace("\n", " ") for h in pg.locator("#dgrid .dgh span").all_inner_texts()]
    assert "Weekend 7–8 Nov" in heads and "Other" not in " ".join(heads) and "+" not in "".join(heads), heads
    rows = {r.locator(".dgn").inner_text().strip(): r for r in pg.locator("#dgrid .dgr:not(.dgh)").all()}
    assert rows["Nikita"].locator(".dgo").inner_text() == "3" and rows["Sumit"].locator(".dgo").inner_text() == "8" and rows["Aditi"].locator(".dgo").inner_text() == ""
    cells = sum(float(c.inner_text() or 0) for c in rows["Nikita"].locator(".dgc").all() if c.inner_text() not in ("", "L")); assert abs(cells + 3 - float(rows["Nikita"].locator(".dgt").inner_text())) < .11


def test_legend_uses_pace_words_and_the_same_tags(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock); pg.locator("#dgrid .ibtn").scroll_into_view_if_needed(); pg.wait_for_timeout(400); pg.locator("#dgrid .ibtn").hover(); pg.wait_for_selector("#gtip:not([hidden])")
    t = pg.inner_text("#gtip").lower(); assert "on pace" in t and "behind pace" in t and "nothing logged" in t and "daily pace target" in t and "calculation" in t
    assert pg.locator("#gtip .tag").count() == 3 and "missing" not in t and "behind on logging" not in t


def test_phone_grid_fits_without_sideways_scroll(ctx_factory, mock):
    pg = open_person_view(ctx_factory, mock, weekend=True, width=390, touch=True); pg.wait_for_timeout(300)
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert pg.evaluate("[...document.querySelectorAll('#dgrid *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1); }).length") == 0
