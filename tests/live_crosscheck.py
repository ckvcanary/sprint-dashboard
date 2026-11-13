"""Logical check of the dashboard against Jira, using independent Jira queries. NOT part of the normal test run (needs the Jira login and the preview).
Run: python3 tests/live_crosscheck.py [preview-url]   Reads only; changes nothing in Jira.
It pulls fresh data through the preview's Refresh, then re-derives every number from Jira on its own and compares."""
import base64, collections, datetime as dt, json, pathlib, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
for p in (ROOT / ".env", ROOT.parent / ".env"):
    if p.exists():
        for l in p.read_text().splitlines():
            if "=" in l and not l.lstrip().startswith("#"): k, v = l.strip().split("=", 1); env.setdefault(k, v.strip("\"'"))
BASE, AUTH = env["JIRA_BASE"].rstrip("/"), base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
PREVIEW = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8767").rstrip("/").replace("/index.html", "")
SPRINT, SPRINT_START, ROLL = 1195, "2026-11-09", {"PROD-3913", "PROD-3977", "PROD-3978", "PROD-3979"}
TASK_DONE = {"Technical Review", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Fixed", "Done"}; STORY_DONE = {"Deployed to UAT", "Deployed to Prod"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
first = lambda a: a["displayName"].split()[0] if a else None


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


def get(p): return json.load(urllib.request.urlopen(PREVIEW + p + "?v=%d" % time.time(), timeout=30))


# 1. fresh pull through the dashboard's own Refresh path
before = get("/data/meta.json")["refreshedAt"]
print("Refreshing the dashboard data from Jira ...", flush=True)
age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(before.replace("Z", "+00:00"))).total_seconds()
if age < 125: time.sleep(125 - age)
urllib.request.urlopen(urllib.request.Request(PREVIEW + "/api/refresh", method="POST", data=b"", headers={"Origin": PREVIEW}))
for _ in range(60):
    time.sleep(3)
    if get("/data/meta.json")["refreshedAt"] != before: break
m, bd, meta = get("/data/map.json"), get("/data/burndown.json"), get("/data/meta.json")
print("Dashboard data from", meta["refreshedAt"], "\n")

# 2. independent facts from Jira
F = ["summary", "status", "assignee", "issuetype", "parent", "timeoriginalestimate", "customfield_10044", "worklog", "created", "updated", "statuscategorychangedate"]
iss = {x["key"]: x for x in search(f"project = PROD AND sprint = {SPRINT} AND issuetype != Epic", F, "changelog")}
subs = {k for k, x in iss.items() if x["fields"]["issuetype"].get("subtask")}
parents = {x["fields"]["parent"]["key"] for k, x in iss.items() if k in subs and x["fields"].get("parent")}
stories = {k for k in iss if k not in subs}
leaf = {k for k in iss if k in subs or k not in parents}     # a task = sub-task, or story with no sub-tasks
res = []
def check(name, ok, detail=""): res.append((name, ok, detail)); print(("PASS  " if ok else "FAIL  ") + name + (("  " + detail) if detail else ""), flush=True)

dash_stories = {s["key"]: s for s in m["stories"] if s["sprint"] == "S24"}
dash_tasks = {t["key"]: t for s in dash_stories.values() for t in s["tasks"]}
check("Same user stories as Jira's Sprint 24", set(dash_stories) == stories, f"dashboard {len(dash_stories)}, Jira {len(stories)}" + ("" if set(dash_stories) == stories else f"; only in Jira {sorted(stories - set(dash_stories))}, only on dashboard {sorted(set(dash_stories) - stories)}"))
check("Same sub-tasks as Jira's Sprint 24", set(dash_tasks) == subs, f"dashboard {len(dash_tasks)}, Jira {len(subs)}")
bt = {t["k"]: t for t in bd["S24"]["tasks"]}
check("Burndown list equals Jira's leaf tickets (every sub-task type, plus tickets without sub-tasks)", set(bt) == leaf, f"dashboard {len(bt)}, Jira {len(leaf)}")

# estimates: rolled-over parents subtract time logged before the sprint start (read from Jira worklogs, independently)
bad = []
for k in leaf:
    f = iss[k]["fields"]; oe = (f.get("timeoriginalestimate") or 0) / 3600
    par = (f.get("parent") or {}).get("key")
    if par in ROLL:
        wl = f["worklog"]["worklogs"] if f["worklog"]["total"] <= len(f["worklog"]["worklogs"]) else jira(f"/rest/api/3/issue/{k}/worklog?maxResults=1000")["worklogs"]
        oe = max(0.0, oe - sum(l["timeSpentSeconds"] / 3600 for l in wl if l["started"][:10] < SPRINT_START))
    if abs(bt.get(k, {}).get("e", -1) - oe) > 0.01: bad.append((k, oe, bt.get(k, {}).get("e")))
check("Every task's estimate matches Jira (rolled-over work: original minus time logged before the sprint)", not bad, f"{len(leaf)} tasks compared" + (f"; differences {bad[:5]}" if bad else ""))
tot_j = sum(max(0.0, (iss[k]["fields"].get("timeoriginalestimate") or 0) / 3600) for k in leaf); tot_d = sum(t["e"] for t in bt.values())
print(f"      (raw Jira estimate total {tot_j:g} h; dashboard total after the rollover rule {tot_d:g} h)")
by_j = collections.defaultdict(float)
for k in leaf:
    a = first(iss[k]["fields"].get("assignee"))
    if a: by_j[a] += bt[k]["e"] if k in bt else 0
