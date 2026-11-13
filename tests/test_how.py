"""How it works page: plain words for people who are not technical"""
import json, re


def open_how(page):
    page.click('[data-tab="how"]'); page.wait_for_selector(".hw")


JARGON = re.compile(r"\b(API|workflow|repository|cron|deploy\w*|token|endpoint|secret|commit|GH_TOKEN|JSON|CI)\b", re.I)


def test_flow_has_every_step_in_plain_words_with_arrowheads(page):
    open_how(page); t = page.locator(".flow").inner_text()
    for w in ["Jira", "Automatic copy job", "Saved copy", "Website host", "This dashboard", "Where our tickets are kept", "Copies the latest from Jira", "Puts the page online"]: assert w in t, w
    arr = page.locator(".arr svg"); assert arr.count() == 4
    for a in arr.all(): assert a.locator("path").count() == 2, "each arrow needs a shaft and a head"


def test_what_starts_an_update_is_explained_simply(page):
    open_how(page); t = page.locator(".startsec").inner_text()
    t = t.lower(); assert "what makes the dashboard update" in t and "on a timetable" in t.lower() and "weekdays, 10:45 am and 6:45 pm ist" in t and "someone presses refresh" in t and "anyone on the team" in t


def test_the_visible_page_and_every_hover_text_avoid_technical_jargon(page):
    open_how(page); visible = page.locator(".hw").inner_text(); found = sorted(set(m.group(0) for m in JARGON.finditer(visible))); assert not found, f"page still uses: {found}"
    for i in range(page.locator(".hw [data-tip]:visible").count()):
        page.locator(".hw [data-tip]:visible").nth(i).hover(); txt = page.locator("#gtip").inner_text(); found = sorted(set(m.group(0) for m in JARGON.finditer(txt))); assert not found, f"hover text {i} uses: {found}"


def test_collapsed_sections_are_also_in_plain_words_and_say_what_each_pass_is_for(page):
    open_how(page); full = page.locator(".hw").inner_html()
    for w in ["Who owns what", "Jira access pass", "Refresh button access pass", "Publishing pass", "12 Nov 2027", "ckvcanary", "chetan-3565", "How many times can we refresh?", "Words you may see"]: assert w in full, w
    assert not JARGON.search(re.sub(r"<[^>]+>", " ", page.locator(".gloss").inner_html()).replace("Access pass", "")), "glossary must stay plain"


def test_info_buttons_show_a_tooltip_on_hover_and_never_expand_the_cards(page):
    open_how(page); btns = page.locator(".hw [data-tip]:visible"); assert btns.count() == 7
    h0 = [n.bounding_box()["height"] for n in page.locator(".node").all()]
    btns.nth(1).hover(); tip = page.locator("#gtip"); tip.wait_for(); assert "On GitHub's computers, not on anyone's laptop" in tip.inner_text() and "read-only access pass" in tip.inner_text() and page.locator("#gtip .ttr").count() == 2
    assert [n.bounding_box()["height"] for n in page.locator(".node").all()] == h0, "the cards must not grow"
    page.mouse.move(5, 5); tip.wait_for(state="hidden")
    btns.nth(6).hover(); assert "keeps the access key safe" in tip.inner_text()


def test_tooltip_also_opens_from_the_keyboard(page):
    open_how(page); page.locator(".hw [data-tip]").nth(0).focus(); assert page.locator("#gtip").is_visible()
    page.keyboard.press("Escape"); assert not page.locator("#gtip").is_visible()


def test_sections_are_collapsed_and_rows_have_room(page):
    open_how(page); assert page.locator(".acc details[open]").count() == 0
    flow = page.locator(".flow").bounding_box(); st = page.locator(".startsec h3").bounding_box()
    assert st["y"] - (flow["y"] + flow["height"]) >= 32
    chips = page.locator(".sc").bounding_box(); nxt = page.locator(".acc details").first.bounding_box(); assert nxt["y"] - (chips["y"] + chips["height"]) >= 24


