"""Activity graph — the year's contributions accumulated as one area.

The profile used a third-party graph widget for this panel. That widget's
hosting has now died three times over (Heroku's free tier, then Cyclic,
then the Vercel deployment returning 402 Payment Required), and a profile
image that depends on somebody else's billing is a blank box waiting to
happen. This card is the same reading, drawn here from the same
contribution calendar every other card already uses: one cumulative curve
over the year, so slope is contribution rate and the height at the right
edge is the total.

Cumulative rather than daily bars because a year of daily values is 365
one-pixel columns, and the question this panel answers is "how busy, and
when", which a rising curve answers at a glance. The area fill is the
curve's own area, not a second series.
"""
import datetime

from . import stats, svg, theme

W = 920
PAD_L, PAD_R = 46, 26
TOP = 92
PLOT_H = 210
H = TOP + PLOT_H + 74


def render(data):
    days = data["days"]
    counts = [d["count"] for d in days]
    total = sum(counts)
    cumulative = []
    running = 0
    for c in counts:
        running += c
        cumulative.append(running)
    peak = max(cumulative) or 1

    left, right = PAD_L, W - PAD_R
    base = TOP + PLOT_H
    step = (right - left) / max(len(cumulative) - 1, 1)

    def x(i):
        return left + i * step

    def y(v):
        return base - (v / peak) * PLOT_H

    points = [(x(i), y(v)) for i, v in enumerate(cumulative)]
    active = sum(1 for c in counts if c > 0)
    best = max(counts) if counts else 0
    best_day = days[counts.index(best)]["date"] if counts else ""
    cur_streak, long_streak = stats.streaks(days)

    out = [svg.svg_open(W, H, f"Activity graph: {total} contributions "
                                f"accumulated across {len(days)} days"),
           svg.panel(10, 10, W - 20, H - 20),
           svg.bar(10, 10, W - 20, "contributions.graph")]

    # headline
    out.append(svg.text(PAD_L, 46, f"{total:,}", theme.GREEN, 22, weight="bold"))
    out.append(svg.text(PAD_L + svg.text_w(f"{total:,}", 22) + 8, 46,
                        "contributions, cumulative", theme.DIM, 11))
    out.append(svg.text(right, 44, f"{active} active days",
                        theme.FG, 11, anchor="end"))
    out.append(svg.text(right, 60,
                        f"best {best} on {best_day} · streak {cur_streak}d "
                        f"(longest {long_streak}d)", theme.DIM, 10, anchor="end"))

    # horizontal gridlines at quarters of the peak, labelled with real values
    for q in (4, 3, 2, 1):
        gy = y(peak * q / 4)
        out.append(svg.line(left, gy, right, gy, theme.BORDER, 1, opacity=0.7))
        out.append(svg.text(left - 8, gy + 4, f"{int(peak * q / 4):,}",
                            theme.DIM, 9, anchor="end"))
    out.append(svg.line(left, base, right, base, theme.BORDER, 1.2))

    # month ticks, taken from the dates rather than assumed evenly spaced
    seen = None
    for i, d in enumerate(days):
        month = d["date"][:7]
        if month != seen:
            seen = month
            out.append(svg.text(x(i), base + 16, d["date"][5:7],
                                theme.DIM, 9, anchor="middle"))

    # the area under the curve, then the curve itself
    area = [f"M {points[0][0]:.1f} {base:.1f}"]
    area += [f"L {px:.1f} {py:.1f}" for px, py in points]
    area.append(f"L {points[-1][0]:.1f} {base:.1f} Z")
    out.append(f'<path d="{" ".join(area)}" fill="{theme.GREEN}" '
               f'fill-opacity="0.10" stroke="none"/>')
    out.append(svg.polyline(points, theme.GREEN, 1.8))

    # a dot on the single best day, which is the one point worth naming
    if counts:
        i = counts.index(best)
        out.append(f'<circle cx="{x(i):.1f}" cy="{y(cumulative[i]):.1f}" '
                   f'r="3.2" fill="{theme.FG}"/>')

    out.append(svg.text(left, H - 22,
                        "drawn from the contribution calendar, not a remote "
                        "widget: slope is the rate, height is the total",
                        theme.DIM, 9))
    out.append(svg.svg_close())
    return "".join(out)
