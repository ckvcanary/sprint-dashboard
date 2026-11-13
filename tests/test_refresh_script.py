"""The data pull script, tested without Jira: which tickets count as closed, and how the timetable retries behave"""
import datetime as dt, importlib.util, json, pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("refresh", ROOT / "scripts" / "refresh.py"); R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


def issue(kind, status, subtask=False, history=None, **extra):
    f = {"issuetype": {"name": kind, "subtask": subtask}, "status": {"name": status}, "updated": "2026-11-13T10:00:00.000+0530", "statuscategorychangedate": "2026-11-13T10:00:00.000+0530"}
    f.update(extra); return {"fields": f, "changelog": {"histories": history or []}}


TASK_TYPES = [("Sub-task", True), ("Story sub-task", True), ("Bug sub-task", True), ("New Feature sub-task", True), ("Task", False), ("Bug", False), ("New Feature", False)]


@pytest.mark.parametrize("kind,sub", TASK_TYPES)
def test_every_task_type_closes_on_the_eight_task_statuses(kind, sub):
    for st in ("Technical Review", "Done", "Fixed", "In Documentation", "Deployed to UAT", "Deployed to Prod", "Invalid", "Deferred"): assert R.finished(issue(kind, st, sub)), (kind, st)
    for st in ("Backlog", "In Progress", "In Testing", "Code_Review", "Research", "On-Hold", "Spec_Completed", "Accepted by Developer", "Ready for Development", "New", "Triaged", "Reopened", "Verified", "ACTIVE"): assert not R.finished(issue(kind, st, sub)), (kind, st)


def test_user_stories_close_only_when_deployed():
    for st in ("Deployed to UAT", "Deployed to Prod"): assert R.finished(issue("Story", st))
    for st in ("Technical Review", "Done", "Fixed", "In Documentation", "In Testing", "Backlog"): assert not R.finished(issue("Story", st)), st


def test_epics_close_only_in_done_because_their_workflow_has_no_deployed_status():
    assert R.finished(issue("Epic", "Done"))
    for st in ("Backlog", "In Progress", "In Testing", "In Documentation"): assert not R.finished(issue("Epic", st)), st


def moves(*pairs):   # (when, to_status)
    return [{"created": w, "items": [{"field": "status", "toString": s}]} for w, s in pairs]


def test_closed_date_is_when_the_ticket_entered_its_closed_state():
    h = moves(("2026-11-10T09:00:00.000+0530", "In Progress"), ("2026-11-12T16:00:00.000+0530", "Technical Review"), ("2026-11-13T11:00:00.000+0530", "Deployed to UAT"))
    assert R.done_date(issue("Story sub-task", "Deployed to UAT", True, h)) == "2026-11-12", "first day of the closed streak, not the last move"


def test_a_ticket_that_was_reopened_uses_the_new_closing_date():
    h = moves(("2026-11-10T10:00:00.000+0530", "Done"), ("2026-11-11T10:00:00.000+0530", "In Progress"), ("2026-11-13T10:30:00.000+0530", "Fixed"))
    assert R.done_date(issue("Bug sub-task", "Fixed", True, h)) == "2026-11-13"


def test_open_tickets_have_no_closed_date_and_late_night_uses_india_time():
    assert R.done_date(issue("Story sub-task", "In Progress", True)) is None
    h = moves(("2026-11-12T20:30:00.000+0000", "Done"))      # 02:00 IST on 13 Nov
    assert R.done_date(issue("Sub-task", "Done", True, h)) == "2026-11-13"


def test_a_story_in_technical_review_is_not_closed_even_though_a_task_would_be():
    assert R.done_date(issue("Story", "Technical Review")) is None and R.done_date(issue("Task", "Technical Review")) is not None


# ---------- the timetable retries
def write_runs(tmp_path, monkeypatch, runs):
    (tmp_path / "runs.json").write_text(json.dumps(runs)); monkeypatch.setattr(R, "DATA", tmp_path)


def at(h, m=0): return dt.datetime(2026, 11, 13, h, m, tzinfo=dt.timezone.utc)


def test_a_retry_stands_down_when_the_slot_already_has_a_scheduled_pull(tmp_path, monkeypatch):
    write_runs(tmp_path, monkeypatch, [{"at": "2026-11-13T05:16:00Z", "trigger": "schedule", "ok": True}])
    assert R.scheduled_pull_done_recently(now=at(5, 46)) and R.scheduled_pull_done_recently(now=at(6, 16))


def test_a_retry_runs_when_the_first_attempt_never_happened_or_failed(tmp_path, monkeypatch):
    write_runs(tmp_path, monkeypatch, []); assert not R.scheduled_pull_done_recently(now=at(5, 46))
    write_runs(tmp_path, monkeypatch, [{"at": "2026-11-13T05:16:00Z", "trigger": "schedule", "ok": False}]); assert not R.scheduled_pull_done_recently(now=at(5, 46))


def test_manual_refreshes_never_stand_a_scheduled_slot_down(tmp_path, monkeypatch):
    write_runs(tmp_path, monkeypatch, [{"at": "2026-11-13T05:20:00Z", "trigger": "manual", "ok": True}]); assert not R.scheduled_pull_done_recently(now=at(5, 46))


def test_the_evening_slot_is_not_blocked_by_the_morning_pull(tmp_path, monkeypatch):
    write_runs(tmp_path, monkeypatch, [{"at": "2026-11-13T05:16:00Z", "trigger": "schedule", "ok": True}]); assert not R.scheduled_pull_done_recently(now=at(13, 16))
