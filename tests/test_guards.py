"""Deployment guardrails: things that would break the live site or leak a secret"""
import pytest

pytestmark = pytest.mark.guard
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "tests" not in p.parts and p.suffix in {".html", ".js", ".py", ".yml", ".md", ".json", ".txt", ""} and p.name != ".env"]


def test_no_secrets_anywhere_in_the_repository():
    bad = re.compile(r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|ATATT[A-Za-z0-9_\-=]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY")
    hits = [str(p.relative_to(ROOT)) for p in FILES if bad.search(p.read_text(errors="ignore"))]
    assert not hits, hits


def test_page_calls_the_vercel_relay_and_loads_data_by_relative_path():
    h = (ROOT / "index.html").read_text()
    assert "const REFRESH_URL = 'https://sprint-dashboard-umber.vercel.app/api/refresh'" in h
    assert "fetch('data/'" in h and "localhost" not in h and "127.0.0.1" not in h


def test_vercel_serves_the_page_the_data_and_the_relay_from_the_repo_root():
    assert (ROOT / "index.html").exists() and (ROOT / "api" / "refresh.js").exists()
    for n in ("map", "burndown", "meta", "runs"): json.loads((ROOT / "data" / f"{n}.json").read_text())


def test_relay_allows_the_vercel_and_github_pages_origins():
    s = (ROOT / "api" / "refresh.js").read_text()
    assert "https://sprint-dashboard-umber.vercel.app" in s and "https://ckvcanary.github.io" in s and "process.env.GH_TOKEN" in s


def test_workflow_runs_every_day_retries_each_slot_and_is_serialised():
    y = (ROOT / ".github" / "workflows" / "refresh.yml").read_text(); crons = re.findall(r'- cron: "([^"]+)"', y)
    assert crons == ["20 5 * * *", "50 5 * * *", "20 6 * * *", "20 13 * * *", "50 13 * * *", "20 14 * * *"], crons    # 10:50 AM and 6:50 PM IST (the same time as cron-job.org) plus two retries each, Monday to Friday
    assert "group: refresh" in y and "cancel-in-progress: false" in y and "timeout-minutes" in y and "workflow_dispatch" in y


def test_saving_the_data_retries_and_fails_loudly_instead_of_hiding_a_failed_push():
    y = (ROOT / ".github" / "workflows" / "refresh.yml").read_text()
    assert "git push" in y and "|| true" not in y and "for i in 1 2 3" in y and "exit 1" in y


def test_scheduled_runs_are_labelled_and_secrets_come_from_github_secrets():
    y = (ROOT / ".github" / "workflows" / "refresh.yml").read_text()
    for k in ("JIRA_BASE", "JIRA_EMAIL", "JIRA_TOKEN"): assert "${{ secrets.%s }}" % k in y
    assert "GITHUB_EVENT_NAME: ${{ github.event_name }}" in y and "permissions:" in y and "contents: write" in y


def test_refresh_script_has_no_cooldown_and_writes_the_stamp():
    s = (ROOT / "scripts" / "refresh.py").read_text()
    assert "cooldown" not in s.lower() and "less than 30 seconds" not in s      # every manual click is a real pull
    assert "scheduled_pull_done_recently" in s and 'out["asOf"] = STAMP' in s and '"sprintIssues"' in s and "TASK_DONE" in s and "STORY_DONE" in s


def statuses(name):
    s = (ROOT / "scripts" / "refresh.py").read_text(); return set(re.findall(r'"([^"]+)"', re.search(name + r" = \{([^}]*)\}", s).group(1)))


def test_closed_statuses_follow_the_agreed_lists():
    assert statuses("TASK_DONE") == {"Technical Review", "Deployed to UAT", "Deployed to Prod", "Fixed", "Done", "Invalid", "Deferred"}
    assert statuses("EPIC_DONE") == {"Done"}, "the Epic workflow has no Deployed status"
    assert statuses("STORY_DONE") == {"Deployed to UAT", "Deployed to Prod"}, "user stories close only when deployed"


def test_page_size_is_reasonable():
    assert (ROOT / "index.html").stat().st_size < 400_000


def test_the_relay_runs_on_vercel_with_nothing_to_install():
    js = (ROOT / "api" / "refresh.js").read_text()
    assert "module.exports" in js and not re.search(r"\brequire\(|^\s*import\s", js, re.M), "plain Node, no packages"
    pj = ROOT / "package.json"
    if pj.exists(): assert json.loads(pj.read_text()).get("type") != "module", "the relay uses module.exports"
    vj = ROOT / "vercel.json"
    if vj.exists(): json.loads(vj.read_text())
    assert len(js) < 10_000


def test_the_page_loads_nothing_over_plain_http_and_has_no_stray_references():
    h = (ROOT / "index.html").read_text()
    assert "http://" not in h.replace("http://www.w3.org/2000/svg", ""), "everything must load over https (the SVG namespace name is not a download)"
    refs = re.findall(r"""(?:src|href)=["'](?!https?:|#|data:|mailto:|javascript:|\$|\{)([^"'$]+)["']""", h)    # code that builds links ($2, ${...}) is not a file reference
    for r in refs: assert (ROOT / r.split("?")[0]).exists(), f"missing file {r}"


def test_the_refresh_script_refuses_to_overwrite_good_data_with_too_little():
    s = (ROOT / "scripts" / "refresh.py").read_text()
    assert "Jira returned too little data" in s and "total < 200" in s and "raise" in s


def test_the_two_timers_agree_with_each_other_and_with_the_workflow():
    """the relay sends the input the workflow declares, both timers run at 10:50 AM and 6:50 PM IST, and the page shows the same slots"""
    y = (ROOT / ".github" / "workflows" / "refresh.yml").read_text(); j = (ROOT / "api" / "refresh.js").read_text(); h = (ROOT / "template.html").read_text(); r = (ROOT / "scripts" / "refresh.py").read_text()
    assert re.search(r"inputs:\s*\n\s+source:", y) and "PULL_SOURCE: ${{ inputs.source }}" in y and 'inputs: { source: "cron-job.org" }' in j and 'PULL_SOURCE") == "cron-job.org"' in r
    assert "SLOTS = [[10, 50], [18, 50]]" in j and "SLOTS = [[10, 50], [18, 50]]" in h and "10:45" not in h and "6:45 PM" not in h
    assert '- cron: "20 5 * * *"' in y and '- cron: "20 13 * * *"' in y        # 05:20 and 13:20 UTC are 10:50 AM and 6:50 PM IST
    assert "scheduled_pull_done_recently" in r and "is_scheduled() and scheduled_pull_done_recently()" in r
