"""19 Nov 2026 data fixes: worklog dates in IST, the documentation-task label rule, the worklog safety net"""
import importlib.util, pathlib, pytest
pytestmark = [pytest.mark.guard, pytest.mark.math]
ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("refresh", ROOT / "scripts" / "refresh.py"); R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


def wl(started): return {"started": started, "timeSpentSeconds": 3600}


def test_sumits_log_lands_on_thursday():      # the real record: started 18 Nov 23:45 -0500 = 19 Nov 10:15 IST
    assert R.log_date(wl("2026-11-18T23:45:14.715-0500")) == "2026-11-19"


@pytest.mark.parametrize("started,day", [
    ("2026-11-18T02:26:59.968-0500", "2026-11-18"),   # 12:56 IST same day
    ("2026-11-17T03:50:34.633-0500", "2026-11-17"),   # 14:20 IST
    ("2026-11-18T13:29:59.000-0500", "2026-11-18"),   # 23:59 IST, still the same day
    ("2026-11-18T13:30:00.000-0500", "2026-11-19"),   # 00:00 IST, next day
    ("2026-11-19T10:00:00.000+0530", "2026-11-19"),   # already IST
    ("2026-11-19T04:30:00.000+0000", "2026-11-19"),   # UTC
    ("2026-11-19T22:00:00.000-0800", "2026-11-20"),   # Pacific
])
def test_log_date_is_the_ist_date(started, day): assert R.log_date(wl(started)) == day


def issue(status, labels=None, kind="Sub-task", sub=True):
    return {"fields": {"issuetype": {"name": kind, "subtask": sub}, "status": {"name": status}, "labels": labels or [], "summary": "Update the documentation for the demo", "assignee": {"displayName": "Chetan Kumar Verma"}, "updated": "2026-11-13T10:00:00.000+0530"}}


@pytest.mark.parametrize("label", ["documentation-task", "documentation_task", "DocumentationTask", "Documentation-Task", "documentationtask"])
def test_label_makes_technical_review_closed(label): assert R.finished(issue("Technical Review", [label]))


@pytest.mark.parametrize("labels", [[], ["documentation"], ["task"], ["documentation", "task"], ["docs"], ["demo"]])
def test_without_the_label_technical_review_is_open(labels): assert not R.finished(issue("Technical Review", labels))     # even for Chetan, even with 'documentation' in the title


@pytest.mark.parametrize("labels", [[], ["documentation-task"]])
def test_in_documentation_is_never_closed(labels): assert not R.finished(issue("In Documentation", labels))


@pytest.mark.parametrize("st", ["Done", "Fixed", "Deployed to UAT", "Deployed to Prod", "Invalid", "Deferred"])
def test_other_closing_statuses_unchanged(st): assert R.finished(issue(st))


def test_label_does_not_close_a_story_in_technical_review(): assert not R.finished(issue("Technical Review", ["documentation-task"], "Story", False))


def test_worklog_safety_net_finds_the_missed_log(monkeypatch):
    R.SEEN_LOGS.clear(); R.SCANNED.clear(); R.SCANNED.add("10"); R.SEEN_LOGS.update({"1", "2"})
    def fake(path, body=None, method=None):
        if "worklog/updated" in path: return {"values": [{"worklogId": 2}, {"worklogId": 3}, {"worklogId": 4}]}
        return [{"id": "2", "issueId": "10", "updated": "2026-11-19T08:36:00.000-0500"}, {"id": "3", "issueId": "10", "updated": "2026-11-19T08:37:29.000-0500"}, {"id": "4", "issueId": "99", "updated": "2026-11-19T08:38:00.000-0500"}]
    monkeypatch.setattr(R, "api", fake)
    miss, newest = R.missing_logs()
    assert miss == ["3"]                      # log 4 is on an issue this pull did not read, so it is not counted
    assert newest == "2026-11-19T08:37:29.000-0500"


def test_worklog_safety_net_quiet_when_all_seen(monkeypatch):
    R.SEEN_LOGS.clear(); R.SCANNED.clear(); R.SCANNED.add("10"); R.SEEN_LOGS.add("2")
    monkeypatch.setattr(R, "api", lambda p, b=None, method=None: {"values": [{"worklogId": 2}]} if "updated" in p else [{"id": "2", "issueId": "10", "updated": "x"}])
    assert R.missing_logs()[0] == []
