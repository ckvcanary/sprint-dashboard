# Dashboard checks: run these after every change, before every deploy

Run `tests/run_checks.sh all` (or `math`, `guard`, `quick`). Every check below is an automated Playwright test. If one fails, do not deploy.

## Maths checks (`math`): the numbers must add up in every situation
Independent model in `tests/test_burndown_math.py`; the page is compared with it row by row.

| Check | What it protects |
|---|---|
| Plan and logging tables match the model | Original estimate, remaining estimate, time left, verdict, logged, over estimate, expected log, missing log, leave and flag for every person, in 8 situations |
| Totals row equals the sum of the people | No row is dropped or counted twice |
| Identities | Original estimate = hours burned + remaining; logged = burned + over; used + left = capacity |
| Capacity bars and the "How this is worked out" box | Used + left = capacity; every line of the working-out is itself correct; the remaining-estimate bar is amber when it fits and red when it does not |
| Chart lines | The blue line never goes up; its end equals the team remaining estimate; the ideal pace is straight from the total down to 0; one dot only |
| Hover card numbers | Ideal pace, remaining estimate, ahead or behind and ticket counts for any day |
| Verdict wording | "Not achievable, short by X h" and "Achievable, room of X h" use the same difference as the tables |
| Overtime | A developer who logs 30 h on 18 h of work shows 12 h over, 0 h left, and does not hide anyone else's open work |
| Leave | Leave lowers capacity, expected log by now and time left only; original and remaining estimates never change |
| Expected log by now | (working hours passed) minus (leave): 24 h minus 4 h = 20 h |
| Capacity page | Leave column and capacity after leave; over or under uses the capacity after leave |
| Leave page | Capacity table and the days on leave equal the data; the Burndown page gives the same numbers |
| Scenarios | Sprint over (Completed / Not completed), sprint not started (nothing used), leave in the future |

## Guardrail checks (`guard`): layout, alignment, wording, safety
| Check | What it protects |
|---|---|
| Every (i) button | Same size (16 px), on the same line as its label, never alone on the next line, at 360, 390, 430, 768, 1024, 1280 and 1440 px |
| No sideways scroll | No page, table, chart or card scrolls sideways or runs off the screen, light and dark, phone to desktop |
| Table headers | One line, equal height, header text ends where the numbers end |
| Cards in a row | The three "what starts GitHub Actions" cards are equal size and spaced; stacked on a phone |
| Tooltips | Never cover their own button, never leave the screen; the status pop-up has two buttons (Statuses, Counted as closed) |
| Phone layout | Bottom navigation, labelled cards instead of tables, chart sized to the screen, 44 px touch targets, tap a day for its summary |
| Wording | Epics, user stories, sub-tasks (four kinds); no Task, Bug or New Feature in these texts; no paragraphs in (i) texts |
| Refresh card | One 75 s countdown, then "Finishing up", never a second count; words from the approved list only |
| Relay | A cron-job.org call within 30 minutes of 10:50 AM or 6:50 PM IST is a scheduled pull; a click is not |
| Refresh script | A pull started by either timer is recorded as scheduled; retries stand down once a pull worked |
| Big sprint | 300 stories and 1,800 sub-tasks still load quickly |
| Guided tour | Guide button, 14 steps that open the right pages, highlight the right part, keep the card on screen; Leave guide, Escape and Done return to the page, view and person; phone sheet with big buttons |
| Phone map | Epics / User stories choice, numbered flow (1, 1.1), laptop map unchanged |
| Tap the label | On a phone the field label (dotted underline) opens a sheet above the tab bar; no circle beside every label |
| Vulnerabilities | Hostile text from Jira, leave data and the browser store stays text; no javascript: links; no secrets in the page; relay refuses GET and foreign origins |
| Timers | Both timers at 10:50 AM and 6:50 PM IST; the relay input matches the workflow; warm-up and catch-up modes |
| Sign-in and session | Needs the team password |
