import datetime as dt, os, pathlib, re, shutil, subprocess, sys, tempfile, urllib.request
import pytest
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fixture, mockserver

PASSWORD = os.environ.get("DASH_PASSWORD")      # the team password is never stored in the repository; set it when running the tests
if not PASSWORD: raise pytest.UsageError("Set DASH_PASSWORD to the team password before running the tests")
SESSION = "fa9304349b9d"      # what the page keeps in the browser after sign-in (the first 12 characters of the password hash)
NOW = dt.datetime(2026, 11, 13, 11, 10, tzinfo=dt.timezone.utc)   # 4:40 PM IST, six minutes after the pull in the fixture


@pytest.fixture(scope="session")
def mock(tmp_path_factory):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True, capture_output=True, cwd=ROOT)
    site = tmp_path_factory.mktemp("site"); pristine = tmp_path_factory.mktemp("pristine") / "data"
    fixture.build(pristine)
    html = (ROOT / "index.html").read_text()
    html = re.sub(r"const REFRESH_URL = '[^']*';", "const REFRESH_URL = '/api/refresh';", html, 1)       # the fake relay replaces the real one
    html = html.replace("const CAP = 64,", "window.RF_TEST = window.RF_TEST || {}; const CAP = 64,", 1) if False else html
    (site / "index.html").write_text(html)
    m = mockserver.Mock(site, pristine); m.reset()
    yield m
    m.srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        yield b
        b.close()


@pytest.fixture
def ctx_factory(browser, mock):
    made = []
    def make(width=1440, height=900, scheme="light", signed_in=True, rf=None, now=NOW, tz=None):
        c = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme, **({"timezone_id": tz} if tz else {}))
        init = ""
        if signed_in: init += "localStorage.setItem('sd_auth', 'fa9304349b9d');"
        if rf: init += "window.RF_TEST = " + rf + ";"
        if init: c.add_init_script(init)
        pg = c.new_page(); pg.errors = []; pg.set_default_timeout(12000)
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
        if now: pg.clock.install(time=now)
        made.append(c); return pg
    mock.reset()
    yield make
    for c in made: c.close()


@pytest.fixture
def page(ctx_factory, mock):
    pg = ctx_factory(); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card"); return pg


def ctl(mock, mode="ok", delay=1.5):
    urllib.request.urlopen(urllib.request.Request(f"{mock.url}/__ctl?mode={mode}&delay={delay}", method="POST", data=b""))


def posts(mock):
    import json; return json.load(urllib.request.urlopen(mock.url + "/__posts"))["n"]
