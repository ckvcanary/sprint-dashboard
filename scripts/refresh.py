"""Pull Sprint data from Jira (REST) and write data/map.json, data/burndown.json, data/meta.json, data/runs.json.
Credentials: JIRA_BASE, JIRA_EMAIL, JIRA_TOKEN from the environment, or from a .env file (../.env or ./.env).
Run: python3 scripts/refresh.py            (stdlib only)"""
import base64, collections, datetime as dt, json, os, pathlib, re, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPRINT_IDS = {"S16": 1059, "S17": 1060, "S18": 1093, "S19": 1126, "S20": 1159, "S21": 1160, "S22": 1193, "S23": 1194, "S24": 1195}
# working window per sprint for the burndown: Mon to Fri, 11:00 to 19:00 IST, 8 h a day, 64 h capacity
WIN = {"S16": ("2026-06-21", "2026-07-06"), "S17": ("2026-07-07", "2026-07-21"), "S19": ("2026-08-24", "2026-09-07"), "S20": ("2026-09-08", "2026-09-22"),
       "S21": ("2026-09-28", "2026-10-09"), "S22": ("2026-10-12", "2026-10-23"), "S23": ("2026-10-26", "2026-11-06"), "S24": ("2026-11-11", "2026-11-20")}
SPRINT_START = {"S24": "2026-11-09"}          # real sprint start, used to split time logged in earlier sprints
DESC_SPRINTS = {"S22", "S23", "S24"}           # descriptions refreshed for these sprints (older ones are kept)
ROLLOVER_SPRINTS = {"S24"}                     # hours rule: task hours = original estimate minus time logged before the sprint start
BOARD = 243
FIELDS = ["summary", "status", "assignee", "issuetype", "parent", "timeoriginalestimate", "worklog", "customfield_10044", "customfield_10020"]


def load_env():
    e = dict(os.environ)
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if p.exists():
            for l in p.read_text().splitlines():
                if "=" in l and not l.lstrip().startswith("#"):
                    k, v = l.strip().split("=", 1)
                    e.setdefault(k, v.strip("\"'"))
    return e


ENV = load_env()
BASE = ENV.get("JIRA_BASE", "").rstrip("/")


def api(path, body=None, method=None):
    auth = base64.b64encode(f"{ENV['JIRA_EMAIL']}:{ENV['JIRA_TOKEN']}".encode()).decode()
    for attempt in range(6):
        req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None,
                                     {"Authorization": "Basic " + auth, "Content-Type": "application/json", "Accept": "application/json"}, method=method)
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(int(ex.headers.get("Retry-After", 3 * (attempt + 1))))
                continue
            raise


def search(jql, fields):
    out, tok = [], None
    while True:
        body = {"jql": jql, "fields": fields, "maxResults": 100}
        if tok:
            body["nextPageToken"] = tok
        d = api("/rest/api/3/search/jql", body)
        out += d.get("issues", [])
        tok = d.get("nextPageToken")
        if d.get("isLast", True) or not tok:
            return out


def full_worklogs(x):
    w = x["fields"].get("worklog") or {}
    wl = w.get("worklogs", [])
    if w.get("total", 0) > len(wl):
        wl = api(f"/rest/api/3/issue/{x['key']}/worklog?maxResults=1000").get("worklogs", [])
    return wl


def first(a):
    return a["displayName"].split()[0] if a else None


def clean(s):
    s = re.sub(r"^(User Story|Epic):\s*", "", s or "")
    return re.sub(r"\s*--\s*Sprint\s*\d+(\s+Backlog)?\s*$", "", s).strip()


def adf_md(n, depth=0):
    if n is None:
        return ""
    if isinstance(n, str):
        return n
    t = n.get("type")
    kids = lambda sep="": sep.join(adf_md(c, depth) for c in n.get("content", []))
    if t == "text":
        s = n.get("text", "")
        for m in n.get("marks", []):
            if m["type"] == "strong": s = f"**{s}**"
            elif m["type"] == "code": s = f"`{s}`"
            elif m["type"] == "link": s = f"[{s}]({m['attrs'].get('href', '')})"
        return s
    if t == "paragraph": return kids() + "\n\n"
    if t == "heading": return "#" * min(6, n["attrs"].get("level", 2)) + " " + kids() + "\n\n"
    if t == "hardBreak": return "\n"
    if t in ("bulletList", "orderedList"):
        return "".join(("- " if t == "bulletList" else f"{i + 1}. ") + adf_md(li, depth + 1).strip() + "\n" for i, li in enumerate(n.get("content", []))) + "\n"
    if t == "listItem": return kids()
    if t == "codeBlock": return "```\n" + kids() + "\n```\n\n"
    if t in ("table", "tableRow"): return kids("\n" if t == "table" else " | ") + ("\n" if t == "table" else "")
    if t in ("tableCell", "tableHeader"): return kids().strip()
    if t in ("mention", "emoji", "inlineCard", "status"):
        a = n.get("attrs", {}); return a.get("text") or a.get("url") or a.get("shortName") or ""
    return kids()


