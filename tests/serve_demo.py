"""Local preview that uses REAL Jira data.  python3 tests/serve_demo.py [port]
Refresh runs the real script (scripts/refresh.py) against live Jira, in a scratch copy, so nothing in the repository changes.
Needs the Jira login in ../.env (JIRA_BASE, JIRA_EMAIL, JIRA_TOKEN)."""
import http.server, os, pathlib, re, shutil, subprocess, sys, tempfile, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import mockserver

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
root = pathlib.Path(__file__).resolve().parent.parent
env = dict(os.environ)
for p in (root / ".env", root.parent / ".env"):
    if p.exists():
        for l in p.read_text().splitlines():
            if "=" in l and not l.lstrip().startswith("#"):
                k, v = l.strip().split("=", 1); env.setdefault(k, v.strip("\"'"))
work = pathlib.Path(tempfile.mkdtemp(prefix="dash-preview-"))
shutil.copytree(root / "scripts", work / "scripts"); shutil.copytree(root / "data", work / "data")
html = re.sub(r"const REFRESH_URL = '[^']*';", "const REFRESH_URL = '/api/refresh';", (root / "index.html").read_text(), 1)
(work / "index.html").write_text(html)
run = lambda: subprocess.run([sys.executable, str(work / "scripts" / "refresh.py")], cwd=work, env=env, capture_output=True, text=True)
print("First pull from Jira ...", flush=True); r = run(); print((r.stdout + r.stderr).strip().splitlines()[-1], flush=True)   # start from live data

orig = http.server.ThreadingHTTPServer
class Fixed(orig):
    def __init__(self, addr, h): super().__init__(("127.0.0.1", port), h)
http.server.ThreadingHTTPServer = Fixed
m = mockserver.Mock(work, work / "data"); m.mode = "ok"
busy = threading.Lock()
def job():
    if not busy.acquire(blocking=False): return
    try:
        r = run(); print(time.strftime("%H:%M:%S"), "refresh:", (r.stdout + r.stderr).strip().splitlines()[-1], flush=True)
    finally: busy.release()
m.job = job
print(f"Preview: http://127.0.0.1:{port}/index.html  (sign in with the team password)  Refresh = real Jira pull", flush=True)
while True: time.sleep(3600)
