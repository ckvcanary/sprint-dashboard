# Vercel dashboard changes, 19 Nov 2026 (local only, branch vercel-fixes, cut from origin/main a3350ff)

## Findings
1. **Thursday log missing (root cause).** Jira returns each worklog `started` in the API user's time zone (US Eastern, -0500). refresh.py took `started[:10]`. Sumit's 8 h log started 18 Nov 23:45 -0500 = 19 Nov 10:15 IST, so it landed on Wednesday. Fix: convert `started` to IST before taking the date (in-window days, "before sprint" hours, after-window hours).
2. **Stale data after Nikita's log.** Her logs were created 13:36 to 13:37 UTC. Pulls ran at 13:34 (before), 13:39 (has her 7.5 h, on GitHub at 13:39:39) and 13:43. So the pipeline took about 3 minutes here; 15 to 20 minutes is not visible in the records. Real gaps found: (a) the relay joins a pull that is already running, which read Jira before the log; (b) the relay and page skip a click within 2 minutes of the last pull; (c) the page reports "Data refreshed" for any newer stamp, even if that pull started before the click. Fix: a click is only satisfied by a pull that STARTED after the click (relay returns server time; a running pull older than 20 s gets one follow-up run queued; skip window 2 min to 30 s). Safety net: after each pull, ask Jira's worklog-updated feed for logs of the last 15 minutes and re-read any issue whose log is missing; record `latestLogAt` and pull duration in meta.json.

## Changes
- Closed rule: a sub-task in Technical Review counts as closed only with the label `documentation-task` (Jira labels cannot hold spaces). Without it Technical Review is a step, not closed. In Documentation is never closed. Removed the name and assignee guess (Jira, demo, Chetan).
- Burndown per person, remaining-work chart: Full screen button, Esc to leave. Detail panel sits directly under the chart (no gap), header is sticky, the Close button is solid blue with an X.
- Day detail: the three tabs become a Filter button with checkboxes (Closed on this day, Closed up to this day, Still open). The list shows the union.
- Chart bands: "Sprint Planning" and "Sprint Retrospective" use the same font size and weight, both on two lines.
- Toasts: compact (smaller padding, one-line text where possible), auto-dismiss after 3.5 s with a thin timer bar, pause while hovered.
- Removed the Stakeholders (Roles) page from the left panel, the phone bar, the guide text, and the tests.

## Tests
Math (IST date model, label rule), Playwright (fullscreen, filter, close button, toast timing, tabs list), overflow and overlap at 1440, 1024, 390 px, colour and dark mode, relay tests (follow-up queue, 30 s skip), full `tests/run_checks.sh all`. Then localhost preview with real Jira data. No push until you approve.