def week_days(a, b):
    d, e = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [d + dt.timedelta(i) for i in range((e - d).days + 1) if (d + dt.timedelta(i)).weekday() < 5]


def sprint_label(date_str):
    starts = [("S22", "2026-10-12"), ("S23", "2026-10-26"), ("S24", "2026-11-09"), ("S25", "2026-11-24")]
    n, s = 25, dt.date.fromisoformat("2026-11-24")
    while s < dt.date.fromisoformat(date_str):
        n += 1; s += dt.timedelta(14); starts.append((f"S{n}", s.isoformat()))
    lab = ""
    for k, s in starts:
        if s <= date_str: lab = k
    return lab.replace("S", "Sprint ")


def main():
    old = json.loads((DATA / "map.json").read_text())
    sprints = {k: v for k, v in SPRINT_IDS.items()}
    names = {s["id"]: s for s in old["sprints"]}
    try:  # pick up newer sprints automatically from the board
        for sp in api(f"/rest/agile/1.0/board/{BOARD}/sprint?state=active,future&maxResults=50").get("values", []):
            m = re.match(r"Sprint (\d+)$", sp["name"])
            if m and f"S{m.group(1)}" not in sprints and sp.get("startDate"):
                k = f"S{m.group(1)}"; sprints[k] = sp["id"]
                WIN[k] = (sp["startDate"][:10], sp["endDate"][:10]); names[k] = {"id": k, "name": sp["name"], "r": ""}
    except Exception as ex:
        print("board lookup skipped:", ex)
    keys = sorted(sprints, key=lambda k: int(k[1:]))
    stories, epics, desc = {}, {}, {}
    bd = {}
    total = 0
    for sk in keys:
        sid = sprints[sk]
        fields = FIELDS + (["description"] if sk in DESC_SPRINTS else [])
        iss = {x["key"]: x for x in search(f"project = PROD AND sprint = {sid} AND issuetype != Epic ORDER BY key", fields)}
        total += len(iss)
        parents = {(x["fields"].get("parent") or {}).get("key") for x in iss.values()}
        # ---------- burndown
        if sk in WIN:
            st, en = WIN[sk]; ss = SPRINT_START.get(sk, st)
            ppl = collections.defaultdict(lambda: {"E": 0.0, "logs": collections.defaultdict(float)})
            for k, x in iss.items():
                if k in parents or not x["fields"].get("assignee"):
                    continue
                f = x["fields"]; pre = 0.0
                for l in full_worklogs(x):
                    d = l["started"][:10]; h = l["timeSpentSeconds"] / 3600; au = first(l["author"])
                    if d < ss: pre += h
                    elif d <= en: ppl[au]["logs"][d] += h
                ppl[first(f["assignee"])]["E"] += max(0.0, (f.get("timeoriginalestimate") or 0) / 3600 - pre)
            bd[sk] = {"name": names.get(sk, {}).get("name", sk.replace("S", "Sprint ")), "win": [st, en],
                      "people": {p: {"E": round(v["E"], 2), "logs": {d: round(h, 2) for d, h in sorted(v["logs"].items())}} for p, v in ppl.items() if v["E"] > 0 or v["logs"]}}
            if sk != "S24": bd[sk]["note"] = "Shows only work still attached to the sprint in Jira; tasks moved out at closure are not included."
        else:
            bd[sk] = {"name": names.get(sk, {}).get("name", sk.replace("S", "Sprint ")), "win": None, "people": {}}
        # ---------- map: stories and their tasks in this sprint
        subs = [x for x in iss.values() if x["fields"]["issuetype"].get("subtask")]
        tops = {k: x for k, x in iss.items() if not x["fields"]["issuetype"].get("subtask")}
        need = {x["fields"]["parent"]["key"] for x in subs if x["fields"].get("parent")} - set(tops)
        if need:
            for x in search("key in (%s)" % ",".join(sorted(need)), [f for f in fields if f != "worklog"]):
                tops[x["key"]] = x
        for k, x in tops.items():
            f = x["fields"]; par = f.get("parent") or {}
            ep = par.get("key") if (par.get("fields", {}).get("issuetype", {}).get("name") == "Epic") else None
            tasks = []
            for s in sorted((y for y in subs if (y["fields"].get("parent") or {}).get("key") == k), key=lambda y: y["key"]):
                sf = s["fields"]; oe = (sf.get("timeoriginalestimate") or 0) / 3600
                if sk in ROLLOVER_SPRINTS:
                    pre = sum(l["timeSpentSeconds"] / 3600 for l in full_worklogs(s) if l["started"][:10] < SPRINT_START.get(sk, "0000"))
                    oe = max(0.0, oe - pre)
                tasks.append({"key": s["key"], "t": sf["summary"], "a": first(sf.get("assignee")), "h": round(oe, 2), "s": sf["status"]["name"]})
                if sk in DESC_SPRINTS and sf.get("description"): desc[s["key"]] = adf_md(sf["description"]).strip()
            own = round((f.get("timeoriginalestimate") or 0) / 3600, 2) if not tasks else 0
            sp = f.get("customfield_10044")
            stories[k] = {"key": k, "title": clean(f["summary"]), "epic": ep, "sprint": sk, "a": first(f.get("assignee")), "sp": int(sp) if sp else None, "own": own, "tasks": tasks}
            if ep:
                epics.setdefault(ep, {"key": ep, "title": clean(par["fields"]["summary"]), "a": None})
            if sk in DESC_SPRINTS and f.get("description"): desc[k] = adf_md(f["description"]).strip()
    # epics: assignee and description
    if epics:
        for x in search("key in (%s)" % ",".join(sorted(epics)), ["summary", "assignee", "description"]):
            epics[x["key"]].update({"title": clean(x["fields"]["summary"]), "a": first(x["fields"].get("assignee"))})
            if x["fields"].get("description"): desc[x["key"]] = adf_md(x["fields"]["description"]).strip()
    for s in old["stories"]:                   # backlog / next-sprint cards are kept as they were
        if s["sprint"] == "NEXT" and s["key"] not in stories:
            stories[s["key"]] = s
            if s.get("epic") and s["epic"] not in epics:
                e = next((e for e in old["epics"] if e["key"] == s["epic"]), None)
                if e: epics[e["key"]] = e
    for e in old["epics"]:
        if e["key"] not in epics and any(s.get("epic") == e["key"] for s in stories.values()): epics[e["key"]] = e
    merged_desc = {k: v for k, v in old["desc"].items() if k in stories or k in epics or any(k == t["key"] for s in stories.values() for t in s["tasks"])}
    merged_desc.update(desc)
    sp_list = [names[k] if k in names else {"id": k, "name": k.replace("S", "Sprint "), "r": ""} for k in keys] + [names.get("NEXT", {"id": "NEXT", "name": "Sprint 25 and backlog", "r": "To be planned"})]
    out = {"sprints": sp_list, "epics": sorted(epics.values(), key=lambda e: e["key"]), "stories": sorted(stories.values(), key=lambda s: (s["sprint"], s["key"])), "desc": merged_desc}
    (DATA / "map.json").write_text(json.dumps(out, separators=(",", ":")))
    (DATA / "burndown.json").write_text(json.dumps(bd, separators=(",", ":")))
    return total


