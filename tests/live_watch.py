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
    t_end = time.time() + HOURS * 3600; run_seen = None; data_seen = None
    while time.time() < t_end:
        time.sleep(20)
        try:
            for r in sched_runs():
                if r["id"] not in seen and run_seen is None:
                    run_seen = r; log(f"CRON FIRED: GitHub started a scheduled run at {r['created_at']} (status {r['status']})")
            if run_seen and run_seen["id"] and data_seen is None:
                m = get(f"{URL}/data/meta.json?v={int(time.time())}")
                if m["refreshedAt"] != start: data_seen = m; log(f"DATA LIVE ON VERCEL: new pull {m['refreshedAt']} (trigger {m.get('trigger')})")
            if data_seen:
                shown = pg.evaluate("META.refreshedAt"); toast = pg.locator(".tst").all_inner_texts()
                if shown == data_seen["refreshedAt"]:
                    log(f"OPEN PAGE UPDATED ITSELF: header now reads '{pg.inner_text('#rfval')}'; messages: {toast}"); log("RESULT: cron ran and the open page updated"); break
        except Exception as e: log(f"(check failed, will retry: {e})")
    else: log("RESULT: nothing happened within the watch window")
    b.close()
