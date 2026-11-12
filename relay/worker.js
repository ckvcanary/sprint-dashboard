// Refresh relay (Cloudflare Worker). The dashboard calls this; the worker starts the GitHub job.
// The GitHub token lives only here, as the secret GH_TOKEN (fine-grained token: this repo only, Actions: Read and write).
const REPO = "ckvcanary/sprint-dashboard", WORKFLOW = "refresh.yml", ORIGIN = "https://ckvcanary.github.io";
const cors = { "Access-Control-Allow-Origin": ORIGIN, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" };
let last = 0;
export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST" || req.headers.get("Origin") !== ORIGIN) return new Response("Not allowed", { status: 403, headers: cors });
    if (Date.now() - last < 60000) return new Response("Already refreshing", { status: 202, headers: cors });   // one refresh a minute
    last = Date.now();
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST", headers: { Authorization: "Bearer " + env.GH_TOKEN, Accept: "application/vnd.github+json", "User-Agent": "sprint-dashboard-relay", "Content-Type": "application/json" }, body: JSON.stringify({ ref: "main" }) });
    return new Response(r.ok ? "Started" : "GitHub answered " + r.status, { status: r.ok ? 200 : 502, headers: cors });
  },
};
