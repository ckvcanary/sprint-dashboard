// Refresh relay on Vercel. The dashboard calls this; it starts the GitHub job.
// The token is a private Vercel setting named GH_TOKEN (fine-grained: this repo only, Actions: Read and write). The page never sees it.
const REPO = "ckvcanary/sprint-dashboard", WORKFLOW = "refresh.yml", ORIGINS = ["https://ckvcanary.github.io", "https://sprint-dashboard-umber.vercel.app"];
let last = 0;
module.exports = async (req, res) => {
  const o = req.headers.origin, ok = ORIGINS.includes(o);
  res.setHeader("Access-Control-Allow-Origin", ok ? o : ORIGINS[0]);
  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST" || !ok) return res.status(403).send("Not allowed");
  if (Date.now() - last < 60000) return res.status(202).send("Already refreshing");   // one refresh a minute
  last = Date.now();
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { Authorization: "Bearer " + process.env.GH_TOKEN, Accept: "application/vnd.github+json", "User-Agent": "sprint-dashboard-relay", "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main" }),
  });
  res.status(r.ok ? 200 : 502).send(r.ok ? "Started" : "GitHub answered " + r.status);
};
