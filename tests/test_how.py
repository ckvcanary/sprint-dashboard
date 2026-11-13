"""How it works page: plain words for people who are not technical"""
import json, re


def open_how(page):
    page.click('[data-tab="how"]'); page.wait_for_selector(".hw")


INVENTED = re.compile(r"copy job|saved copy|access pass|website host|timetable|publishing pass|words you may see", re.I)


def test_flow_uses_the_real_names_with_arrowheads(page):
    open_how(page); t = page.locator(".flow").inner_text()
    for w in ["Jira", "GitHub Actions", "Reads the Jira REST API", "GitHub repository", "Commits JSON data", "Vercel", "Deploys the page", "Dashboard"]: assert w in t, w
    arr = page.locator(".arr svg"); assert arr.count() == 4
    for a in arr.all(): assert a.locator("path").count() == 2, "each arrow needs a shaft and a head"


def test_what_starts_github_actions_is_two_short_cards(page):
    open_how(page); s = page.locator(".startsec"); t = s.inner_text().lower()
    assert "what starts github actions" in t and "cron schedule" in t and "weekdays, twice a day" in t and "refresh button" in t and "anyone on the team" in t and s.locator("p").count() == 0


def test_the_page_never_uses_an_invented_name(page):
    open_how(page); page.click("summary:has-text('Accounts and renewal')"); page.click("summary:has-text('Refresh limits')"); page.click("summary:has-text('Links')")
    assert not INVENTED.search(page.locator(".hw").inner_text())
    for i in range(page.locator(".hw [data-tip]:visible").count()):
        page.locator(".hw [data-tip]:visible").nth(i).hover(); txt = page.locator("#gtip").inner_text(); assert not INVENTED.search(txt), (i, txt)


def test_accounts_and_renewal_use_real_terms_and_say_who_owns_what(page):
    open_how(page); page.click("summary:has-text('Accounts and renewal')"); t = page.locator(".hw").inner_text()
    for w in ["Cron schedule", "Jira API token", "GitHub token, Refresh button", "GitHub token, publishing", "12 Nov 2027", "ckvcanary", "chetan-3565", "No expiry"]: assert w in t, w


def test_info_buttons_show_a_tooltip_on_hover_and_never_expand_the_cards(page):
    open_how(page); btns = page.locator(".hw [data-tip]:visible"); assert btns.count() == 7
    h0 = [n.bounding_box()["height"] for n in page.locator(".node").all()]
    btns.nth(1).hover(); tip = page.locator("#gtip"); tip.wait_for(); assert "GitHub's servers, not on anyone's laptop" in tip.inner_text() and "Jira API token" in tip.inner_text() and page.locator("#gtip .ttr").count() == 2
    assert [n.bounding_box()["height"] for n in page.locator(".node").all()] == h0, "the cards must not grow"
    page.mouse.move(5, 5); tip.wait_for(state="hidden")
    btns.nth(6).hover(); assert "Vercel API route starts the GitHub Actions workflow" in tip.inner_text()


def test_tooltips_are_grey_and_not_white_like_the_page_is_dark(ctx_factory, mock):
    pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.click('[data-tab="how"]'); pg.locator(".hw [data-tip]").nth(0).hover()
    bg = pg.evaluate("getComputedStyle(document.querySelector('#gtip')).backgroundColor"); page_bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg != "rgb(255, 255, 255)" and bg != page_bg, (bg, page_bg)


def test_tooltip_also_opens_from_the_keyboard(page):
    open_how(page); page.locator(".hw [data-tip]").nth(0).focus(); assert page.locator("#gtip").is_visible()
    page.keyboard.press("Escape"); assert not page.locator("#gtip").is_visible()


def test_sections_are_collapsed_and_rows_have_room(page):
    open_how(page); assert page.locator(".acc details[open]").count() == 0
    flow = page.locator(".flow").bounding_box(); st = page.locator(".startsec h3").bounding_box()
    assert st["y"] - (flow["y"] + flow["height"]) >= 32
    chips = page.locator(".sc").bounding_box(); nxt = page.locator(".acc details").first.bounding_box(); assert nxt["y"] - (chips["y"] + chips["height"]) >= 24


