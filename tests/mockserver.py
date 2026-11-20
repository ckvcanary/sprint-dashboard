"""Local stand-in for the live site: serves the built page and the data files, and a fake refresh relay whose answer the tests choose.
Modes: ok, running, fresh, fail, noop, mismatch, stale_bd, since_ok, since_late, error502, forbidden. After `delay` seconds a successful refresh rewrites the data files."""
import http.server, json, pathlib, shutil, threading, time, urllib.parse

NEW_STAMP = "2026-11-13T11:12:00Z"
NEW_MS = 1794568320000      # NEW_STAMP in milliseconds, the "server time of the click" the relay returns in the since_* modes


class Mock:
    def __init__(self, site, pristine):
        self.site, self.pristine = pathlib.Path(site), pathlib.Path(pristine)
        self.mode, self.delay, self.posts, self.fake_counts = "ok", 1.5, [], True
        mock = self

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(s, *a, **k): super().__init__(*a, directory=str(mock.site), **k)
            def log_message(s, *a): pass
            def end_headers(s): s.send_header("Cache-Control", "no-store"); super().end_headers()
            def _send(s, code, obj):
                b = json.dumps(obj).encode(); s.send_response(code); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
            def do_POST(s):
                u = urllib.parse.urlparse(s.path); q = urllib.parse.parse_qs(u.query)
                if u.path == "/__ctl":
                    mock.mode = q.get("mode", ["ok"])[0]; mock.delay = float(q.get("delay", ["1.5"])[0]); return s._send(200, {"ok": True})
                if u.path == "/__reset":
                    mock.reset(); return s._send(200, {"ok": True})
                if u.path == "/__newer":    # newer data lands on the server without the page asking
                    mock.write(stamp=NEW_STAMP); return s._send(200, {"ok": True})
                if u.path == "/api/refresh":
                    mock.posts.append(time.time())
                    if mock.mode == "forbidden": return s._send(403, {"state": "denied"})
                    if mock.mode == "error502": return s._send(502, {"state": "error"})
                    if mock.mode == "limit": return s._send(429, {"state": "limit", "used": 96, "limit": 100})
                    if mock.mode == "fresh": return s._send(200, {"state": "fresh"})
                    if mock.mode in ("ok", "running", "fail", "mismatch", "stale_bd", "since_ok", "since_late", "nochange"):
                        threading.Thread(target=mock.job, daemon=True).start()
                    body = {"state": "running" if mock.mode == "running" else "started"}
                    if mock.mode == "since_ok": body["since"] = NEW_MS - 5000          # the pull started after the click: acceptable
                    if mock.mode == "since_late": body["since"] = NEW_MS + 60000       # the pull that arrives started BEFORE the click: must not count
                    return s._send(202 if mock.mode == "running" else 200, body)
                s._send(404, {})
            def do_GET(s):
                if s.path.startswith("/__posts"): return s._send(200, {"n": len(mock.posts)})
                super().do_GET()

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    url = property(lambda s: f"http://127.0.0.1:{s.port}")

    def reset(self):
        self.mode, self.delay, self.posts = "ok", 1.5, []
        shutil.rmtree(self.site / "data", ignore_errors=True); shutil.copytree(self.pristine, self.site / "data")

    def write(self, stamp=NEW_STAMP, ok=True, map_stamp=None, error=None):
        d = self.site / "data"; rj = lambda n: json.loads((d / f"{n}.json").read_text())
        meta, m, runs = rj("meta"), rj("map"), rj("runs")
        if ok and self.mode != "stale_bd":
            b = rj("burndown")
            for v in b.values(): v["asOf"] = stamp
            if self.mode != "nochange":      # a real pull brings something new: Nikita logged 2 more hours
                try: lg = b["S24"]["people"]["Nikita"]["logs"]; lg["2026-11-12"] = round(lg.get("2026-11-12", 0) + 2, 1)
                except KeyError: pass
            (d / "burndown.json").write_text(json.dumps(b))
        if ok and self.mode != "nochange" and "info" in m:      # a real pull brings something new: two more hours on one ticket
            m["info"]["PROD-9111"]["lg"] = round(m["info"]["PROD-9111"]["lg"] + 2, 2)
        if ok:
            meta.update({"refreshedAt": stamp, **({"issues": 1077, "sprintIssues": 14} if self.fake_counts else {})}); m["asOf"] = map_stamp or stamp
            (d / "map.json").write_text(json.dumps(m)); (d / "meta.json").write_text(json.dumps(meta))
        runs.append({"at": stamp, "trigger": "manual", "ok": ok, "issues": 1077 if ok else 0, "sprint": "Sprint 24", "by": "tester", **({"error": error} if error else {})})
        (d / "runs.json").write_text(json.dumps(runs))

    def job(self):
        time.sleep(self.delay)
        if self.mode == "fail": self.write(ok=False, error="Jira answered 401")
        elif self.mode == "mismatch": self.write(map_stamp="2026-11-13T09:00:00Z")
        else: self.write()
