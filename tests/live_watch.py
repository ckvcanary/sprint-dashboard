"""Watches the live site for the next scheduled (cron) pull and whether an already-open page updates by itself.
Run: LIVE_URL=https://sprint-dashboard-umber.vercel.app python3 tests/live_watch.py [hours]
Keeps one signed-in browser tab open on the live link, then logs: when GitHub starts the scheduled run, when the data lands on Vercel,
and when the open page updates itself (the 'Data updated' message)."""
import json, os, sys, time, urllib.request, datetime as dt
from playwright.sync_api import sync_playwright

URL = os.environ.get("LIVE_URL", "https://sprint-dashboard-umber.vercel.app").rstrip("/"); HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 20
SESSION = "fa9304349b9d"
now = lambda: dt.datetime.now().strftime("%a %d %b %H:%M:%S")
def log(s): print(f"[{now()}] {s}", flush=True)
def get(u): return json.load(urllib.request.urlopen(u, timeout=30))
def sched_runs(): return get("https://api.github.com/repos/ckvcanary/sprint-dashboard/actions/runs?event=schedule&per_page=5")["workflow_runs"]

seen = {r["id"] for r in sched_runs()}; log(f"watching {URL}; scheduled runs already on record: {len(seen)}")
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True); c = b.new_context(viewport={"width": 1440, "height": 900}); c.add_init_script(f"localStorage.setItem('sd_auth','{SESSION}')")
    pg = c.new_page(); pg.goto(URL + "/"); pg.wait_for_selector("#map .card"); start = pg.evaluate("META.refreshedAt"); log(f"open page shows data refreshed at {start}")
    t_end = time.time() + HOURS * 3600; handled = set(seen); last_stamp = start
    while time.time() < t_end:
        time.sleep(20)
        try:
            for r in sched_runs():
                if r["id"] in handled: continue
                handled.add(r["id"]); log(f"CRON FIRED: GitHub started a scheduled run at {r['created_at']}")
                for _ in range(30):       # wait for it to finish (up to 10 minutes)
                    time.sleep(20); cur = [x for x in sched_runs() if x["id"] == r["id"]][0]
                    if cur["status"] == "completed": break
                log(f"  that run finished: {cur['conclusion']}")
                time.sleep(25); m = get(f"{URL}/data/meta.json?v={int(time.time())}")
                if m["refreshedAt"] == last_stamp: log("  it stood down (this slot already had a scheduled pull), so no new data, as designed"); continue
                log(f"  DATA LIVE ON VERCEL: new pull {m['refreshedAt']} (trigger {m.get('trigger')})"); last_stamp = m["refreshedAt"]
                for _ in range(15):
                    time.sleep(20)
                    if pg.evaluate("META.refreshedAt") == m["refreshedAt"]:
                        log(f"  OPEN PAGE UPDATED ITSELF: header reads '{pg.inner_text('#rfval')}'; messages on screen: {pg.locator('.tst').all_inner_texts()}"); log("RESULT: cron ran and the open page updated"); b.close(); sys.exit(0)
                log("  the open page did NOT update within 5 minutes")
        except SystemExit: raise
        except Exception as e: log(f"(check failed, will retry: {e})")
    log("RESULT: window ended"); b.close()