def test_usage_limits_are_explained_with_a_live_team_wide_meter(page):
    open_how(page); page.click("summary:has-text('How many times can we refresh?')"); t = page.locator(".lim").inner_text()
    assert "3 of 100" in t and "shared by the whole team, from every browser and every person" in t and "stops at 95" in t and "100 page updates a day" in t
    assert "No limit for us" in t and "backup copy of the dashboard always shows it" in t
    assert page.locator(".lim a[href='https://vercel.com/docs/limits']").count() == 1 and page.locator(".lim a[href='https://docs.github.com/en/actions/reference/limits']").count() == 1


def test_the_refresh_count_is_the_same_for_everyone_not_per_browser(ctx_factory, mock):
    d = mock.site / "data" / "runs.json"; runs = json.loads(d.read_text())
    for who in ("ckvcanary", "ckvcanary", "Scheduler", "ckvcanary"): runs.append({"at": "2026-11-13T10:00:00Z", "trigger": "manual" if who != "Scheduler" else "schedule", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": who})
    d.write_text(json.dumps(runs)); seen = []
    for _ in range(2):                                   # two separate browsers, two separate people
        pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); pg.hover(".rfcard .ibtn"); pg.locator("#gtip").wait_for(); seen.append(re.search(r"(\d+) of 100", pg.locator("#gtip").inner_text()).group(1))
    assert seen == ["7", "7"], "3 earlier runs plus 4 added, counted for every person and every browser"


def test_links_point_at_vercel_and_github(page):
    open_how(page); page.click("summary:has-text('Links')"); hrefs = page.locator(".links a").evaluate_all("els => els.map(e => e.href)")
    assert "https://sprint-dashboard-umber.vercel.app/" in hrefs and "https://vercel.com/chetan-3565/sprint-dashboard" in hrefs
    assert "https://github.com/ckvcanary/sprint-dashboard" in hrefs and any(h.endswith("/actions/workflows/refresh.yml") for h in hrefs)
    for a in page.locator(".links a").all(): assert a.get_attribute("target") == "_blank" and "noopener" in a.get_attribute("rel")


def test_no_personal_machine_or_name_is_mentioned(page):
    open_how(page); t = page.locator(".hw").text_content().lower()
    assert "chetan's" not in t and "chetan kumar" not in t and "my mac" not in t and "laptop" not in t.replace("not on anyone's laptop", "")


def test_no_secret_values_are_shown(page):
    open_how(page); t = page.locator(".hw").text_content()
    assert not re.search(r"github_pat_|ghp_|ATATT", t)


def test_intro_is_three_short_cards_not_a_paragraph(page):
    open_how(page); g = page.locator(".glance > div"); assert g.count() == 3 and "Refreshes by itself" in g.nth(0).inner_text() and "Weekdays, 10:45 AM and 6:45 PM IST" in g.nth(0).inner_text()
    assert "Refresh any time" in g.nth(1).inner_text() and "No computer needed" in g.nth(2).inner_text()
    t = page.locator(".hw").inner_text(); assert "This dashboard shows what is in Jira." in t and "automatic job" not in t


def test_good_to_know_and_account_owner_are_clear(page):
    open_how(page); t = page.locator(".hw").inner_text(); assert "nothing runs on Claude" in t and "company GitHub account ckvcanary" in t
    page.locator(".hw [data-tip]").nth(5).hover(); assert "tried again 30 and 60 minutes later" in page.locator("#gtip").inner_text()


def test_the_vercel_wait_is_explained_where_people_will_look(page):
    open_how(page); page.locator(".hw [data-tip]").nth(3).hover(); tip = page.locator("#gtip").inner_text()
    assert "A few seconds of wait" in tip and "countdown timer with a little extra time built in" in tip and page.locator("#gtip .ttr").count() == 2
    t = page.locator(".gk").inner_text(); assert "Why Refresh shows a timer" in t and "Vercel needs a few seconds" in t and "about 40 seconds" in t and "only after it has checked" in t
