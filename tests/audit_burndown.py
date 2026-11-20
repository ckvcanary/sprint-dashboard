"""Logic audit of the Burndown page: every number the page shows is re-derived from Jira, with its own code, and compared with what the page displays.
Run against a deployed page or a preview (read only apart from the optional --refresh, which uses the page's own Refresh button path):
    python3 tests/audit_burndown.py https://sprint-dashboard-umber.vercel.app [--refresh]
Needs the Jira login (.env) and Playwright with Chrome. The browser is signed in by setting the same marker the page keeps after the password step, so the password is not needed here.

Three layers:  Jira  ->  data files (refresh.py)  ->  what the page shows (template.html).
  A. data files against an independent read of Jira (estimates, logged hours by day, burn, over estimate, closed dates)
  B. the page's tables, bars, chart hover, day panel and capacity bars against numbers computed from the rules, not from the page's own code
  C. edge cases: other sprints' day axis, retrospective day, over-estimate, closed-before-sprint, empty states"""
import base64, collections, datetime as dt, json, pathlib, re, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
for p in (ROOT / ".env", ROOT.parent / ".env"):
    if p.exists():
        for l in p.read_text().splitlines():
            if "=" in l and not l.lstrip().startswith("#"): k, v = l.strip().split("=", 1); env.setdefault(k, v.strip("\"'"))
BASE, AUTH = env["JIRA_BASE"].rstrip("/"), base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8767").rstrip("/")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CAP, DH, WH0 = 64, 8, 11
SPRINT_ID, START, WIN = 1195, "2026-11-09", ("2026-11-11", "2026-11-20")
TASK_DONE = {"Technical Review", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Fixed", "Done", "Invalid", "Deferred"}; STORY_DONE = {"Deployed to UAT", "Deployed to Prod"}; EPIC_DONE = {"Done"}
first = lambda a: a["displayName"].split()[0] if a else None
res = []


def check(name, ok, detail=""):
    res.append(ok); print(("PASS  " if ok else "FAIL  ") + name + (("  " + str(detail)) if detail else ""), flush=True)


def jira(path, body=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"Authorization": "Basic " + AUTH, "Content-Type": "application/json", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=90))


import re as _re
_ND = _re.compile(r"\b(document|documentation|docs?|demos?|jira|reporting|retrospective|presentation|deck|training|knowledge transfer|u\.?s\.? team)\b", _re.I)
nondev = lambda x: (x["fields"].get("assignee") or {}).get("displayName", "").split(" ")[0] == "Chetan" or bool(_ND.search(x["fields"].get("summary") or ""))      # Technical Review closes only documentation, demo, reporting and Jira work


def search(jql, fields, expand=None):
    out, tok = [], None
    while True:
        b = {"jql": jql, "fields": fields, "maxResults": 100}
        if expand: b["expand"] = expand
        if tok: b["nextPageToken"] = tok
        d = jira("/rest/api/3/search/jql", b); out += d["issues"]; tok = d.get("nextPageToken")
        if d.get("isLast", True) or not tok: return out


def get(p): return json.load(urllib.request.urlopen(urllib.request.Request(URL + p + "?v=%d" % time.time(), headers={"User-Agent": "audit"}), timeout=30))


# ---------------------------------------------------------------- optional: one real refresh, so Jira and the data files are from the same moment
if "--refresh" in sys.argv:
    before = get("/data/meta.json")["refreshedAt"]
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(before.replace("Z", "+00:00"))).total_seconds()
    if age < 125: time.sleep(125 - age)
    urllib.request.urlopen(urllib.request.Request(URL + "/api/refresh", method="POST", data=b"", headers={"Origin": URL, "User-Agent": "audit"}))
    for _ in range(80):
        time.sleep(4)
        try:
            if get("/data/meta.json")["refreshedAt"] != before: time.sleep(25); break      # wait for the deployment of the new data to go live
        except Exception: pass
meta, bd = get("/data/meta.json"), get("/data/burndown.json"); S = bd["S24"]
print("Data from", meta["refreshedAt"], "on", URL, "\n")

