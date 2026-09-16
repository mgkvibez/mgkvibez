"""GitHub profile data: live GraphQL fetch, or offline fixture.

Both paths return the same normalized dict:

    {
      "login": str,
      "fetched_at": str,           # ISO timestamp
      "total": int,               # contributions in the last 365 days
      "days": [{date, count}],    # one entry per calendar day
      "repos": [{
          name, language, stars, pushed_at, size_kb, archived, pushed_days_ago
      }],
    }

The fixture is a real snapshot of the live response (testdata/profile.json),
so the offline tests exercise the same data the cards ship with.
"""
import datetime as dt
import json
import os
import urllib.request

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                  orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        primaryLanguage { name }
        stargazerCount
        pushedAt
        isArchived
        diskUsage
        defaultBranchRef { target { ... on Commit { history { totalCount } } } }
      }
    }
  }
}
"""


def _normalize(raw, login):
    user = raw["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]

    now = dt.datetime.now(dt.timezone.utc)
    repos = []
    for r in user["repositories"]["nodes"]:
        pushed = dt.datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00"))
        repos.append({
            "name": r["name"],
            "language": (r.get("primaryLanguage") or {}).get("name") or "unknown",
            "stars": r["stargazerCount"],
            "pushed_at": r["pushedAt"],
            "pushed_days_ago": (now - pushed).days,
            "size_kb": r["diskUsage"],
            "commits": (((r.get("defaultBranchRef") or {}).get("target") or {})
                        .get("history", {}).get("totalCount")) or 0,
            "archived": r["isArchived"],
        })
    return {
        "login": login,
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": cal["totalContributions"],
        "days": [{"date": d["date"], "count": d["contributionCount"]} for d in days],
        "repos": repos,
    }


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "mgkvibez-cards"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.load(resp)
    if raw.get("errors") or not raw.get("data", {}).get("user"):
        raise RuntimeError(f"GraphQL failed: {raw.get('errors')}")
    return _normalize(raw, login)


def load_fixture(path):
    raw = json.load(open(path))
    days = [d for w in raw["data"]["user"]["contributionsCollection"]
            ["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    # take the snapshot date from the fixture so offline renders are stable
    now = dt.datetime(2026, 9, 16, 10, 57, tzinfo=dt.timezone.utc)
    repos = []
    for r in raw["data"]["user"]["repositories"]["nodes"]:
        pushed = dt.datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00"))
        repos.append({
            "name": r["name"],
            "language": (r.get("primaryLanguage") or {}).get("name") or "unknown",
            "stars": r["stargazerCount"],
            "pushed_at": r["pushedAt"],
            "pushed_days_ago": (now - pushed).days,
            "size_kb": r["diskUsage"],
            "commits": (((r.get("defaultBranchRef") or {}).get("target") or {})
                        .get("history", {}).get("totalCount")) or 0,
            "archived": r["isArchived"],
        })
    return {
        "login": "mgkvibez",
        "fetched_at": raw.get("fetched_at", "2026-09-16T10:57:00Z"),
        "total": raw["data"]["user"]["contributionsCollection"]
                      ["contributionCalendar"]["totalContributions"],
        "days": [{"date": d["date"], "count": d["contributionCount"]} for d in days],
        "repos": repos,
    }
