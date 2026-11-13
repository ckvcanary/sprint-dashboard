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
    const rr = await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=5");
    if (rr.ok) {
      const runs = (await rr.json()).workflow_runs || [];
      if (runs.some(r => ACTIVE.includes(r.status))) return res.status(202).json({ state: "running" });
      const done = runs.find(r => r.status === "completed" && r.conclusion === "success");
      if (done && Date.now() - Date.parse(done.updated_at) < FRESH_MS) return res.status(200).json({ state: "fresh", at: done.updated_at });
    }
    const since = new Date(Date.now() - DAY_MS).toISOString().replace(/\.\d+Z$/, "Z");
    const cr = await gh("/actions/workflows/" + WORKFLOW + "/runs?per_page=1&created=" + encodeURIComponent(">=" + since));
    if (cr.ok) { const n = (await cr.json()).total_count || 0; if (n >= LIMIT - RESERVE) return res.status(429).json({ state: "limit", used: n, limit: LIMIT }); }
    if (Date.now() - lastDispatch < 5000) return res.status(202).json({ state: "running" });   // two clicks in the same moment
    lastDispatch = Date.now();
    const r = await gh("/actions/workflows/" + WORKFLOW + "/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
    return r.ok ? res.status(200).json({ state: "started" }) : res.status(502).json({ state: "error", detail: "GitHub answered " + r.status });
  } catch (e) {
    return res.status(502).json({ state: "error", detail: "Could not reach GitHub" });
  }
};
