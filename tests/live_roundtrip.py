"""Live check that what changes in Jira shows up on the dashboard after Refresh. NOT part of the normal test run: it edits Jira and puts everything back.
Needs the preview running (python3 tests/serve_demo.py 8767) and the Jira login in ../.env.
Steps: 1) note the current Jira values  2) change assignee, story points and original estimate  3) click Refresh, check the dashboard
       4) restore Jira exactly  5) click Refresh, check the dashboard shows the original values again."""
import base64, json, os, pathlib, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
for p in (ROOT / ".env", ROOT.parent / ".env"):
    if p.exists():
        for l in p.read_text().splitlines():
            if "=" in l and not l.lstrip().startswith("#"): k, v = l.strip().split("=", 1); env.setdefault(k, v.strip("\"'"))
BASE, AUTH = env["JIRA_BASE"].rstrip("/"), base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8767/index.html"
EPIC, STORY, TASK, TASK_STORY = "PROD-3912", "PROD-3919", "PROD-3970", "PROD-3896"


def jira(path, body=None, method=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"Authorization": "Basic " + AUTH, "Content-Type": "application/json", "Accept": "application/json"}, method=method)
    with urllib.request.urlopen(r, timeout=60) as x: b = x.read(); return json.loads(b) if b else {}


def get(k):
    f = jira(f"/rest/api/3/issue/{k}?fields=assignee,customfield_10044,timeoriginalestimate,summary")["fields"]
    return {"assignee": (f["assignee"] or {}).get("accountId"), "name": (f["assignee"] or {}).get("displayName"), "sp": f["customfield_10044"], "oe": f["timeoriginalestimate"]}


def put(k, fields): jira(f"/rest/api/3/issue/{k}", {"fields": fields}, "PUT")


def read_ui(pg):
    """What the dashboard shows right now."""
    out = {}
    out["epic_pill"] = pg.evaluate("k => { const c = document.querySelector(`#map .card.epic[data-e='${k}']`); return c ? c.querySelector('.pill').innerText.trim() : null }", EPIC)
    out["story_card"] = pg.evaluate("k => { const c = document.querySelector(`#map .card.story[data-s='${k}']`); return c ? c.innerText.replace(/\\n/g,' | ') : null }", STORY)
    pg.click(f"#map .card.story[data-s='{TASK_STORY}']"); pg.wait_for_selector("#drawer.on"); pg.click(f"#drawer [data-t='{TASK}']"); pg.wait_for_timeout(300)
    out["task_drawer"] = pg.inner_text("#drawer").replace("\n", " | "); pg.keyboard.press("Escape")
    return out


def click_refresh(pg, wait_for_age=125):
    age = pg.evaluate("(Date.now() - Date.parse(META.refreshedAt)) / 1000")
    if age < wait_for_age: print(f"   waiting {int(wait_for_age - age)} s so the refresh is not skipped as too recent ...", flush=True); time.sleep(wait_for_age - age)
    pg.click("#rfbtn"); t = pg.locator(".tst.success, .tst.error, .tst.info"); t.first.wait_for(timeout=180000)
    return t.first.inner_text().replace("\n", " | "), t.first.get_attribute("class")


before = {k: get(k) for k in (EPIC, STORY, TASK)}
pathlib.Path("/private/tmp/roundtrip_before.json").write_text(json.dumps(before, indent=1))
print("Jira before:", json.dumps(before), flush=True)
ok = True
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True); c = b.new_context(viewport={"width": 1440, "height": 900}); c.add_init_script("localStorage.setItem('sd_auth', 'fa9304349b9d')")
    pg = c.new_page(); pg.goto(URL); pg.wait_for_selector("#map .card")
    base_ui = read_ui(pg); print("Dashboard before:", json.dumps(base_ui), flush=True)
    try:
        new_sp = int((before[STORY]["sp"] or 0) + 1); new_oe = before[TASK]["oe"] + 3600
        print(f"\nSTEP 1: in Jira, remove the assignee of {EPIC}, set {STORY} story points to {new_sp}, set {TASK} original estimate +1 h", flush=True)
        put(EPIC, {"assignee": None}); put(STORY, {"customfield_10044": new_sp}); put(TASK, {"timetracking": {"originalEstimate": f"{int(new_oe / 3600)}h" if new_oe % 3600 == 0 else f"{int(new_oe / 60)}m"}})
        print("   Jira now:", json.dumps({k: get(k) for k in (EPIC, STORY, TASK)}), flush=True)
        msg, cls = click_refresh(pg); print("   toast:", cls.split()[-1], "|", msg, flush=True)
        ui = read_ui(pg); print("   Dashboard now:", json.dumps(ui), flush=True)
        c1 = ui["epic_pill"] and "Unassigned" in ui["epic_pill"]; c2 = ui["story_card"] and (f"{new_sp} pts" in ui["story_card"] or f"{new_sp} pt" in ui["story_card"]); h_old = f"{before[TASK]['oe'] / 3600:g} h"; h_new = f"{new_oe / 3600:g} h"
        c3 = h_new in ui["task_drawer"]
        print(f"   CHECK assignee removed shows Unassigned: {'PASS' if c1 else 'FAIL'}; story points {new_sp}: {'PASS' if c2 else 'FAIL'}; task estimate {h_old} -> {h_new}: {'PASS' if c3 else 'FAIL'}", flush=True); ok &= bool(c1 and c2 and c3)
    finally:
        print(f"\nSTEP 2: restore Jira exactly", flush=True)
        put(EPIC, {"assignee": {"accountId": before[EPIC]["assignee"]}} if before[EPIC]["assignee"] else {"assignee": None})
        put(STORY, {"customfield_10044": before[STORY]["sp"]}); put(TASK, {"timetracking": {"originalEstimate": f"{int(before[TASK]['oe'] / 3600)}h" if before[TASK]["oe"] % 3600 == 0 else f"{int(before[TASK]['oe'] / 60)}m"}})
        after = {k: get(k) for k in (EPIC, STORY, TASK)}; print("   Jira restored:", json.dumps(after), flush=True)
        same = all(after[k] == before[k] for k in before); print("   Jira identical to before:", "PASS" if same else "FAIL", flush=True); ok &= same
    msg, cls = click_refresh(pg); print("   toast:", cls.split()[-1], "|", msg, flush=True)
    ui = read_ui(pg); print("   Dashboard after restore:", json.dumps(ui), flush=True)
    same_ui = ui == base_ui; print("   Dashboard shows the original values again:", "PASS" if same_ui else "FAIL", flush=True); ok &= same_ui
    b.close()
print("\nRESULT:", "ALL PASS" if ok else "SOMETHING FAILED"); sys.exit(0 if ok else 1)
