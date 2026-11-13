# Dashboard tests

Playwright tests for the sprint dashboard. They run in Chrome against a local copy of the page with made-up data and a fake refresh service, so they never touch Jira, GitHub or Vercel.

```
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements.txt
DASH_PASSWORD='<the team password>' .venv/bin/python -m pytest tests
```

The team password is not stored in the repository, so the tests read it from `DASH_PASSWORD`.

| File | What it protects |
|---|---|
| test_gate.py | Sign-in page, wrong-password toast, Show/Hide, session expiry |
| test_map.py | Cards show points only, drawer facts, attachment names, comments, legend gap |
| test_capacity.py | Capacity labels, equal panel heights, totals |
| test_burndown.py | Read-only As of, day x of 10, capacity left, axes, hover counts, grouped chart |
| test_pulllog.py | Weekday schedule by sprint, counts, plain wording |
| test_how.py | Flow charts, cron and account explanation, links, no secrets shown |
| test_refresh.py | Progress card, verified "Data refreshed", failure, timeout, stale files, double click |
| test_relay.py | The Vercel relay: joins a running refresh, skips fresh data, refuses other origins |
| test_guards.py | No secrets in the repo, Vercel layout, weekday cron, cooldown, finished-status list |
| test_responsive.py | No sideways scroll, dark mode, no console errors |

## Live checks that touch Jira (not in the normal run)

`tests/live_roundtrip.py` changes an epic's assignee, a story's points and a task's estimate in Jira, clicks Refresh on the preview, checks the dashboard shows the change, restores Jira exactly, refreshes again and checks the original values are back. Start the preview first: `python3 tests/serve_demo.py 8767` (its Refresh runs the real Jira pull).
