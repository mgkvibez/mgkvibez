"""Collaboration — the part of a year's work that involved someone else.

Commits are deliberately not one of the bars: a year is hundreds of
commits against a handful of pull requests, so on a shared axis the
collaborative measures would be slivers a pixel long. Commits are the
denominator the hero figure is quoted against instead. The movement
lines come from the snapshot archive and stay absent until it is old
enough to answer.
"""
from . import history, svg, theme

W = 460
PAD = 18
PLOT_TOP = 88
PITCH = 34
BAR_H = 12
VALUE_W = 60


def render(data, entries=None):
    entries = entries or []
    collab = data.get("collab", {})
    prs = collab.get("prs", 0)
    issues = collab.get("issues", 0)
    reviews = collab.get("reviews", 0)
    acts = prs + issues + reviews
    total = data["total"]

    rows = [("pull requests", prs, "prs"),
            ("issues", issues, "issues"),
            ("reviews", reviews, "reviews")]
    rows.sort(key=lambda r: -r[1])
    share = acts / total if total else 0
    h = PLOT_TOP + len(rows) * PITCH + 24

    def trend(key, now_value):
        ago = history.days_ago(entries, 28)
        if not ago:
            return ""
        before = ago.get(key, 0)
        d = now_value - before
        return ("flat" if d == 0 else f"▲ {d}" if d > 0 else f"▼ {-d}") + " in 30d"

    out = [svg.svg_open(W, h, "Collaboration card: pull requests, issues and "
                              "reviews, with the collaborative share of all "
                              "contributions"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "contributions.collab"),
           svg.text(PAD, 52, "collaborative acts", theme.DIM, 10),
           svg.text(PAD, 74, f"{acts}", theme.FG, 20, weight="700")]
    if total:
        out.append(svg.text(
            PAD + svg.text_w(str(acts), 20) + 10, 74,
            f"{share * 100:.1f}% of all contributions "
            f"({collab.get('commits', 0)} commits the rest)",
            theme.DIM, 10))

    track_x = PAD + 104
    track_w = W - PAD - VALUE_W - 10 - track_x
    top = rows[0][1] or 1
    y = PLOT_TOP
    for label, value, key in rows:
        mv = trend(key, value)
        out.append(svg.text(PAD, y + BAR_H, label, theme.FG, 11))
        if mv:
            out.append(svg.text(PAD, y + BAR_H + 12, mv, theme.DIM, 8))
        bar_w = max(2, value / top * track_w)
        out.append(svg.rect(track_x, y, bar_w, BAR_H, theme.GREEN, rx=2))
        out.append(svg.text(W - PAD - 4, y + BAR_H, str(value), theme.DIM, 10,
                            anchor="end"))
        y += PITCH
    out.append(svg.svg_close())
    return "".join(out)