# ---------------------------------------------------------------- independent read of Jira
F = ["summary", "status", "assignee", "issuetype", "parent", "timeoriginalestimate", "worklog", "created", "updated", "statuscategorychangedate"]
iss = {x["key"]: x for x in search(f"project = PROD AND sprint = {SPRINT_ID} AND issuetype != Epic", F, "changelog")}
parents = {x["fields"]["parent"]["key"] for x in iss.values() if x["fields"].get("parent")}
leaf = [k for k in iss if k not in parents]
is_story = lambda x: (not x["fields"]["issuetype"].get("subtask")) and x["fields"]["issuetype"]["name"] in ("Story", "Epic")


def logs_of(x):
    w = x["fields"]["worklog"]
    return w["worklogs"] if w["total"] <= len(w["worklogs"]) else jira(f"/rest/api/3/issue/{x['key']}/worklog?maxResults=1000")["worklogs"]


def closed_day(x, ds):
    cur = x["fields"]["status"]["name"]
    if cur not in ds: return None
    since = None
    for h in sorted((x.get("changelog") or {}).get("histories", []), key=lambda h: h["created"]):
        for it in h["items"]:
            if it.get("field") == "status": since = (since or h["created"]) if it.get("toString") in ds else None
    f = x["fields"]; t = since or f.get("statuscategorychangedate") or f["updated"]
    return dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(IST).date().isoformat()


P = collections.defaultdict(lambda: {"E": 0.0, "logs": collections.defaultdict(float), "burn": collections.defaultdict(float), "over": 0.0})
task_close, over, noest, unassigned = {}, [], [], []
for k in leaf:
    x = iss[k]; f = x["fields"]; raw = (f.get("timeoriginalestimate") or 0) / 3600; L = logs_of(x)
    pre = sum(l["timeSpentSeconds"] / 3600 for l in L if l["started"][:10] < START); e = max(0.0, raw - pre)
    if not f.get("assignee"): unassigned.append(k); continue
    if not raw: noest.append(k)
    who, left, lg = first(f["assignee"]), e, 0.0
    for l in sorted((l for l in L if START <= l["started"][:10] <= WIN[1]), key=lambda l: l["started"][:10]):
        d, h = l["started"][:10], l["timeSpentSeconds"] / 3600; P[first(l["author"])]["logs"][d] += h; lg += h
        c = min(h, left); left -= c; P[who]["burn"][d] += c
    if lg > e + .005: P[who]["over"] += lg - e; over.append(k)
    P[who]["E"] += e
    if not is_story(x): task_close[k] = closed_day(x, TASK_DONE if nondev(x) else TASK_DONE - {"Technical Review"})
story_close = {k: closed_day(iss[k], STORY_DONE) for k in iss if is_story(iss[k])}
eps = {iss[k]["fields"]["parent"]["key"] for k in iss if is_story(iss[k]) and (iss[k]["fields"].get("parent") or {}).get("fields", {}).get("issuetype", {}).get("name") == "Epic"}
epic_close = {e["key"]: closed_day(e, EPIC_DONE) for e in (search("key in (%s)" % ",".join(sorted(eps)), ["status", "issuetype", "created", "updated", "statuscategorychangedate"], "changelog") if eps else [])}
people = {n: p for n, p in P.items() if p["E"] > 0 or p["logs"]}

# ---------------------------------------------------------------- A. data files against Jira
print("A. Data files against Jira")
for n in sorted(people):
    p, d = people[n], S["people"].get(n, {"E": 0, "logs": {}, "burn": {}, "over": 0})
    same = lambda a, b: all(abs(a.get(k, 0) - b.get(k, 0)) < .02 for k in set(a) | set(b))
    check(f"{n}: estimate, logged hours by day, burn by day and over estimate equal Jira", abs(p["E"] - d["E"]) < .02 and same(p["logs"], d["logs"]) and same(p["burn"], d.get("burn", {})) and abs(p["over"] - d.get("over", 0)) < .02,
          f"E {p['E']:g}/{d['E']:g}  logged {sum(p['logs'].values()):g}/{sum(d['logs'].values()):g}  burn {sum(p['burn'].values()):g}/{sum(d.get('burn', {}).values()):g}  over {p['over']:g}/{d.get('over', 0):g}")
