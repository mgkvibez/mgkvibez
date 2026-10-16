"""Derived stats shared by the newer cards (added 2026-10-16).

Everything here is a pure function over the normalized profile dict, so
the offline tests exercise the same math the live cards ship with.
"""
import datetime as dt


# --- streaks -----------------------------------------------------------

def streaks(days):
    """(current, longest) contribution-day streaks from the calendar.

    A streak counts days with at least one contribution; the calendar is
    the source of truth, not the commit sample.
    """
    active = [bool(d["count"]) for d in days]
    longest = run = 0
    for a in active:
        run = run + 1 if a else 0
        longest = max(longest, run)
    # current streak: walk back from today; today itself is allowed to be
    # quiet without breaking the streak (GitHub's own convention).
    cur = 0
    if len(active) >= 2 and active[-1]:
        cur = 1
        for a in reversed(active[:-1]):
            if a:
                cur += 1
            else:
                break
    return cur, longest


# --- language shares ----------------------------------------------------

def lang_shares(repo_langs, top=6, fold_below=0.02):
    """Language share of tracked bytes across repos, folded for the tail.

    Returns [(name, bytes, share)] with an "Other" bucket in last place.
    Shares are fractions of the total (0..1). Folding at 2% keeps the card
    readable; the fold notes how many languages went into the bucket.
    """
    totals = {}
    for langs in repo_langs.values():
        for name, size in langs.items():
            totals[name] = totals.get(name, 0) + size
    total = sum(totals.values())
    if not total:
        return []
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    out, folded, rest = [], 0, 0.0
    for name, size in ranked:
        if len(out) < top and size / total >= fold_below:
            out.append((name, size, size / total))
        else:
            folded += 1
            rest += size / total
    if folded:
        out.append((f"Other ({folded})", None, rest))
    return out


# --- calendar bands -----------------------------------------------------

def bands(days):
    """Quartile cuts of the non-zero day counts.

    Four bands off the data's own distribution rather than fractions of
    the maximum, so one heroic day cannot flatten the whole year into a
    single shade. Returns (c1, c2, c3) such that:
      1..c1 = band 1, (c1..c2] = band 2, (c2..c3] = band 3, > c3 = band 4.
    """
    counts = sorted(d["count"] for d in days if d["count"] > 0)
    if not counts:
        return 1, 1, 1

    def q(p):
        i = p * (len(counts) - 1)
        lo = counts[int(i)]
        hi = counts[min(int(i) + 1, len(counts) - 1)]
        return lo + (hi - lo) * (i - int(i))

    # distinct, non-overlapping cuts; dedupe by clamping upward
    cuts = sorted({max(1, round(q(0.25))), max(1, round(q(0.50))),
                   max(1, round(q(0.75)))})
    while len(cuts) < 3:
        cuts.append(cuts[-1] + 1)
    return tuple(cuts[:3]) + ()


def band_index(count, cuts):
    """Which of the four bands a day's count falls into (0-based)."""
    if count <= 0:
        return 0
    for i, c in enumerate(cuts):
        if count <= c:
            return i + 1
    return 4


def band_label(i, cuts):
    """Numeric range label for band i, so the reading survives greyscale."""
    ranges = ["0"]
    lo = 1
    for c in cuts:
        ranges.append(f"{lo}-{c}")
        lo = c + 1
    ranges.append(f"{lo}+")
    return ranges[i]


# --- rhythm ---------------------------------------------------------------

def rhythm_grid(commit_sample):
    """7x24 commit counts by weekday (Mon-first) and hour (UTC).

    Sampled from recent default-branch history, not the contribution
    calendar: a calendar cell is a count with no clock, and a heatmap
    made of dates would say nothing about when in the day the work
    happened.
    """
    grid = [[0] * 24 for _ in range(7)]
    for s in commit_sample:
        t = dt.datetime.fromisoformat(s["date"].replace("Z", "+00:00"))
        row = t.weekday()
        grid[row][t.hour] += 1
    return grid


# --- formatting ------------------------------------------------------------

def fmt_bytes(n):
    """Tracked-bytes formatter: KB under a megabyte, MB above."""
    if n is None:
        return ""
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} kB"
    return f"{n} B"


def fmt_share(share):
    return f"{share * 100:.1f}%"


def month_totals(year_days):
    """Twelve monthly contribution totals for one year's day list."""
    months = [0] * 12
    for d in year_days:
        months[int(d["date"][5:7]) - 1] += d["count"]
    return months
