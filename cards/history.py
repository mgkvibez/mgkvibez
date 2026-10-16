"""Snapshot archive — the profile's own memory of what it was.

Drift and 30-day movement need a reading of the past that the GitHub API
cannot give: it serves levels (how much now), never history (how it
changed). So every live render appends one line to history.jsonl, the
workflow commits it back, and the next render reads it. Until the file is
old enough to answer, the cards that need it simply say less — no
invented numbers.

One line per run, trimmed to TRIM_DAYS so the file stays flat.
"""
import datetime as dt
import json
import os

from . import stats

TRIM_DAYS = 180


def _snapshot(data):
    langs = stats.lang_shares(data.get("repo_langs", {}))
    return {
        "date": data["fetched_at"][:10],
        "total": data["total"],
        "commits": data.get("collab", {}).get("commits", 0),
        "prs": data.get("collab", {}).get("prs", 0),
        "issues": data.get("collab", {}).get("issues", 0),
        "reviews": data.get("collab", {}).get("reviews", 0),
        "stars": sum(r["stars"] for r in data["repos"]),
        "followers": data.get("followers", 0),
        "langs": {name: round(share, 4) for name, _, share in langs},
    }


def record(data, path="history.jsonl"):
    """Append today's snapshot; one line per date, newest last."""
    snap = _snapshot(data)
    entries = load(path)
    entries = [e for e in entries if e["date"] != snap["date"]]
    entries.append(snap)
    save(entries, path)
    return snap


def save(entries, path="history.jsonl"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e, sort_keys=True) + "\n")


def load(path="history.jsonl"):
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def trim(entries, now=None, days=TRIM_DAYS):
    now = now or dt.date.today()
    cutoff = now - dt.timedelta(days=days)
    return [e for e in entries if dt.date.fromisoformat(e["date"]) >= cutoff]


def days_ago(entries, age, now=None):
    """The closest snapshot at least `age` days old (None if too young)."""
    now = now or dt.date.today()
    target = now - dt.timedelta(days=age)
    best = None
    for e in entries:
        d = dt.date.fromisoformat(e["date"])
        if d <= target and (best is None or d > dt.date.fromisoformat(best["date"])):
            best = e
    return best
