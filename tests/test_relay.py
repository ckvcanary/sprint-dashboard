"""The Vercel relay (api/refresh.js) run against a pretend GitHub"""
import pytest

pytestmark = pytest.mark.guard
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


HARNESS_CRON = """async ({src, origin, ua, nowIso, runs}) => {
  const calls = []; const process = {env: {GH_TOKEN: 't'}}; const T = Date.parse(nowIso);
  class FakeDate extends Date { constructor(...a) { a.length ? super(...a) : super(T); } static now() { return T; } }
  const fetch = async (url, opt) => { calls.push({url, method: (opt||{}).method || 'GET', body: (opt||{}).body});
    if (url.includes('/runs')) return {ok: true, status: 200, json: async () => ({workflow_runs: runs, total_count: 3})};
    return {ok: true, status: 204}; };
  const module = {exports: {}}; new Function('module', 'process', 'fetch', 'Date', src)(module, process, fetch, FakeDate);
  const out = {}; const res = {setHeader: () => {}, status: c => (out.code = c, res), json: o => (out.body = o, res), end: () => res};
  await module.exports({method: 'POST', headers: {origin, 'user-agent': ua}}, res);
  return {out, dispatch: calls.filter(c => c.method === 'POST').map(c => JSON.parse(c.body))};
}"""
CRON_UA = "Mozilla/4.0 (compatible; cron-job.org; http://cron-job.org/abuse/)"


def cron_call(page, ua, ist, runs=()):
    return page.evaluate(HARNESS_CRON, dict(src=SRC, origin=ALLOWED, ua=ua, nowIso=ist, runs=list(runs)))


def test_cron_job_call_inside_a_slot_is_a_scheduled_pull(page):
    for ist in ("2026-11-17T10:45:30+05:30", "2026-11-17T11:10:00+05:30", "2026-11-17T18:45:10+05:30"):   # Tue 17 Nov
        r = cron_call(page, CRON_UA, ist)
        assert r["out"]["body"]["state"] == "started" and r["dispatch"] == [{"ref": "main", "inputs": {"source": "cron-job.org"}}], ist


def test_cron_job_call_still_starts_when_a_run_is_going_or_data_is_fresh(page):
    busy = [{"status": "in_progress"}]
    fresh = [{"status": "completed", "conclusion": "success", "updated_at": "2026-11-17T10:44:50+05:30"}]
    for runs in (busy, fresh):
        r = cron_call(page, CRON_UA, "2026-11-17T10:45:00+05:30", runs)
        assert r["out"]["body"]["state"] == "started" and r["dispatch"][0]["inputs"] == {"source": "cron-job.org"}


def test_cron_job_call_outside_a_slot_is_a_plain_manual_refresh(page):
    for ist in ("2026-11-17T11:32:00+05:30", "2026-11-17T14:00:00+05:30", "2026-11-21T11:40:00+05:30", "2026-11-22T19:40:00+05:30"):   # test run, afternoon, and after the window on a Saturday and a Sunday
        r = cron_call(page, CRON_UA, ist)
        assert r["dispatch"] == [{"ref": "main"}], ist


def test_a_dashboard_click_inside_a_slot_window_is_not_a_scheduled_pull(page):
    r = cron_call(page, "Mozilla/5.0 Chrome", "2026-11-17T10:45:00+05:30")
    assert r["dispatch"] == [{"ref": "main"}]


def test_cron_job_org_at_1055_and_1855_ist_counts_as_scheduled(page):
    for ist in ("2026-11-17T10:50:20+05:30", "2026-11-17T18:55:05+05:30", "2026-11-18T10:45:00+05:30"):
        r = cron_call(page, CRON_UA, ist); assert r["dispatch"] == [{"ref": "main", "inputs": {"source": "cron-job.org"}}], ist


def test_window_edges(page):
    for ist, scheduled in (("2026-11-17T10:20:00+05:30", True), ("2026-11-17T11:20:00+05:30", True), ("2026-11-17T10:10:00+05:30", False), ("2026-11-17T11:30:00+05:30", False), ("2026-11-17T18:20:00+05:30", True), ("2026-11-17T19:20:00+05:30", True), ("2026-11-17T18:10:00+05:30", False), ("2026-11-17T19:30:00+05:30", False), ("2026-11-22T10:50:00+05:30", True), ("2026-11-21T18:55:00+05:30", True)):
        r = cron_call(page, CRON_UA, ist); assert (r["dispatch"][0].get("inputs") is not None) == scheduled, ist


