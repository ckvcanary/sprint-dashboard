"""Rebuild index.html from template.html and the files in data/.
Default: the page loads data/*.json when opened (used on GitHub Pages).
python3 scripts/build.py --embed   also writes artifact.html with the data inside (works offline)."""
import json, pathlib, sys
r = pathlib.Path(__file__).resolve().parent.parent
t = (r / "template.html").read_text()
HEAD = '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<style>body{margin:0}</style>\n'
(r / "index.html").write_text(HEAD + t)
if "--embed" in sys.argv:
    d = {k: (r / f"data/{k}.json").read_text() for k in ("map", "burndown", "meta", "runs")}
    (r / "artifact.html").write_text(t.replace("/*DATA*/{sprints:[],epics:[],stories:[],desc:{}}", d["map"], 1).replace("/*BD*/{}", d["burndown"], 1).replace("/*META*/null", d["meta"], 1).replace("/*RUNS*/[]", d["runs"], 1))
print("built")