by_d = {n: p["E"] for n, p in bd["S24"]["people"].items()}
check("Per-person estimate totals equal the sum of that person's tasks", all(abs(by_d.get(n, 0) - by_j.get(n, 0)) < 0.05 for n in set(by_d) | set(by_j)), "; ".join(f"{n} {by_d.get(n, 0):g} h" for n in sorted(by_d)))
check("Story points match Jira for every user story", all((dash_stories[k]["sp"] or 0) == int(iss[k]["fields"].get("customfield_10044") or 0) for k in stories if k in dash_stories), f"total {sum(int(iss[k]['fields'].get('customfield_10044') or 0) for k in stories)} points")
check("Assignee of every user story matches Jira", all(dash_stories[k]["a"] == first(iss[k]["fields"].get("assignee")) for k in stories if k in dash_stories))
check("Assignee of every task matches Jira", all(dash_tasks[k]["a"] == first(iss[k]["fields"].get("assignee")) for k in subs if k in dash_tasks))
check("Status of every task matches Jira", all(dash_tasks[k]["s"] == iss[k]["fields"]["status"]["name"] for k in subs if k in dash_tasks))

# epics
eps = {}
for k in stories:
    par = iss[k]["fields"].get("parent") or {}
    if par.get("fields", {}).get("issuetype", {}).get("name") == "Epic": eps[par["key"]] = None
if eps:
    for x in search("key in (%s)" % ",".join(sorted(eps)), ["assignee", "summary"]): eps[x["key"]] = first(x["fields"].get("assignee"))
de = {e["key"]: e["a"] for e in m["epics"]}
check("Assignee of every epic matches Jira", all(de.get(k) == v for k, v in eps.items()), "; ".join(f"{k} {v or 'Unassigned'}" for k, v in sorted(eps.items())))

# closed tickets: Jira's own answer with the agreed lists (tasks: six statuses; user stories and epics: Deployed to UAT or Prod only)
q = lambda names: ",".join(f'"{n}"' for n in sorted(names))
task_done = {x["key"] for x in search(f"project = PROD AND sprint = {SPRINT} AND issuetype in subTaskIssueTypes() AND status in ({q(TASK_DONE)})", ["status"])} | {x["key"] for x in search(f"project = PROD AND sprint = {SPRINT} AND issuetype in (Task, Bug, \"New Feature\") AND status in ({q(TASK_DONE)})", ["status"])}
story_done = {x["key"] for x in search(f"project = PROD AND sprint = {SPRINT} AND issuetype = Story AND status in ({q(STORY_DONE)})", ["status"])}
done_j = task_done & leaf     # tasks: every sub-task type and any top-level Task, Bug or New Feature without sub-tasks
done_d = {k for k, t in bt.items() if t["d"] and not t.get("y")}
check("Tasks the dashboard counts as closed equal Jira's list for the agreed statuses", done_d == done_j, f"dashboard {len(done_d)}, Jira {len(done_j)}" + ("" if done_d == done_j else f"; differences {sorted(done_d ^ done_j)}"))
sd_ = {s["k"]: s for s in bd["S24"]["stories"]}; done_s = {k for k, s in sd_.items() if s["d"]}
check("User stories counted as closed equal Jira's list (Deployed to UAT or Prod)", done_s == story_done, f"dashboard {len(done_s)}, Jira {len(story_done)}")
ed_ = {e["k"]: e for e in bd["S24"]["epics"]}; done_e = {k for k, e in ed_.items() if e["d"]}
ej = {x["key"] for x in search(f"key in ({','.join(sorted(eps))}) AND status in ({q(STORY_DONE)})", ["status"])} if eps else set()
check("Epics of the sprint equal Jira's, and the closed ones equal Jira's list (Deployed to UAT or Prod)", set(ed_) == set(eps) and done_e == ej, f"{len(ed_)} epics, {len(done_e)} closed (Jira {len(ej)})")

# the day each task was closed, from Jira's own history
wrong = []
for k in done_d:
    since = None
    for h in sorted(iss[k].get("changelog", {}).get("histories", []), key=lambda h: h["created"]):
        for it in h["items"]:
            if it.get("field") == "status": since = (since or h["created"]) if it.get("toString") in (TASK_DONE if k in subs else STORY_DONE) else None
    want = dt.datetime.strptime(since, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(IST).date().isoformat() if since else None
    if want and bt[k]["d"] != want: wrong.append((k, bt[k]["d"], want))
check("Closed-on date of every finished task matches Jira's status history", not wrong, f"{len(done_d)} compared" + (f"; differences {wrong[:5]}" if wrong else ""))
check("Dashboard data is from this pull (map and meta stamps equal)", m["asOf"] == meta["refreshedAt"], meta["refreshedAt"])
print("\nRESULT:", "ALL PASS" if all(r[1] for r in res) else f"{sum(not r[1] for r in res)} CHECK(S) FAILED"); sys.exit(0 if all(r[1] for r in res) else 1)