check("Same people in the data as in Jira", set(S["people"]) == set(people), f"{sorted(S['people'])}")
check("Closed date of every task equals Jira's status history", {t["k"]: t["d"] for t in S["tasks"] if not t.get("y")} == task_close)
check("Closed date of every user story equals Jira's status history", {s["k"]: s["d"] for s in S["stories"]} == story_close)
check("Closed date of every epic equals Jira's status history", {e["k"]: e["d"] for e in S["epics"]} == epic_close)
a = S.get("audit", {})
check("Data checks equal Jira: no estimate, no assignee, over estimate", sorted(a.get("noEstimate", [])) == sorted(noest) and sorted(u["k"] for u in a.get("unassigned", [])) == sorted(unassigned) and sorted(o["k"] for o in a.get("overrun", [])) == sorted(over), f"noEstimate {noest} unassigned {unassigned} over {over}")

# ---------------------------------------------------------------- the rules, applied independently
def wdays(a, b):
    d, e, out = dt.date.fromisoformat(a), dt.date.fromisoformat(b), []
    while d <= e:
        if d.weekday() < 5: out.append(d.isoformat())
        d += dt.timedelta(1)
    return out
WD = wdays(*WIN); SD = wdays(START, "2026-12-31")[:10]; PLAN = sum(d < WD[0] for d in SD); TOT = len(WD) * DH
asof = (dt.datetime.fromisoformat(meta["refreshedAt"].replace("Z", "+00:00")).astimezone(IST)).replace(tzinfo=None)
AT = min(asof, dt.datetime.fromisoformat(WD[-1] + "T19:00")); AD = AT.date().isoformat()


def elapsed(at):
    e = 0.0
    for d in WD:
        if d < at.date().isoformat(): e += DH
        elif d == at.date().isoformat(): e += max(0, min(DH, at.hour + at.minute / 60 - WH0))
    return e
EL = elapsed(AT)


LEAVE = []
try:
    import urllib.request
    LEAVE = json.loads(urllib.request.urlopen(URL + "/data/leave.json?v=1", timeout=20).read()).get("S24", [])
except Exception:
    LEAVE = []                    # no leave file means no leave


def model(n, p):
    k = CAP / TOT; lv = {}
    for x in LEAVE:
        if x["name"] == n and x["date"] in WD: lv[x["date"]] = min(DH, lv.get(x["date"], 0) + x["hours"])
    avail = [max(0, DH - lv.get(d, 0)) * k for d in WD]; capP = sum(avail)
    def used_at(h):
        u, rest = 0.0, max(0, h)
        for a_ in avail:
            if rest <= 1e-9: break
            t = min(DH, rest); u += a_ * t / DH; rest -= t
        return u
    burned = sum(h for d, h in p["burn"].items() if d <= AD); logged = sum(h for d, h in p["logs"].items() if d <= AD)
    used = used_at(EL); remain, left = max(0, p["E"] - burned), max(0, capP - used); exp = p["E"] * used / capP if capP > 0 else 0; miss = max(0, exp - logged); gap = remain - left     # expected log = (original estimate / capacity days) x capacity days passed
    st = "Not started" if EL <= 0 else "Well behind pace" if miss > 8 else "Behind pace" if miss > .05 else "On pace"
    late = asof.date().isoformat() > WD[-1]
    vd = ("Not completed" if remain > .05 else "Completed") if late else ("Not achievable" if gap > .05 else "Achievable")
    return dict(E=p["E"], logged=logged, remain=remain, over=max(0, logged - burned), exp=exp, miss=miss, left=left, st=st, cap=capP, used=used, leave=sum(lv.values()), vd=vd, used_at=used_at)
M = {n: model(n, p) for n, p in people.items()}
tot = lambda k: sum(m[k] for m in M.values())


def ideal_at(h): return sum((m["E"] * max(0, 1 - m["used_at"](h) / (m["cap"] + 8)) if m["cap"] > 0 else m["E"]) for m in M.values())


def remaining_at(day_i, who):
    """Remaining estimate shown for the day at index day_i (0-based over the sprint days) for the people in who."""
    d = SD[day_i]; lim = d if d >= WD[0] else (dt.date.fromisoformat(WD[0]) - dt.timedelta(1)).isoformat()
    lim = min(lim, AD) if d >= WD[0] else lim
    return sum(max(0, people[n]["E"] - sum(h for x, h in people[n]["burn"].items() if x <= lim)) for n in who)


