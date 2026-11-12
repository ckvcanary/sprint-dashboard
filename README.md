# Sprint Dashboard

Live page: https://ckvcanary.github.io/sprint-dashboard/

Four views: **Map** (epics, user stories, tasks, with a description drawer), **Capacity** (64 h per person), **Burndown** (per member, per sprint, with time-log flags) and **Pull log** (every Jira pull; scheduled pulls are counted per sprint, manual refreshes are listed separately).

## How the data stays fresh (no laptop needed)
- A GitHub Actions job (`.github/workflows/refresh.yml`) pulls Jira at **10:45 AM and 6:45 PM IST every day**.
- Anyone with write access can press **Refresh data** on the page, or open Actions, pick "Refresh Jira data" and click Run workflow.
- Each run rewrites `data/*.json`, records itself in `data/runs.json`, and republishes the page. The page shows when the data was last refreshed.
- Jira login lives in GitHub secrets `JIRA_BASE`, `JIRA_EMAIL`, `JIRA_TOKEN` (Settings, Secrets and variables, Actions). A bad token fails the run and leaves the data unchanged.

## Team member setup (one time)
1. Ask Chetan to add your GitHub username as a collaborator (Settings, Collaborators, Write).
2. Accept the invite.
3. Create a fine-grained token at github.com/settings/personal-access-tokens/new: repository access `ckvcanary/sprint-dashboard`, permission Actions: Read and write.
4. Open the dashboard, click **Refresh data**, paste the token once. It is stored only in your browser.

## Files
- `template.html` source page. `index.html` built page. `data/` map, burndown, meta, runs.
- `scripts/refresh.py` Jira pull (REST, standard library only). `scripts/build.py` rebuilds `index.html` (`--embed` also writes `artifact.html` with the data inside).
- Hours rule: new tickets use the original estimate; rolled-over tickets use the original estimate minus time logged before the sprint start.
