"""The README table view — the same numbers as the cards, readable raw.

The block is regenerated between the cards:table markers on every live
render, so the README is a file with two writers (the generator and a
human edit) that never collide: humans own everything outside the
markers, the generator owns everything inside. First run on a README
without markers adds them additively.
"""
import datetime as dt

from . import history, stats

START = "<!-- cards:table:start -->"
END = "<!-- cards:table:end -->"


def _fmt_share(share):
    return f"{share * 100:.1f}%"


def _delta_str(d):
    if d > 0:
        return f"▲ {d} in 30d"
    if d < 0:
        return f"▼ {-d} in 30d"
    return "flat over 30d"


def _trend(entries, key, now_value):
    ago = history.days_ago(entries, 28)
    if not ago:
        return "—"
    return _delta_str(now_value - ago.get(key, 0))


def build(data, entries=None):
    entries = entries or []
    collab = data.get("collab", {})
    stars = sum(r["stars"] for r in data["repos"])
    cur, longest = stats.streaks(data["days"])
    acts = collab.get("prs", 0) + collab.get("issues", 0) + collab.get("reviews", 0)
    share = acts / data["total"] if data["total"] else 0

    recent = sum(d["count"] for d in data["days"][-30:])
    prior = sum(d["count"] for d in data["days"][-60:-30])
    focus = _delta_str(recent - prior) if recent or prior else ""

    lines = []
    lines.append("| Right now | Reading | Move |")
    lines.append("|---|---|---|")
    lines.append(f"| Contributions (365d) | {data['total']} total | "
                 f"{focus if focus else '—'} |")
    lines.append(f"| Last 30 days | {recent} | see the activity card |")
    lines.append("")
    lines.append("| Metric | Last 365 days | Move |")
    lines.append("|---|---:|---|")
    lines.append(f"| Contributions | {data['total']} | "
                 f"{_trend(entries, 'total', data['total'])} |")
    lines.append(f"| Commits | {collab.get('commits', 0)} | "
                 f"{_trend(entries, 'commits', collab.get('commits', 0))} |")
    lines.append(f"| Pull requests | {collab.get('prs', 0)} | "
                 f"{_trend(entries, 'prs', collab.get('prs', 0))} |")
    lines.append(f"| Issues | {collab.get('issues', 0)} | "
                 f"{_trend(entries, 'issues', collab.get('issues', 0))} |")
    lines.append(f"| Reviews | {collab.get('reviews', 0)} | "
                 f"{_trend(entries, 'reviews', collab.get('reviews', 0))} |")
    lines.append(f"| Current streak | {cur}d | — |")
    lines.append(f"| Longest streak | {longest}d | — |")
    lines.append(f"| Repositories | {len(data['repos'])} | — |")
    lines.append(f"| Stars earned | {stars} | "
                 f"{_trend(entries, 'stars', stars)} |")
    lines.append(f"| Followers | {data.get('followers', 0)} | "
                 f"{_trend(entries, 'followers', data.get('followers', 0))} |")
    lines.append(f"| Collaborative acts | {acts} ({_fmt_share(share)} of all) | — |")

    lines.append("")
    lines.append("| Language | Share | Tracked size |")
    lines.append("|---|---:|---:|")
    for name, size, share_ in stats.lang_shares(data.get("repo_langs", {})):
        lines.append(f"| {name} | {_fmt_share(share_)} | "
                     f"{stats.fmt_bytes(size) or '—'} |")

    grid = stats.rhythm_grid(data.get("commit_sample", []))
    sample = sum(sum(r) for r in grid)
    if sample:
        peak = max(((r, c) for r in range(7) for c in range(24)),
                   key=lambda rc: grid[rc[0]][rc[1]])
        nights = sum(grid[r][c] for r in range(7)
                     for c in list(range(0, 6)) + list(range(22, 24)))
        lines.append("")
        lines.append("| Commit rhythm | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Busiest slot | "
                     f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][peak[0]]} "
                     f"{peak[1]:02d}:00 ({grid[peak[0]][peak[1]]} commits) |")
        lines.append(f"| Sample | {sample} recent commits |")
        lines.append(f"| Nights, 22:00–06:00 | "
                     f"{nights / sample * 100:.0f}% of the sample |")
        lines.append("| Clock | UTC — every stamp came back without an offset |")

    years = sorted(data.get("years", []), key=lambda y: y["year"])
    if years:
        lines.append("")
        lines.append("| Year | Contributions |")
        lines.append("|---|---:|")
        for y in years:
            if y["total"] or (data.get("created_at") and
                              y["year"] == int(data["created_at"][:4])):
                lines.append(f"| {y['year']} | {y['total']} |")

    lines.append("")
    lines.append("| Building | Commits | Size | Stars | Last push | State | Access |")
    lines.append("|---|---:|---:|---:|---|---|---|")
    for r in sorted(data["repos"], key=lambda r: -r["commits"]):
        if r["archived"] or r["pushed_days_ago"] > 90:
            state = "dormant"
        elif r["pushed_days_ago"] > 30:
            state = "quiet"
        else:
            state = "occupied"
        name = (f"[{r['name']}](https://github.com/{data['login']}/{r['name']})"
                if not r["private"] else r["name"])
        size = (f"{r['size_kb'] / 1024:.1f} MB" if r["size_kb"] >= 1024
                else f"{r['size_kb']} kB")
        lines.append(f"| {name} | {r['commits']} | {size} | {r['stars']} "
                     f"| {r['pushed_at'][:10]} | {state} "
                     f"| {'private' if r['private'] else 'public'} |")
    lines.append("")
    lines.append(f"_Private repositories are listed for their activity only — "
                 f"they are not linked, because the link would 404 for "
                 f"everyone but me._")
    lines.append("")
    lines.append(f"_Generated by `cards/` on {dt.date.today().isoformat()}, "
                 f"from the live GitHub GraphQL API. Table maintained between "
                 f"the cards:table markers._")
    return "\n".join(lines)


def update(readme, block):
    """Insert or replace the marked section, leaving the rest untouched."""
    if START in readme and END in readme:
        before, rest = readme.split(START, 1)
        _, after = rest.split(END, 1)
        return before + START + "\n\n" + block + "\n" + END + after
    return readme.rstrip() + "\n\n<details>\n<summary>Open the table view</summary>\n\n" \
        + START + "\n\n" + block + "\n" + END + "\n\n</details>\n"
