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
      # extended fields (2026-10-16) — additive, cards built before them
      # still work; every extended key is optional to the reader:
      "name": str,                     # display name
      "created_at": str,               # account creation ISO date
      "followers": int,
      "collab": {commits, prs, issues, reviews, restricted},
      "years": [{year, total, days}],  # per-calendar-year contribution days
      "commit_sample": [{date, repo}], # recent default-branch commit stamps
      "repo_langs": {repo: {lang: bytes}},
    }

The fixture is a real snapshot of the live response (testdata/profile.json),
so the offline tests exercise the same data the cards ship with.

The year span reaches back six calendar years, aliased y0..y5, because the
API caps a single contributionsCollection at one year. Years before the
account existed come back empty and are simply absent from the list.
"""
import datetime as dt
import json
import os
import urllib.request

API = "https://api.github.com/graphql"

YEAR_SPAN = 6

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    createdAt
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
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
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
        stargazerCount
        pushedAt
        isArchived
        isPrivate
        diskUsage
        defaultBranchRef { target { ... on Commit {
          history { totalCount }
          recent: history(first: 50) { nodes { committedDate } }
        } } }
      }
    }
    %s
  }
}
"""


def _year_aliases(now):
    """One aliased contributionsCollection per calendar year, current first.

    The API rejects future ranges outright, so the current year's window is
    clamped to now.
    """
    parts = []
    for i in range(YEAR_SPAN):
        year = now.year - i
        to = dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc)
        if to > now:
            to = now
        parts.append(
            "y%d: contributionsCollection(from: \"%04d-01-01T00:00:00Z\", "
            "to: \"%s\") { contributionCalendar { totalContributions "
            "weeks { contributionDays { date contributionCount } } } }"
            % (i, year, to.strftime("%Y-%m-%dT%H:%M:%SZ")))
    return "\n  ".join(parts)


def _year_list(raw_user, login, now):
    years = []
    for i in range(YEAR_SPAN):
        alias = raw_user.get("y%d" % i)
        if not alias:
            continue
        cal = alias.get("contributionCalendar", {})
        days = [d for w in cal.get("weeks", []) for d in w["contributionDays"]]
        if not days:
            continue
        years.append({
            "year": now.year - i,
            "total": cal.get("totalContributions", 0),
            "days": [{"date": d["date"], "count": d["contributionCount"]}
                     for d in days],
        })
    return years


def _repo_langs(node):
    """{language: tracked bytes} for one repo, from its languages edges."""
    out = {}
    for edge in ((node.get("languages") or {}).get("edges") or []):
        name = (edge.get("node") or {}).get("name")
        if name:
            out[name] = out.get(name, 0) + (edge.get("size") or 0)
    return out


def _commit_sample(raw_user, limit_per_repo=50):
    """Recent default-branch commit stamps, repo-labelled, oldest-first."""
    stamps = []
    for r in raw_user.get("repositories", {}).get("nodes", []):
        target = ((r.get("defaultBranchRef") or {}).get("target") or {})
        # "recent" aliases the CommitHistoryConnection itself, so its
        # nodes hang directly off it.
        nodes = (target.get("recent") or {}).get("nodes") or []
        for n in nodes[:limit_per_repo]:
            stamps.append({"date": n["committedDate"], "repo": r["name"]})
    stamps.sort(key=lambda s: s["date"])
    return stamps


def _normalize(raw, login, now=None):
    user = raw["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    now = now or dt.datetime.now(dt.timezone.utc)

    repos = []
    repo_langs = {}
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
            "private": r["isPrivate"],
        })
        repo_langs[r["name"]] = _repo_langs(r)

    cc = user.get("contributionsCollection", {})
    return {
        "login": login,
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": cal["totalContributions"],
        "days": [{"date": d["date"], "count": d["contributionCount"]} for d in days],
        "repos": repos,
        "name": user.get("name") or login,
        "created_at": user.get("createdAt") or "",
        "followers": ((user.get("followers") or {}).get("totalCount") or 0),
        "collab": {
            "commits": cc.get("totalCommitContributions") or 0,
            "prs": cc.get("totalPullRequestContributions") or 0,
            "issues": cc.get("totalIssueContributions") or 0,
            "reviews": cc.get("totalPullRequestReviewContributions") or 0,
            "restricted": cc.get("restrictedContributionsCount") or 0,
        },
        "years": _year_list(user, login, now),
        "commit_sample": _commit_sample(user),
        "repo_langs": repo_langs,
    }


def fetch_raw(login, token, now=None):
    """Live GraphQL response, unnormalized — the fixture is saved from this."""
    now = now or dt.datetime.now(dt.timezone.utc)
    query = QUERY % _year_aliases(now)
    body = json.dumps({"query": query, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "mgkvibez-cards"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.load(resp)
    if raw.get("errors") or not raw.get("data", {}).get("user"):
        raise RuntimeError(f"GraphQL failed: {raw.get('errors')}")
    raw["login"] = login
    raw["fetched_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return raw


def fetch(login, token, now=None):
    raw = fetch_raw(login, token, now)
    return _normalize(raw, login, now)


# The fixture is stored as the raw GraphQL response so the offline path
# exercises the same normalizer as the live path. Older fixtures (pre
# 2026-10-16) lack the extended fields; the loader tolerates them so
# historical snapshots still render.
def load_fixture(path, now=None):
    raw = json.load(open(path))
    user = raw["data"]["user"]
    if "fetched_at" in raw and raw["fetched_at"].endswith("Z"):
        try:
            now = dt.datetime.strptime(raw["fetched_at"],
                                        "%Y-%m-%dT%H:%M:%SZ")
            now = now.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    else:
        now = dt.datetime(2026, 9, 16, 9, 38, tzinfo=dt.timezone.utc)
    # Older fixtures have no y0..y5 aliases; _normalize tolerates that.
    return _normalize(raw, raw.get("login", "mgkvibez"), now)


def save_fixture(path, data, raw=None):
    """Persist a fresh snapshot for offline tests (raw response preferred)."""
    with open(path, "w") as f:
        json.dump(raw, f, indent=1)
    print(f"saved fixture {path}")
