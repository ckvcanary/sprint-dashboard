// Refresh relay on Vercel. The dashboard calls this; it starts the GitHub job.
// The token is a private Vercel setting named GH_TOKEN (fine-grained: this repo only, Actions: Read and write). The page never sees it.
// Many people can click at once: a refresh already running is joined (not started again), a pull finished under 2 minutes ago counts as current,
// and refreshes stop at 95 in 24 hours (the free Vercel plan allows 100 deployments a day and every refresh publishes the site once; 5 stay free for the scheduled pulls).
const REPO = "ckvcanary/sprint-dashboard", WORKFLOW = "refresh.yml";
const ORIGINS = ["https://ckvcanary.github.io", "https://sprint-dashboard-umber.vercel.app"];
const FRESH_MS = 120000, ACTIVE = ["queued", "in_progress", "waiting", "pending", "requested"], LIMIT = 100, RESERVE = 5, DAY_MS = 86400000;
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
let lastDispatch = 0;
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
    const rr = cron ? { ok: false } : await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=5");
    if (rr.ok) {
      const runs = (await rr.json()).workflow_runs || [];
      if (runs.some(r => ACTIVE.includes(r.status))) return res.status(202).json({ state: "running" });
      const done = runs.find(r => r.status === "completed" && r.conclusion === "success");
      if (done && Date.now() - Date.parse(done.updated_at) < FRESH_MS) return res.status(200).json({ state: "fresh", at: done.updated_at });
    }
    const since = new Date(Date.now() - DAY_MS).toISOString().replace(/\.\d+Z$/, "Z");
    const cr = await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=1&created=" + encodeURIComponent(">=" + since));
    if (cr.ok) { const n = (await cr.json()).total_count || 0; if (n >= LIMIT - RESERVE) return res.status(429).json({ state: "limit", used: n, limit: LIMIT }); }
    if (!cron && Date.now() - lastDispatch < 5000) return res.status(202).json({ state: "running" });   // two clicks in the same moment
    lastDispatch = Date.now();
    const r = await gh("/actions/workflows/" + WORKFLOW + "/dispatches", { method: "POST", body: JSON.stringify(cron ? { ref: "main", inputs: { source: "cron-job.org" } } : { ref: "main" }) });
    return r.ok ? res.status(200).json({ state: "started" }) : res.status(502).json({ state: "error", detail: "GitHub answered " + r.status });
  } catch (e) {
    return res.status(502).json({ state: "error", detail: "Could not reach GitHub" });
  }
};

module.exports.inSlotWindow = inSlotWindow;