def test_usage_limits_use_a_short_table_and_a_live_team_wide_meter(page):
    open_how(page); page.click("summary:has-text('Refresh limits')"); t = page.locator(".lim").inner_text()
    assert "3 of 100" in t and "Stops at 95 of 100 a day" in t and "One refresh per 2 minutes" in t and "No limit (public repository)" in t and "5,000 requests an hour" in t
    assert [x.upper() for x in page.locator(".lim th").all_inner_texts()] == ["RULE", "VALUE"] and "Limit" not in page.locator(".lim th").all_inner_texts() and "Reason" not in t and len(t) < 330


def test_the_refresh_count_is_the_same_for_everyone_not_per_browser(ctx_factory, mock):
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    for who in ("ckvcanary", "ckvcanary", "Scheduler", "ckvcanary"): runs.append({"at": "2026-11-13T10:00:00Z", "trigger": "manual" if who != "Scheduler" else "schedule", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": who})
    d.write_text(json.dumps(runs)); seen = []
    for _ in range(2):                                   # two separate browsers, two separate people
        pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.hover(".rfcard .ibtn"); pg.locator("#gtip").wait_for(); seen.append(re.search(r"(\d+) of 100", pg.locator("#gtip").inner_text()).group(1))
    assert seen == ["7", "7"], "3 earlier runs plus 4 added, counted for every person and every browser"


def test_links_are_grouped_by_what_they_are_for(page):
    open_how(page); page.click("summary:has-text('Links')"); heads = page.locator(".lgrp h4").all_inner_texts(); assert [h.upper() for h in heads] == ["USE", "BEHIND THE SCENES", "BACKUP"]
    hrefs = page.locator(".lgrp a").evaluate_all("els => els.map(e => e.href)")
    assert "https://sprint-dashboard-umber.vercel.app/" in hrefs and "https://vercel.com/chetan-3565/sprint-dashboard" in hrefs and "https://github.com/ckvcanary/sprint-dashboard" in hrefs and any(h.endswith("/actions/workflows/refresh.yml") for h in hrefs)
    use = page.locator(".lgrp > div").nth(0).inner_text(); assert "Team dashboard" in use and "Jira board" in use and "Vercel project" not in use
    for a in page.locator(".lgrp a").all(): assert a.get_attribute("target") == "_blank" and "noopener" in a.get_attribute("rel")


def test_no_personal_machine_or_name_is_mentioned(page):
    open_how(page); t = page.locator(".hw").text_content().lower()
    assert "chetan's" not in t and "chetan kumar" not in t and "my mac" not in t and "laptop" not in t.replace("no laptop needs to be on", "")


def test_no_secret_values_are_shown(page):
    open_how(page); t = page.locator(".hw").text_content()
    assert not re.search(r"github_pat_|ghp_|ATATT", t)


def test_intro_is_three_short_cards_and_the_page_is_short(page):
    open_how(page); g = page.locator(".glance > div"); assert g.count() == 3 and "Cron schedule" in g.nth(0).inner_text() and "Weekdays, 10:45 AM and 6:45 PM IST" in g.nth(0).inner_text()
    assert "Refresh button" in g.nth(1).inner_text() and "Hosted on Vercel" in g.nth(2).inner_text()
    t = page.locator(".hw").inner_text(); assert "Jira to this dashboard, with no one needed." in t and len(t) < 900, len(t)
    assert page.locator(".gk, .gloss").count() == 0, "no extra bullet list or glossary"


def test_cron_and_vercel_facts_sit_under_the_info_buttons(page):
    open_how(page); page.locator(".hw [data-tip]").nth(5).hover(); t = page.locator("#gtip").inner_text()
    assert "retried 30 and 60 minutes later" in t and "ckvcanary" in t and "No Claude job" in t
    page.locator(".hw [data-tip]").nth(3).hover(); tip = page.locator("#gtip").inner_text()
    assert "A few seconds of wait" in tip and "countdown timer with extra time built in" in tip and page.locator("#gtip .ttr").count() == 2
