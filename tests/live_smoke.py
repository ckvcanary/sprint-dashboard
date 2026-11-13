"""Post-deploy check of the live Vercel link. Read-only apart from the optional --refresh step.
Run: python3 tests/live_smoke.py [https://sprint-dashboard-umber.vercel.app] [--refresh]
Checks the page, the data files, the relay's rules, and (with --refresh) one real end-to-end refresh with timing."""
import json, re, sys, time, urllib.error, urllib.request

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "https://sprint-dashboard-umber.vercel.app").rstrip("/")
PAGES = "https://ckvcanary.github.io"
res = []


def check(name, ok, detail=""): res.append(ok); print(("PASS  " if ok else "FAIL  ") + name + (("  " + detail) if detail else ""), flush=True)


def req(url, method="GET", headers=None, data=None):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=30) as x: return x.status, dict(x.headers), x.read()
    except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read()


s, h, b = req(BASE + "/"); html = b.decode("utf-8", "ignore")
check("Page loads", s == 200 and "Sprint Dashboard" in html, f"HTTP {s}, {len(b) // 1024} KB")
check("Page asks for the team password first", 'id="gate"' in html and "GATE_HASH" in html)
check("Page points the Refresh button at this site's relay", "/api/refresh" in html)
for f in ("map", "burndown", "meta", "runs"):
    s, h, b = req(f"{BASE}/data/{f}.json?v={int(time.time())}")
    try: ok = s == 200 and json.loads(b) is not None
    except ValueError: ok = False
    check(f"data/{f}.json is valid", ok, f"HTTP {s}, cache-control: {h.get('Cache-Control', h.get('cache-control', '-'))}")
meta = json.loads(req(f"{BASE}/data/meta.json?v={int(time.time())}")[2]); m = json.loads(req(f"{BASE}/data/map.json?v={int(time.time())}")[2])
check("Map and meta carry the same pull stamp (the page's own verification)", m.get("asOf") == meta.get("refreshedAt"), f"map {m.get('asOf')}, meta {meta.get('refreshedAt')}  (an older deploy without the stamp fails this until the first refresh)")
age = (time.time() - time.mktime(time.strptime(meta["refreshedAt"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone) / 3600
check("Data is fresh enough (under 14 hours old)", age < 14, f"{age:.1f} h old")
# the relay's rules
URL = BASE + "/api/refresh"
s, h, b = req(URL, "OPTIONS", {"Origin": BASE, "Access-Control-Request-Method": "POST"}); check("Relay answers the browser's preflight for this site", s == 204 and h.get("access-control-allow-origin", h.get("Access-Control-Allow-Origin")) == BASE, f"HTTP {s}")
s, h, b = req(URL, "OPTIONS", {"Origin": PAGES, "Access-Control-Request-Method": "POST"}); check("Relay also allows the GitHub Pages backup", s == 204 and h.get("access-control-allow-origin", h.get("Access-Control-Allow-Origin")) == PAGES)
s, h, b = req(URL, "POST", {"Origin": "https://evil.example"}, b""); check("Relay refuses another website", s == 403, f"HTTP {s}")
s, h, b = req(URL, "GET", {"Origin": BASE}); check("Relay refuses a plain GET", s == 403, f"HTTP {s}")
s, h, b = req(URL, "POST", {}, b""); check("Relay refuses a call with no origin", s == 403, f"HTTP {s}")
if "--refresh" in sys.argv:
    before = meta["refreshedAt"]; t0 = time.time(); s, h, b = req(URL, "POST", {"Origin": BASE}, b"")
    try: state = json.loads(b).get("state")
    except ValueError: state = None
    check("Relay accepts a real refresh", s in (200, 202) and state in ("started", "running", "fresh"), f"HTTP {s}, state {state}")
    if state in ("started", "running"):
        done = None
        for _ in range(80):
            time.sleep(3); m2 = json.loads(req(f"{BASE}/data/meta.json?v={int(time.time())}")[2])
            if m2["refreshedAt"] != before: done = m2; break
        check("New data appeared on Vercel", bool(done), f"{time.time() - t0:.0f} s after the click" if done else "no change after 4 minutes")
        if done: mp = json.loads(req(f"{BASE}/data/map.json?v={int(time.time())}")[2]); check("The new map matches the new pull stamp", mp.get("asOf") == done["refreshedAt"])
print("\nRESULT:", "ALL PASS" if all(res) else f"{res.count(False)} CHECK(S) FAILED"); sys.exit(0 if all(res) else 1)
