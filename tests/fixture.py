"""Deterministic test data in the same shape as data/*.json (no real Jira content).
Pull time ("as of") is Fri 13 Nov 2026, 4:34 PM IST = 11:04 UTC. Sprint 24 runs 9 Nov to 23 Nov."""
import json, pathlib

ASOF = "2026-11-13T11:04:00Z"
NOW = "2026-11-13T11:10:00Z"      # the page clock in tests


def task(k, t, a, h, s): return {"key": k, "t": t, "a": a, "h": h, "s": s}


def build(dest):
    d = pathlib.Path(dest); d.mkdir(parents=True, exist_ok=True)
    sprints = [{"id": f"S{n}", "name": f"Sprint {n}", "r": ""} for n in range(20, 25)] + [{"id": "NEXT", "name": "Sprint 25 and backlog", "r": ""}]
    epics = [{"key": "PROD-9001", "title": "Zippy ATS Registration", "a": "Nikita", "s": "In Progress"}, {"key": "PROD-9002", "title": "Shared Microservices", "a": "Sumit", "s": "Done"}]
    stories = [
        {"key": "PROD-9101", "title": "Free Plan, Usage Limits and Upgrade Flow", "epic": "PROD-9001", "sprint": "S24", "a": "Nikita", "sp": 8, "own": 0, "s": "In Progress",
         "tasks": [task("PROD-9111", "Free plan limits and upgrade popup", "Nikita", 8, "In Progress"), task("PROD-9112", "Login page revamp", "Nikita", 4, "Deployed to UAT"), task("PROD-9113", "Downgrade to Free", "Nikita", 6, "Backlog")]},
        {"key": "PROD-9102", "title": "Login Microservice, Build and Deliver", "epic": "PROD-9002", "sprint": "S24", "a": "Sumit", "sp": 1, "own": 0, "s": "In Testing",
         "tasks": [task("PROD-9121", "Token service", "Sumit", 16, "In Testing"), task("PROD-9122", "Session tests", "Aditi", 12, "Done")]},
        {"key": "PROD-9103", "title": "Tracker story without points", "epic": None, "sprint": "S24", "a": "Aditi", "sp": None, "own": 4, "s": "Deployed to UAT", "tasks": []},
        {"key": "PROD-9091", "title": "Earlier registration story", "epic": "PROD-9001", "sprint": "S23", "a": "Nikita", "sp": 3, "own": 0, "tasks": [task("PROD-9131", "Spec review", "Nikita", 4, "Done")]},
    ]
    desc = {"PROD-9101": "Users on the free plan see usage limits.\n\n- Limits per plan\n- Upgrade popup", "PROD-9111": "Show the popup when a limit is reached."}
    extra = {"PROD-9101": {"att": ["Technical approach.pdf", "Screenshot 2026-11-12.png"],
                           "cm": [{"a": "Chetan Kumar Verma", "at": "2026-11-10T09:00:00.000+0530", "t": "First comment on the story."}, {"a": "Nikita", "at": "2026-11-12T16:30:00.000+0530", "t": "Latest comment with a [link](https://example.com)."}]},
             "PROD-9111": {"att": [], "cm": [{"a": "Nikita", "at": "2026-11-12T11:00:00.000+0530", "t": "Started the work."}]}}
    CK = "Chetan Kumar Verma"
    def inf(rp, lb, du, oe, lg, lk=None): return {"rp": rp, "lb": lb, "du": du, "oe": oe, "lg": lg, "lk": lk or []}
    info = {"PROD-9001": inf(CK, [], None, 0, 0), "PROD-9002": inf(CK, ["shared"], "2026-11-23", 0, 0),
            "PROD-9101": inf(CK, ["zippy", "documentation-task"], "2026-11-23", 0, 0, [{"t": "blocks", "k": "PROD-9102", "s": "Login Microservice, Build and Deliver", "st": "In Testing"}]),
            "PROD-9102": inf(CK, [], "2026-11-23", 0, 0), "PROD-9103": inf("Nikita", [], None, 4, 2), "PROD-9091": inf(CK, [], "2026-11-06", 0, 0),
            "PROD-9111": inf(CK, ["frontend"], "2026-11-20", 8, 7, [{"t": "is blocked by", "k": "PROD-9113", "s": "Downgrade to Free", "st": "In Progress"}]),
            "PROD-9112": inf("Nikita", [], "2026-11-12", 4, 4.5), "PROD-9113": inf(CK, [], None, 6, 0),
            "PROD-9121": inf(CK, ["documentation-task"], "2026-11-20", 16, 16), "PROD-9122": inf("Aditi", [], "2026-11-13", 12, 3), "PROD-9131": inf(CK, [], "2026-11-06", 4, 4)}
    scope = {"space": "Product Development", "spaceKey": "PROD", "board": "PROD board", "boardId": 243}
    m = {"sprints": sprints, "epics": epics, "stories": stories, "desc": desc, "extra": extra, "info": info, "scope": scope, "asOf": ASOF}
    people = {"Nikita": {"E": 18.0, "logs": {"2026-11-11": 4.0, "2026-11-12": 6.0}}, "Sumit": {"E": 16.0, "logs": {"2026-11-11": 8.0, "2026-11-12": 8.0}}, "Aditi": {"E": 16.0, "logs": {"2026-11-11": 5.0}}}
    tasks24 = [{"k": "PROD-9111", "a": "Nikita", "e": 8, "d": None, "s": "Free plan limits and upgrade popup", "st": "In Progress", "sd": "2026-11-11", "lg": 6, "ll": "2026-11-12"},
               {"k": "PROD-9112", "a": "Nikita", "e": 4, "d": "2026-11-12", "s": "Login page revamp", "st": "Deployed to UAT", "sd": "2026-11-12", "lg": 4, "ll": "2026-11-12"},
               {"k": "PROD-9113", "a": "Nikita", "e": 6, "d": None, "s": "Downgrade to Free", "st": "In Progress", "sd": "2026-11-10", "lg": 0, "ll": None},
               {"k": "PROD-9121", "a": "Sumit", "e": 16, "d": None, "s": "Token service", "st": "In Testing", "sd": "2026-11-09", "lg": 16, "ll": "2026-11-12"},
               {"k": "PROD-9122", "a": "Aditi", "e": 12, "d": "2026-11-13", "s": "Session tests", "st": "Done", "sd": "2026-11-13", "lg": 0, "ll": None},
               {"k": "PROD-9103", "a": "Aditi", "e": 4, "d": "2026-11-12", "y": 1, "s": "Tracker story without points", "st": "Deployed to UAT", "sd": "2026-11-12", "lg": 0, "ll": None}]
    bd = {"S20": {"name": "Sprint 20", "win": None, "people": {}}, "S21": {"name": "Sprint 21", "win": None, "people": {}},
          "S22": {"name": "Sprint 22", "win": ["2026-10-12", "2026-10-23"], "start": "2026-10-12", "end": "2026-10-23", "tasks": [], "people": {"Nikita": {"E": 40.0, "logs": {"2026-10-13": 8.0}}}},
          "S23": {"name": "Sprint 23", "win": ["2026-10-26", "2026-11-06"], "start": "2026-10-26", "end": "2026-11-06", "tasks": [{"k": "PROD-9131", "a": "Nikita", "e": 4, "d": "2026-10-30"}], "people": {"Nikita": {"E": 4.0, "logs": {"2026-10-27": 4.0}}}},
          "S24": {"name": "Sprint 24", "win": ["2026-11-11", "2026-11-20"], "start": "2026-11-09", "end": "2026-11-23", "tasks": tasks24, "stories": [{"k": "PROD-9101", "a": "Nikita", "d": None}, {"k": "PROD-9102", "a": "Sumit", "d": None}, {"k": "PROD-9103", "a": "Aditi", "d": "2026-11-12"}], "epics": [{"k": "PROD-9001", "a": "Nikita", "d": None}, {"k": "PROD-9002", "a": "Sumit", "d": "2026-11-13"}], "people": people}}
    for v in bd.values(): v["asOf"] = ASOF
    meta = {"refreshedAt": ASOF, "trigger": "manual", "issues": 1066, "sprint": "Sprint 24", "sprintIssues": 12, "by": "tester"}
    runs = [{"at": "2026-11-12T14:10:01Z", "trigger": "manual", "ok": True, "issues": 1064, "sprint": "Sprint 24", "by": "tester"},
            {"at": "2026-11-13T05:16:10Z", "trigger": "schedule", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": "Scheduler"},
            {"at": ASOF, "trigger": "manual", "ok": True, "issues": 1066, "sprint": "Sprint 24", "by": "tester"}]
    for n, o in (("map", m), ("burndown", bd), ("meta", meta), ("runs", runs), ("leave", {})):
        (d / f"{n}.json").write_text(json.dumps(o))
    return d
