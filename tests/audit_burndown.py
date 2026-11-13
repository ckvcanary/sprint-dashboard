"""Logic audit of the Burndown page: every number the page shows is re-derived from Jira, with its own code, and compared with what the page displays.
Run against a deployed page or a preview (read only apart from the optional --refresh, which uses the page's own Refresh button path):
    python3 tests/audit_burndown.py https://sprint-dashboard-umber.vercel.app [--refresh]
Needs the Jira login (.env) and Playwright with Chrome. The browser is signed in by setting the same marker the page keeps after the password step, so the password is not needed here.

Three layers:  Jira  ->  data files (refresh.py)  ->  what the page shows (template.html).
  A. data files against an independent read of Jira (estimates, logged hours by day, burn, over estimate, closed dates)
  B. the page's tables, bars, chart hover, day panel and Logic page against numbers computed from the rules, not from the page's own code
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
    if not is_story(x): task_close[k] = closed_day(x, TASK_DONE)
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


def model(n, p):
    burned = sum(h for d, h in p["burn"].items() if d <= AD); logged = sum(h for d, h in p["logs"].items() if d <= AD)
    exp, remain, left = CAP * EL / TOT, max(0, p["E"] - burned), CAP * (TOT - EL) / TOT; miss = max(0, exp - logged)
    st = "Not started" if EL <= 0 else "Time log missing" if miss > 8 else "Behind on logging" if miss > 2 else "On track"
    if EL > 0 and st == "On track" and remain > left + .05 and asof.date().isoformat() <= WD[-1]: st = "Cannot finish in time"
    return dict(E=p["E"], logged=logged, remain=remain, over=max(0, logged - burned), exp=exp, miss=miss, left=left, st=st)
M = {n: model(n, p) for n, p in people.items()}
tot = lambda k: sum(m[k] for m in M.values())


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

    pg = page_for()
    check("Burndown has three areas: Overall, Per person, Logic", pg.locator(".seg button").all_inner_texts() == ["Overall", "Per person", "Logic"])
    ov = pg.locator(".term").inner_text()
    dayno = sum(d <= asof.date().isoformat() for d in SD)
    check("Overview: sprint day equals the count of working days from the start", (f"{dayno} of 10" in ov) if dayno <= 10 else "10 of 10" in ov, f"expected {dayno} of 10")
    check("Overview: capacity line says 64 h = 8 days x 8 h", "64 h per person = 8 days × 8 h" in ov)
    cap = pg.locator(".capb").inner_text(); used = num(re.search(r"Used\s+([\d.]+) h", cap).group(1)); lf = num(re.search(r"Left\s+([\d.]+) h", cap).group(1))
    n = len(people); check(f"Whole-team capacity bar: used {n * CAP * EL / TOT:.1f} h of {n * CAP} h", close(used, n * CAP * EL / TOT) and close(used + lf, n * CAP), f"page: used {used}, left {lf}")
    gb = pg.evaluate("() => [...document.querySelectorAll('.gb svg text')].map(t => t.textContent)")
    bad = []
    for nm, m in M.items():
        i = gb.index(nm); v = [num(x) for x in gb[i - 3:i]]
        if not (close(v[0], m["E"]) and close(v[1], m["logged"]) and close(v[2], m["exp"])): bad.append((nm, v))
    check("Hours by person: the bars show original estimate, logged and expected for every person", not bad, bad or f"{len(M)} people compared")

    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#cw svg")
    def table():
        return pg.evaluate("() => { const t = [...document.querySelectorAll('#v-bd .panel table')].pop(); return [...t.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim())); }")
    rows = {r[0]: r for r in table()}
    cols = ["E", "logged", "remain", "over", "exp", "miss", "left"]
    for nm, m in M.items():
        r = rows.get(nm); good = bool(r) and all(close(num(r[1 + i]), m[c]) for i, c in enumerate(cols)) and r[8] == m["st"]
        check(f"{nm}: table row equals the rules (original, logged, remaining, over, expected, missing, left, flag)", good, f"page {r[1:9] if r else None}  rules {[round(m[c], 1) for c in cols] + [m['st']]}")
    ev = rows.get("Everyone"); check("Everyone row is the sum of the people rows", bool(ev) and all(close(num(ev[1 + i]), tot(c), .15) for i, c in enumerate(cols)), f"page {ev[1:8] if ev else None}")

    # hover on every day, Everyone
    svg = pg.locator("#cw svg").bounding_box(); slots = len(SD) + (1 if (WIN and S.get("end") == (dt.date.fromisoformat(SD[-1]) + dt.timedelta(3 if dt.date.fromisoformat(SD[-1]).weekday() == 4 else 1)).isoformat()) else 0)
    def slot_xy(k): return svg["x"] + (60 + (k + .5) / slots * (1000 - 60 - 16)) / 1000 * svg["width"], svg["y"] + svg["height"] * .4
    sE = tot("E")
    for i in range(slots):
        pg.mouse.move(*slot_xy(i)); pg.wait_for_selector("#tip:not([hidden])")
        t = pg.evaluate("() => Object.fromEntries([...document.querySelectorAll('#tip .mt tbody tr')].map(r => [r.cells[0].innerText.split(String.fromCharCode(10))[0], [...r.cells].slice(1).map(c => c.innerText.trim())]))")
        d = SD[i] if i < len(SD) else S["end"]
        if d > AD:
            check(f"Hover {d}: a day that has not happened says so", "Not happened yet" in pg.locator("#tip").inner_text()); continue
        nn = 0 if d < WD[0] else min(WD.index(d) + 1, len(WD)) if d in WD else len(WD)
        ideal_done = sE * min(nn * DH, TOT) / TOT; rem = remaining_at(i, list(people))
        # for today the page uses elapsed hours of today: remaining is the value at the pull time; same as burn up to today
        got_ideal, got_act = t["Ideal pace"], t["Actual"]
        ok1 = close(num(got_ideal[0]), ideal_done, .1) and close(num(got_ideal[1]), sE - ideal_done, .1)
        ok2 = close(num(got_act[1]), rem, .1) and close(num(got_act[0]), sE - rem, .1)
        cl = lambda m: sum(1 for v in m.values() if v and v <= d); today = lambda m: sum(1 for v in m.values() if v == d)
        for nm, m in (("Tasks", task_close), ("User stories", story_close), ("Epics", epic_close)):
            g = t[nm]; ok3 = int(g[0]) == today(m) and g[1] == f"{cl(m)} of {len(m)}" and int(g[2]) == len(m) - cl(m)
            check(f"Hover {d} {nm}: closed today / so far / open equal Jira's history", ok3, f"page {g}  Jira {today(m)}, {cl(m)} of {len(m)}, {len(m) - cl(m)}")
        check(f"Hover {d}: ideal pace and actual hours equal the rules", ok1 and ok2, f"page ideal {got_ideal} actual {got_act}  rules ideal {ideal_done:.1f}/{sE - ideal_done:.1f} actual {sE - rem:.1f}/{rem:.1f}")
    pg.mouse.move(5, 5); pg.wait_for_selector("#tip", state="hidden")

    # day panel for every past day: the three tabs list exactly Jira's tickets
    for i, d in enumerate(SD):
        if d > AD: continue
        pg.mouse.click(*slot_xy(i)); pg.wait_for_selector("#dayd:not([hidden])")
        counts = pg.evaluate("() => [...document.querySelectorAll('.dtabs button')].map(b => +b.querySelector('b').innerText)")
        allc = {**task_close, **story_close, **epic_close}
        want = [sum(v == d for v in allc.values()), sum(1 for v in allc.values() if v and v <= d), sum(1 for v in allc.values() if not (v and v <= d))]
        check(f"Day panel {d}: tab counts (closed this day, so far, still open) equal Jira", counts == want, f"page {counts} Jira {want}")
        pg.mouse.click(*slot_xy(i))
    pg.click('[data-bdview="logic"]'); pg.wait_for_selector(".lgc")

    # per-person capacity bar
    pg.click('[data-bdview="person"]'); pg.wait_for_selector("#bdwho")
    for nm, m in M.items():
        pg.select_option("#bdwho", nm); t = pg.locator(".pcap").inner_text()
        u = num(re.search(r"Used\s+([\d.]+) h", t).group(1)); check(f"{nm}: capacity bar used = 64 h x time passed / total time", close(u, CAP * EL / TOT), f"page {u}")
        r = {x[0]: x for x in table()}.get(nm); check(f"{nm}: single-person table matches the rules", bool(r) and close(num(r[1]), m["E"]) and close(num(r[3]), m["remain"]))

    # Logic page
    pg.click('[data-bdview="logic"]'); pg.wait_for_selector("#lgchk")
    fails = pg.locator("#lgchk .tag.bad").count(); check("Logic page: every self-check passes", fails == 0 and pg.locator("#lgchk .tag.ok").count() >= 6, f"{pg.locator('#lgchk .tag.ok').count()} pass, {fails} fail")
    lt = {r[0]: r for r in pg.evaluate("() => [...document.querySelectorAll('.lgc')][0] ? [...document.querySelectorAll('.lgc')][0].tBodies[0] ? [...[...document.querySelectorAll('.lgc')][0].tBodies[0].rows].map(r => [...r.cells].map(c => c.innerText.trim())) : [] : []")}
    for lab, want in (("Original estimate", tot("E")), ("Logged", tot("logged")), ("Remaining estimate", tot("remain")), ("Over estimate", tot("over")), ("Expected logged by now", tot("exp")), ("Missing log", tot("miss")), ("Time left in sprint", tot("left"))):
        check(f"Logic page value: {lab}", lab in lt and close(num(lt[lab][3].split()[0]), want, .15), f"page {lt.get(lab, ['', '', '', None])[3]}  rules {want:.1f}")
    w = pg.evaluate("() => [...document.querySelectorAll('#lgwarn tr')].map(r => [r.cells[0].innerText, r.cells[1].innerText])"); wd_ = {a: b for a, b in w}
    check("Logic page data checks: over estimate, no estimate and no assignee counts equal Jira", int(wd_["Tasks logged over their own estimate"]) == len(over) and int(wd_["Tasks with no original estimate"]) == len(noest) and int(wd_["Tasks with no assignee (left out of the burndown)"]) == len(unassigned), str(wd_))
    check("No JavaScript errors on the Burndown page", not pg.errors, pg.errors[:2])

    # ---------------- C. edge cases on older sprints: the axis must start on the sprint's first working day
    print("\nC. Edge cases")
    for sp, first_day, retro in (("S22", "Mon 12 Oct", False), ("S23", "Mon 26 Oct", True), ("S21", "Mon 28 Sep", False), ("S20", "Tue 8 Sep", False)):
        q = page_for(sp); q.click('[data-bdview="person"]'); q.wait_for_selector("#cw svg")
        labs = q.evaluate("() => [...document.querySelectorAll('#cw svg text')].map(t => t.textContent)")
        bsp = bd[sp]; wd = wdays(*bsp["win"])
        dn = [x for x in labs if re.fullmatch(r"(Day \d+|Retro)", x)]
        check(f"{sp}: the day axis starts on {wd[0]} (Day 1) and has {'a' if retro else 'no'} retrospective slot", dn[0] == "Day 1" and (("Retro" in dn) == retro) and len([x for x in dn if x.startswith("Day")]) == 10, f"{dn}")
        dates = [x for x in labs if re.fullmatch(r"\d+ [A-Z][a-z]{2}", x)]
        want0 = (dt.date.fromisoformat(wd[0])).strftime("%-d %b"); check(f"{sp}: first date label equals the first working day {want0}", dates and dates[0] == want0, f"{dates[:3]}")
        pe = bsp["people"]; tt = q.evaluate("() => { const t = [...document.querySelectorAll('#v-bd .panel table')].pop(); return [...t.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.innerText.trim())); }")
        bad = [r[0] for r in tt if r[0] in pe and not (close(num(r[1]), pe[r[0]]["E"], .06))]
        check(f"{sp}: every person's original estimate in the table equals the data", not bad, bad)
        check(f"{sp}: remaining estimate is never above original estimate", all(num(r[3]) <= num(r[1]) + .06 for r in tt if r[0] in pe))
        q.context.close()
    br.close()

print("\nRESULT:", "ALL PASS" if all(res) else f"{sum(not r for r in res)} OF {len(res)} CHECKS FAILED"); sys.exit(0 if all(res) else 1)
