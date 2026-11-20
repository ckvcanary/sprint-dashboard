// Refresh relay on Vercel. The dashboard calls this; it starts the GitHub job.
// The token is a private Vercel setting named GH_TOKEN (fine-grained: this repo only, Actions: Read and write). The page never sees it.
// A click never waits on a timer. A run that is queued has not read Jira yet, so a click joins it. A run that is already reading Jira may have read it before the new time log, so a new run is queued behind it (GitHub keeps one waiting run at most, so many clicks collapse into one).
// and refreshes stop at 95 in 24 hours (the free Vercel plan allows 100 deployments a day and every refresh publishes the site once; 5 stay free for the scheduled pulls).
const REPO = "ckvcanary/sprint-dashboard", WORKFLOW = "refresh.yml";
const ORIGINS = ["https://ckvcanary.github.io", "https://sprint-dashboard-umber.vercel.app"];
const ACTIVE = ["queued", "in_progress", "waiting", "pending", "requested"], LIMIT = 100, RESERVE = 5, DAY_MS = 86400000;
const gh = (path, opt = {}) => fetch("https://api.github.com/repos/" + REPO + path, Object.assign({}, opt, {
  headers: { Authorization: "Bearer " + process.env.GH_TOKEN, Accept: "application/vnd.github+json", "User-Agent": "sprint-dashboard-relay", "Content-Type": "application/json" },
}));
// The cron-job.org timer calls this relay at 10:50 AM and 6:50 PM IST every day, weekends included, the same time as the GitHub schedule (30 minutes either side of a slot counts as that slot). A call from cron-job.org inside a slot window is a scheduled pull:
// it always starts a run (the workflow queues it behind one already running) and tells the workflow so, so the Pull log records the slot as Pulled.
const SLOTS = [[10, 50], [18, 50]], WINDOW_MS = 30 * 60000;
function inSlotWindow(now) {
  const ist = new Date(now + 5.5 * 3600e3);
  const mins = ist.getUTCHours() * 60 + ist.getUTCMinutes();
  return SLOTS.some(([h, m]) => Math.abs(mins - (h * 60 + m)) * 60000 <= WINDOW_MS);
}
const fromCronJob = (req, now) => /cron-job\.org/i.test(req.headers["user-agent"] || "") && inSlotWindow(now);
// Two extra calls from cron-job.org make the 10:50 AM and 6:50 PM pulls safe:
//   ?mode=warm     at 10:50 AM and 6:50 PM: wakes this function and checks that GitHub and the token answer; starts nothing.
//   ?mode=catchup  at 11:05 AM and 7:05 PM: starts a scheduled pull only when no scheduled pull worked in the last 2 hours (read from the public data/runs.json).
const RUNS_URL = "https://raw.githubusercontent.com/" + REPO + "/main/data/runs.json", CATCHUP_MS = 120 * 60000;
const modeOf = req => { try { return new URL(req.url || "/", "http://relay").searchParams.get("mode") || ""; } catch (e) { return ""; } };
async function lastScheduledPull() {
  try { const r = await fetch(RUNS_URL + "?v=" + Date.now()); if (!r.ok) return 0; const runs = await r.json(); const ok = runs.filter(x => x.trigger === "schedule" && x.ok).map(x => Date.parse(x.at)); return ok.length ? Math.max(...ok) : 0; } catch (e) { return 0; }
}
// Decides and dispatches one click. Clicks that arrive while this is still being decided share it (no timer): GitHub would only keep one waiting run anyway, so a burst of clicks must not use up the daily run count.
async function startClick(cron) {
  const rr = cron ? { ok: false } : await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=5");
  let followUp = false;
  if (rr.ok) {
    const runs = (await rr.json()).workflow_runs || [];
    const active = runs.filter(r => ACTIVE.includes(r.status));
    if (active.length) {
      const waiting = active.some(r => r.status !== "in_progress");      // queued: it has not read Jira yet, so it will include whatever was logged before this click
      if (waiting) return [202, { state: "running", since: Date.now() }];
      followUp = true;     // the running pull already read Jira and may have missed a new log, so one more pull is queued behind it
    }
  }
  const since = new Date(Date.now() - DAY_MS).toISOString().replace(/\.\d+Z$/, "Z");
  const cr = await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=1&created=" + encodeURIComponent(">=" + since));
  if (cr.ok) { const n = (await cr.json()).total_count || 0; if (n >= LIMIT - RESERVE) return [429, { state: "limit", used: n, limit: LIMIT }]; }
  const r = await gh("/actions/workflows/" + WORKFLOW + "/dispatches", { method: "POST", body: JSON.stringify(cron ? { ref: "main", inputs: { source: "cron-job.org" } } : { ref: "main" }) });
  return r.ok ? [200, { state: followUp ? "queued" : "started", since: Date.now() }] : [502, { state: "error", detail: "GitHub answered " + r.status }];
}
let deciding = null;
module.exports = async (req, res) => {
  const o = req.headers.origin, ok = ORIGINS.includes(o);
  res.setHeader("Access-Control-Allow-Origin", ok ? o : ORIGINS[0]);
  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST" || !ok) return res.status(403).json({ state: "denied" });
  try {
    const mode = modeOf(req);
    if (mode === "warm") {
      const t0 = Date.now(); let github = "unreachable";
      try { const r = await gh(""); github = r.ok ? "ok" : "token problem (" + r.status + ")"; } catch (e) {}
      return res.status(github === "ok" ? 200 : 502).json({ state: "warm", github, ms: Date.now() - t0 });
    }
    if (mode === "catchup") {
      const at = await lastScheduledPull();
      if (at && Date.now() - at < CATCHUP_MS) return res.status(200).json({ state: "already pulled", at: new Date(at).toISOString() });
    }
    const cron = fromCronJob(req, Date.now());
    if (!cron && deciding) { const [code, out] = await deciding; return code === 200 ? res.status(202).json({ state: "running", since: Date.now() }) : res.status(code).json(out); }
    const job = startClick(cron); if (!cron) deciding = job;
    try { const [code, out] = await job; return res.status(code).json(out); } finally { if (deciding === job) deciding = null; }
  } catch (e) {
    return res.status(502).json({ state: "error", detail: "Could not reach GitHub" });
  }
};

module.exports.inSlotWindow = inSlotWindow;
