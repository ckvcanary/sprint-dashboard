"""The Vercel relay (api/refresh.js) run against a pretend GitHub"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "api" / "refresh.js").read_text()
HARNESS = """async ({src, origin, method, runs, runsStatus, dispatchStatus, twice, total}) => {
  const calls = []; const process = {env: {GH_TOKEN: 'test-token'}};
  runs = runs.map(r => r.ago != null ? Object.assign({}, r, {updated_at: new Date(Date.now() - r.ago * 1000).toISOString()}) : r);
  const fetch = async (url, opt) => { calls.push({url, method: (opt||{}).method || 'GET', auth: ((opt||{}).headers||{}).Authorization, body: (opt||{}).body});
    if (url.includes('/runs')) return {ok: runsStatus === 200, status: runsStatus, json: async () => ({workflow_runs: runs, total_count: total == null ? runs.length : total})};
    return {ok: dispatchStatus === 204, status: dispatchStatus}; };
  const module = {exports: {}}; new Function('module', 'process', 'fetch', 'Date', src)(module, process, fetch, Date);
  const run = async () => { const out = {headers: {}}; const res = {setHeader: (k, v) => out.headers[k] = v, status: c => (out.code = c, res), json: o => (out.body = o, res), end: () => res};
    await module.exports({method, headers: {origin}}, res); return out; };
  const a = await run(); const b = twice ? await run() : null; return {a, b, calls};
}"""
HARNESS_PARALLEL = """async ({src, origin, n}) => {
  const calls = []; const state = {active: false}; const process = {env: {GH_TOKEN: 't'}};
  const fetch = async (url, opt) => { await new Promise(r => setTimeout(r, Math.random() * 20)); const method = (opt || {}).method || 'GET'; calls.push(method);
    if (url.includes('/runs')) return {ok: true, status: 200, json: async () => ({workflow_runs: state.active ? [{status: 'queued'}] : [], total_count: 3})};
    state.active = true; return {ok: true, status: 204}; };
  const module = {exports: {}}; new Function('module', 'process', 'fetch', 'Date', src)(module, process, fetch, Date);
  const one = async () => { const out = {}; const res = {setHeader: () => {}, status: c => (out.code = c, res), json: o => (out.body = o, res), end: () => res};
    await module.exports({method: 'POST', headers: {origin}}, res); return out.body.state; };
  const states = await Promise.all(Array.from({length: n}, one)); return {states, dispatches: calls.filter(m => m === 'POST').length};
}"""
ALLOWED = "https://sprint-dashboard-umber.vercel.app"


def call(page, **k):
    base = dict(src=SRC, origin=ALLOWED, method="POST", runs=[], runsStatus=200, dispatchStatus=204, twice=False, total=None); base.update(k)
    return page.evaluate(HARNESS, base)


def iso(sec_ago):
    return sec_ago      # turned into a time inside the page, so it follows the page clock


def test_idle_relay_starts_the_workflow(page):
    r = call(page, runs=[{"status": "completed", "conclusion": "success", "ago": iso(900)}])
    assert r["a"]["code"] == 200 and r["a"]["body"]["state"] == "started"
    d = [c for c in r["calls"] if c["method"] == "POST"]; assert len(d) == 1 and d[0]["url"].endswith("/actions/workflows/refresh.yml/dispatches") and json.loads(d[0]["body"]) == {"ref": "main"}
    assert all(c["auth"] == "Bearer test-token" for c in r["calls"])


def test_running_workflow_is_joined_not_started_again(page):
    for st in ("queued", "in_progress", "waiting", "pending", "requested"):
        r = call(page, runs=[{"status": st}]); assert r["a"]["code"] == 202 and r["a"]["body"]["state"] == "running" and not [c for c in r["calls"] if c["method"] == "POST"], st


def test_recent_success_counts_as_current(page):
    r = call(page, runs=[{"status": "completed", "conclusion": "success", "ago": iso(60)}])
    assert r["a"]["body"]["state"] == "fresh" and not [c for c in r["calls"] if c["method"] == "POST"]


def test_failed_recent_run_does_not_block_a_new_one(page):
    r = call(page, runs=[{"status": "completed", "conclusion": "failure", "ago": iso(30)}]); assert r["a"]["body"]["state"] == "started"


def test_two_clicks_in_the_same_moment_dispatch_once(page):
    r = call(page, twice=True); assert len([c for c in r["calls"] if c["method"] == "POST"]) == 1 and r["b"]["body"]["state"] == "running"


def test_unknown_origin_and_wrong_method_are_refused(page):
    assert call(page, origin="https://evil.example")["a"]["code"] == 403 and call(page, method="GET")["a"]["code"] == 403
    assert not [c for c in call(page, origin="https://evil.example")["calls"]]


def test_both_team_links_are_allowed_and_preflight_works(page):
    for o in ("https://ckvcanary.github.io", "https://sprint-dashboard-umber.vercel.app"):
        r = call(page, origin=o); assert r["a"]["headers"]["Access-Control-Allow-Origin"] == o
    assert call(page, method="OPTIONS")["a"]["code"] == 204


def test_github_trouble_is_reported_as_502_and_status_lookup_failure_still_dispatches(page):
    assert call(page, dispatchStatus=500)["a"]["code"] == 502
    r = call(page, runsStatus=500); assert r["a"]["body"]["state"] == "started"


def test_relay_stops_at_95_refreshes_in_24_hours_and_says_so(page):
    r = call(page, runs=[{"status": "completed", "conclusion": "success", "ago": 900}], total=95)
    assert r["a"]["code"] == 429 and r["a"]["body"] == {"state": "limit", "used": 95, "limit": 100} and not [c for c in r["calls"] if c["method"] == "POST"]
    r = call(page, runs=[{"status": "completed", "conclusion": "success", "ago": 900}], total=94); assert r["a"]["body"]["state"] == "started"


def test_joining_a_running_refresh_is_allowed_even_at_the_limit(page):
    r = call(page, runs=[{"status": "in_progress"}], total=99); assert r["a"]["body"]["state"] == "running"