# ---------------------------------------------------------------- B. the page
from playwright.sync_api import sync_playwright
num = lambda t: float(re.sub(r"[^\d.\-]", "", t.replace("−", "-")) or 0)
close = lambda a, b, t=.06: abs(a - b) <= t
print("\nB. What the page shows")
with sync_playwright() as pw:
    br = pw.chromium.launch(channel="chrome", headless=True)

    def page_for(sprint="S24"):
        c = br.new_context(viewport={"width": 1500, "height": 950}); c.add_init_script(f"localStorage.setItem('sd_auth','fa9304349b9d');localStorage.setItem('sprintdash.one','{sprint}');")
        pg = c.new_page(); pg.set_default_timeout(20000); pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e))); pg.goto(URL + "/"); pg.wait_for_selector('[data-tab="bd"]'); pg.click('[data-tab="bd"]'); pg.wait_for_selector(".seg"); return pg

    def bars(scope):
        out = {}
        for x in pg.locator(scope + " .cb").all_inner_texts():
            m = re.search(r"([\d.]+) h of ([\d.]+) h \((\d+)%\)", x); out[x.split("\n")[0].strip()] = (float(m.group(1)), float(m.group(2)))
        return out

    pg = page_for()
    check("Burndown has two views: Overall and Per person (no Logic page, no Rules page)", pg.locator(".seg button").all_inner_texts() == ["Overall", "Per person"])
    ov = pg.locator(".term").inner_text()
    dayno = sum(d <= asof.date().isoformat() for d in SD); capno = sum(d <= asof.date().isoformat() for d in WD)
    wsp, wcp = pg.locator("#wsprint").inner_text().replace("\n", " "), pg.locator("#wcap").inner_text().replace("\n", " ")
    check("Widget: sprint day equals the count of working days from the start", (f"{dayno} of 10" in wsp) if dayno <= 10 else "Complete" in wsp, f"expected {dayno} of 10, page {wsp}")
    check("Widget: capacity day equals the working days passed, planning days not counted", (f"{capno} of {len(WD)}" in wcp) if capno and asof.date().isoformat() <= WD[-1] else True, f"expected {capno} of {len(WD)}, page {wcp}")
    check("Overview: capacity line says 64 hours = (8 days) x (8 hours)", "64 hours = (8 days) × (8 hours)" in ov)
    check("Overview: one fact per row (no dot-separated lines)", " · " not in ov)
    n = len(people); b = bars("#capov")
    capT = tot("cap"); usedT = tot("used"); leftT = tot("left"); remT = tot("remain")
    check(f"Whole-team bars: used {usedT:.1f} h, left {leftT:.1f} h, remaining estimate {remT:.1f} h of {capT:.1f} h", close(b["Capacity used"][0], usedT, .15) and close(b["Capacity left"][0], leftT, .15) and close(b["Remaining estimate"][0], remT, .15) and all(close(v[1], capT, .15) for v in b.values()), f"page {b}")
    check("Whole-team bars: used + left = capacity", close(b["Capacity used"][0] + b["Capacity left"][0], capT, .2))
    gb = pg.evaluate("() => [...document.querySelectorAll('.gb svg text')].map(t => t.textContent)")
    bad = []
    for nm, m in M.items():
        i = gb.index(nm); v = [num(x) for x in gb[i - 3:i]]
        if not (close(v[0], m["E"]) and close(v[1], m["logged"]) and close(v[2], m["exp"])): bad.append((nm, v))
    check("Hours by person: the bars show original estimate, logged and expected for every person", not bad, bad or f"{len(M)} people compared")

    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    def table(sel): return {r[0]: r for r in pg.evaluate("s => [...document.querySelectorAll(s + ' tbody tr')].map(r => [...r.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim()))", sel)}
    plan_, log_ = table("#tplan"), table("#tlog")
    for nm, m in M.items():
        r, l = plan_.get(nm), log_.get(nm)
        good = bool(r) and close(num(r[1]), m["E"]) and close(num(r[2]), m["remain"]) and close(num(r[3]), m["left"]) and r[4].startswith(m["vd"])
        check(f"{nm}: plan table equals the rules (original, remaining, time left, verdict {m['vd']})", good, f"page {r[1:5] if r else None}  rules {[round(m[c], 1) for c in ('E', 'remain', 'left')] + [m['vd']]}")
        good = bool(l) and all(close(num(l[1 + i]), m[c]) for i, c in enumerate(["logged", "over", "exp", "miss", "leave"])) and l[6] == m["st"]
        check(f"{nm}: logging table equals the rules (logged, over, expected, missing, leave, flag)", good, f"page {l[1:7] if l else None}  rules {[round(m[c], 1) for c in ['logged', 'over', 'exp', 'miss', 'leave']] + [m['st']]}")
    ev, el_ = plan_.get("Everyone"), log_.get("Everyone")
    check("Everyone rows are the sum of the people rows", bool(ev) and all(close(num(ev[1 + i]), tot(c), .25) for i, c in enumerate(["E", "remain", "left"])) and all(close(num(el_[1 + i]), tot(c), .25) for i, c in enumerate(["logged", "over", "exp", "miss", "leave"])), f"{ev} {el_}")
    chk = pg.text_content("#nowlbl"); check("Chart: the label at the end of the blue line equals the team remaining estimate", close(num(chk.split("·")[1]), remT, .1), chk)
    check("Chart: exactly one dot on the lines (the latest pull)", pg.locator("#cw svg circle:visible").count() == 1)

    # hover on every day, Everyone
    svg = pg.locator("#cw svg").bounding_box(); slots = len(SD) + (1 if (WIN and S.get("end") == (dt.date.fromisoformat(SD[-1]) + dt.timedelta(3 if dt.date.fromisoformat(SD[-1]).weekday() == 4 else 1)).isoformat()) else 0)
    def slot_xy(k):
        pg.locator("#cw").scroll_into_view_if_needed(); pg.wait_for_timeout(450); sv = pg.locator("#cw svg").bounding_box()      # a scroll hides the hover card, so let it finish first
        return sv["x"] + (60 + (k + .5) / slots * (1000 - 60 - 16)) / 1000 * sv["width"], sv["y"] + sv["height"] * .4
    sE = tot("E")
    for i in range(slots):
        pg.mouse.move(*slot_xy(i)); pg.wait_for_selector("#tip:not([hidden])")
        d = SD[i] if i < len(SD) else S["end"]
        if d > AD:
            check(f"Hover {d}: a day that has not happened says so", "has not happened yet" in pg.locator("#tip").inner_text()); continue
        hm = pg.evaluate("() => [...document.querySelectorAll('#tip .mt')].map(t => [...t.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim())))")
        hrs, tk = {r[0].split(chr(10))[0]: r[1] for r in hm[0]}, {r[0]: r[1:] for r in hm[1]}
        nn = 0 if d < WD[0] else min(WD.index(d) + 1, len(WD)) if d in WD else len(WD)
        h = min(nn * DH, EL); ideal = ideal_at(h) if nn else sE; rem = remaining_at(i, list(people))
        check(f"Hover {d}: ideal pace and remaining estimate equal the rules", close(num(hrs["Ideal pace"]), ideal, .1) and close(num(hrs["Remaining estimate"]), rem, .1), f"page {hrs}  rules ideal {ideal:.1f} remaining {rem:.1f}")
        cl = lambda m: sum(1 for v in m.values() if v and v <= d); today = lambda m: sum(1 for v in m.values() if v == d)
        for nm, m in (("Sub-tasks", task_close), ("User stories", story_close), ("Epics", epic_close)):
            g = tk[nm]; ok3 = int(g[0]) == today(m) and g[1] == f"{cl(m)} of {len(m)}" and int(g[2]) == len(m) - cl(m)
            check(f"Hover {d} {nm}: closed on the day / up to the day / open equal Jira's history", ok3, f"page {g}  Jira {today(m)}, {cl(m)} of {len(m)}, {len(m) - cl(m)}")
    pg.mouse.move(5, 5); pg.wait_for_selector("#tip", state="hidden")

    # day panel for every past day: the summary table and the three tabs list exactly Jira's tickets
    allc = {**task_close, **story_close, **epic_close}
    for i, d in enumerate(SD):
        if d > AD: continue
        pg.mouse.click(*slot_xy(i)); pg.wait_for_selector("#dayd:not([hidden])"); pg.wait_for_timeout(500)
        sm = {r[0]: r[1:] for r in pg.evaluate("() => [...document.querySelectorAll('#dayd .dsum tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim()))")}
        ok = True; why = []
        for nm, m in (("Sub-tasks", task_close), ("User stories", story_close), ("Epics", epic_close)):
            c1, c2 = sum(v == d for v in m.values()), sum(1 for v in m.values() if v and v <= d)
            if not (int(sm[nm][0]) == c1 and sm[nm][1] == f"{c2} of {len(m)}" and int(sm[nm][2]) == len(m) - c2): ok = False; why.append((nm, sm[nm], c1, c2))
        check(f"Day panel {d}: summary counts (closed on the day, up to the day, still open) equal Jira", ok, why)
        for tab, want in (("today", sum(v == d for v in allc.values())), ("closed", sum(1 for v in allc.values() if v and v <= d)), ("open", sum(1 for v in allc.values() if not (v and v <= d)))):
            pg.click("[data-dfilter]"); pg.check(f'[data-dfk="{tab}"]'); [pg.uncheck(f'[data-dfk="{k}"]') for k in ("today", "closed", "open") if k != tab and pg.locator(f'[data-dfk="{k}"]').is_checked()]; pg.keyboard.press("Escape"); nrows = pg.locator("#dayd .dtab tbody tr:not(.dgrp):not(.rnone)").count()
            check(f"Day panel {d}, tab {tab}: the list holds {want} tickets", nrows == want, f"page {nrows}")
        xs = pg.evaluate("() => [...new Set([...document.querySelectorAll('#dayd .dtab td.num')].map(c => Math.round(c.getBoundingClientRect().right)))].length")
        check(f"Day panel {d}: the estimate column lines up across epics, user stories and sub-tasks", xs == 1, f"{xs} different right edges")
        pg.mouse.click(*slot_xy(i)); pg.wait_for_timeout(300)

    # per-person capacity bars and tables
    pg.wait_for_selector("#bdwho")
    for nm, m in M.items():
        pg.select_option("#bdwho", nm); bb = bars("#capper")
        check(f"{nm}: capacity bars equal the rules (used {m['used']:.1f}, left {m['left']:.1f}, remaining {m['remain']:.1f} of {m['cap']:.1f} h)", close(bb["Capacity used"][0], m["used"], .1) and close(bb["Capacity left"][0], m["left"], .1) and close(bb["Remaining estimate"][0], m["remain"], .1) and close(bb["Capacity used"][1], m["cap"], .1), f"page {bb}")
        r = table("#tplan").get(nm); check(f"{nm}: single-person plan table matches the rules", bool(r) and close(num(r[1]), m["E"]) and close(num(r[2]), m["remain"]) and r[4].startswith(m["vd"]))
    check("No JavaScript errors on the Burndown page", not pg.errors, pg.errors[:2])

    # ---------------- C. edge cases on older sprints: the axis must start on the sprint's first working day
    print("\nC. Edge cases")
    for sp, first_day, retro in (("S22", "Mon 12 Oct", False), ("S23", "Mon 26 Oct", False), ("S21", "Mon 28 Sep", False), ("S20", "Tue 8 Sep", False)):
        q = page_for(sp); q.click('[data-bdview="person"]'); q.wait_for_selector("#cw svg")
        labs = q.evaluate("() => [...document.querySelectorAll('#cw svg text')].map(t => t.textContent)")
        bsp = bd[sp]; wd = wdays(*bsp["win"])
        dn = [x for x in labs if re.fullmatch(r"(Day \d+|Retro)", x)]
        check(f"{sp}: the day axis starts on {wd[0]} (Day 1) and has {'a' if retro else 'no'} retrospective slot", dn[0] == "Day 1" and (("Retro" in dn) == retro) and len([x for x in dn if x.startswith("Day")]) == 10, f"{dn}")
        dates = [x for x in labs if re.fullmatch(r"\d+ [A-Z][a-z]{2}", x)]
        want0 = (dt.date.fromisoformat(wd[0])).strftime("%-d %b"); check(f"{sp}: first date label equals the first working day {want0}", dates and dates[0] == want0, f"{dates[:3]}")
        pe = bsp["people"]; tt = [r for r in q.evaluate("() => [...document.querySelectorAll('#tplan tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim()))")]
        bad = [r[0] for r in tt if r[0] in pe and not (close(num(r[1]), pe[r[0]]["E"], .06))]
        check(f"{sp}: every person's original estimate in the table equals the data", not bad, bad)
        check(f"{sp}: remaining estimate is never above original estimate", all(num(r[2]) <= num(r[1]) + .06 for r in tt if r[0] in pe))
        q.context.close()
    br.close()

print("\nRESULT:", "ALL PASS" if all(res) else f"{sum(not r for r in res)} OF {len(res)} CHECKS FAILED"); sys.exit(0 if all(res) else 1)
