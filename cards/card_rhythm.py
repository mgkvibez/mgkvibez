"""Commit rhythm — when in the week, and the day, the work happens.

A 7 by 24 heatmap sampled from recent default-branch history: the
contribution calendar is a count with no clock, and a rhythm made of
dates would say nothing about hours. Every stamp in the sample is UTC
— the card says so rather than silently guessing a timezone. The same
sequential ramp as the calendar card, because both are magnitudes.
"""
from . import stats, svg, theme

W = 460
PAD = 18
TOP = 76
CELL, GAP = 12, 3
LEFT = 40


def render(data):
    grid = stats.rhythm_grid(data.get("commit_sample", []))
    sample = sum(sum(row) for row in grid)
    h = TOP + 7 * (CELL + GAP) + 58

    shades = ["#161b22", "#123d1f", "#1f7a33", "#39d353", "#00ff41"]
    out = [svg.svg_open(W, h, "Commit rhythm: a 7 by 24 heatmap of commits by "
                              "day of week and hour of day"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "commits.rhythm"),
           svg.text(PAD, TOP - 12, "hour (UTC)      Mon → Sun", theme.DIM, 9)]

    for col in (0, 6, 12, 18):
        out.append(svg.text(LEFT + col * (CELL + GAP) + 2, TOP - 2,
                            f"{col:02d}", theme.DIM, 8))

    peak = max((max(row) for row in grid), default=0) or 1
    all_counts = [v for row in grid for v in row if v]
    # three cuts spread over the sample's own active cells
    cuts = stats.bands([{"count": v} for v in all_counts]) if all_counts else (1, 1, 1)

    for r, row in enumerate(grid):
        out.append(svg.text(LEFT - 6, TOP + r * (CELL + GAP) + CELL - 2,
                            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][r],
                            theme.DIM, 8, anchor="end"))
        for c, v in enumerate(row):
            lvl = stats.band_index(v, cuts) if v else 0
            out.append(svg.rect(LEFT + c * (CELL + GAP),
                                TOP + r * (CELL + GAP), CELL, CELL,
                                shades[lvl], rx=2))

    if sample:
        wk = sum(sum(row) for row in grid[5:]) / sample
        peak_r, peak_c = max(((r, c) for r in range(7) for c in range(24)),
                             key=lambda rc: grid[rc[0]][rc[1]])
        nights = sum(grid[r][c] for r in range(7) for c in
                     list(range(0, 6)) + list(range(22, 24))) / sample
        day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][peak_r]
        out.append(svg.text(PAD, h - 26,
                            f"{sample} commits sampled — busiest {day} "
                            f"{peak_c:02d}:00, weekend {wk * 100:.0f}%, "
                            f"nights {nights * 100:.0f}%", theme.DIM, 9))
    else:
        out.append(svg.text(PAD, h - 26,
                            "no commit sample available yet", theme.DIM, 9))
    out.append(svg.svg_close())
    return "".join(out)
