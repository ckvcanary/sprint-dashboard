# Sprint Dashboard

One page with three views: Map (epics, user stories, tasks, with a description drawer), Capacity (64 h per person) and Burndown (per member, per sprint, with time-log flags).

- `index.html` is the built page, open it in a browser. It is also published as a Claude Artifact.
- `template.html` is the source. Data placeholders: `/*DATA*/` and `/*BD*/`.
- `data/map.json` holds sprints, epics, stories, tasks and descriptions. `data/burndown.json` holds original estimate and dated worklogs per member per sprint.
- `python3 scripts/build.py` rebuilds `index.html` from the template and data.
- `scripts/build_burndown.py` is the burndown data builder. It reads saved Jira search results; moving it to the Jira REST API is the next step, so the scheduled sync can refresh the data.

Data is a snapshot from 12 Nov 2026. Hours rule: new tickets use the original estimate; rolled-over tickets use the original estimate minus time logged before the sprint start.