HARNESS_MODE = """async ({src, origin, ua, nowIso, mode, runs, tokenOk}) => {
  const calls = []; const process = {env: {GH_TOKEN: 't'}}; const T = Date.parse(nowIso);
  class FakeDate extends Date { constructor(...a) { a.length ? super(...a) : super(T); } static now() { return T; } }
  const fetch = async (url, opt) => { calls.push({url, method: (opt||{}).method || 'GET', body: (opt||{}).body});
    if (url.includes('raw.githubusercontent.com')) return {ok: true, status: 200, json: async () => runs};
    if (url.endsWith('/repos/ckvcanary/sprint-dashboard')) return {ok: tokenOk, status: tokenOk ? 200 : 401, json: async () => ({})};
    if (url.includes('/runs')) return {ok: true, status: 200, json: async () => ({workflow_runs: [], total_count: 3})};
    return {ok: true, status: 204}; };
  const module = {exports: {}}; new Function('module', 'process', 'fetch', 'Date', 'URL', src)(module, process, fetch, FakeDate, URL);
  const out = {}; const res = {setHeader: () => {}, status: c => (out.code = c, res), json: o => (out.body = o, res), end: () => res};
  await module.exports({method: 'POST', url: '/api/refresh' + (mode ? '?mode=' + mode : ''), headers: {origin, 'user-agent': ua}}, res);
  return {out, dispatch: calls.filter(c => c.method === 'POST').map(c => JSON.parse(c.body)), fetched: calls.map(c => c.url)};
}"""


def mode_call(page, mode, ist="2026-11-17T11:05:00+05:30", runs=(), token_ok=True):
    return page.evaluate(HARNESS_MODE, dict(src=SRC, origin=ALLOWED, ua=CRON_UA, nowIso=ist, mode=mode, runs=list(runs), tokenOk=token_ok))


def test_warm_call_wakes_the_relay_checks_github_and_starts_nothing(page):
    r = mode_call(page, "warm", "2026-11-17T10:50:00+05:30"); assert r["out"]["code"] == 200 and r["out"]["body"]["state"] == "warm" and r["out"]["body"]["github"] == "ok" and r["dispatch"] == []
    r = mode_call(page, "warm", "2026-11-17T10:50:00+05:30", token_ok=False); assert r["out"]["code"] == 502 and "token problem (401)" in r["out"]["body"]["github"] and r["dispatch"] == [], "a broken token is visible before the slot"


def test_catchup_pulls_only_when_the_slot_was_missed(page):
    done = [{"at": "2026-11-17T05:26:10Z", "trigger": "schedule", "ok": True}]            # a scheduled pull at 10:56 AM IST
    r = mode_call(page, "catchup", "2026-11-17T11:05:00+05:30", done); assert r["out"]["body"]["state"] == "already pulled" and r["dispatch"] == []
    r = mode_call(page, "catchup", "2026-11-17T11:05:00+05:30", []); assert r["out"]["body"]["state"] == "started" and r["dispatch"] == [{"ref": "main", "inputs": {"source": "cron-job.org"}}]
    old = [{"at": "2026-11-16T13:26:10Z", "trigger": "schedule", "ok": True}]; r = mode_call(page, "catchup", "2026-11-17T11:05:00+05:30", old); assert r["out"]["body"]["state"] == "started", "yesterday's pull does not count"
    manual = [{"at": "2026-11-17T05:26:10Z", "trigger": "manual", "ok": True}]; r = mode_call(page, "catchup", "2026-11-17T11:05:00+05:30", manual); assert r["out"]["body"]["state"] == "started", "a manual refresh does not fill a scheduled slot"
    failed = [{"at": "2026-11-17T05:26:10Z", "trigger": "schedule", "ok": False}]; r = mode_call(page, "catchup", "2026-11-17T18:35:00+05:30", failed); assert r["out"]["body"]["state"] == "started"


def test_weekend_slots_count_too(page):
    for ist in ("2026-11-21T10:50:10+05:30", "2026-11-22T18:55:10+05:30"):      # Saturday and Sunday
        r = cron_call(page, CRON_UA, ist); assert r["dispatch"] == [{"ref": "main", "inputs": {"source": "cron-job.org"}}], ist