def record(ok, issues, err=""):
    now = dt.datetime.now(dt.timezone.utc)
    ist = (now + dt.timedelta(hours=5, minutes=30)).date().isoformat()
    trig = "schedule" if ENV.get("GITHUB_EVENT_NAME") == "schedule" else "manual"
    by = "Scheduler" if trig == "schedule" else (ENV.get("GITHUB_ACTOR") or "Local run")
    rec = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "trigger": trig, "ok": ok, "issues": issues, "sprint": sprint_label(ist), "by": by}
    if err: rec["error"] = err[:200]
    p = DATA / "runs.json"
    runs = json.loads(p.read_text()) if p.exists() else []
    runs.append(rec)
    p.write_text(json.dumps(runs[-2000:], separators=(",", ":")))
    if ok:
        (DATA / "meta.json").write_text(json.dumps({"refreshedAt": rec["at"], "trigger": trig, "issues": issues, "sprint": rec["sprint"], "by": by}))


if __name__ == "__main__":
    if not all(ENV.get(k) for k in ("JIRA_BASE", "JIRA_EMAIL", "JIRA_TOKEN")):
        sys.exit("Missing JIRA_BASE, JIRA_EMAIL or JIRA_TOKEN")
    try:
        n = main()
    except Exception as ex:
        record(False, None, str(ex)); raise
    record(True, n)
    print("refreshed, issues pulled:", n)
