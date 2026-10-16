"""Years — contributions by year and month, one row per year.

Twelve monthly cells per row shaded in four bands, each year's total in
a column at the right. Bands come from the monthly totals across the
shown years, so the shading is the profile's own distribution. Years
before the account existed are absent rather than zero: an empty row
measures nothing.
"""
import datetime as dt

from . import stats, svg, theme

W = 460
PAD = 18
TOP = 74
CELL, GAP = 12, 3
LEFT = 52
PITCH = CELL + GAP + 14


def render(data):
    created = data.get("created_at") or ""
    years = [y for y in data.get("years", []) if y["total"] > 0 or
             (created[:4] and y["year"] == int(created[:4]))]
    years.sort(key=lambda y: y["year"])
    h = TOP + max(len(years), 1) * PITCH + 26

    months = [stats.month_totals(y["days"]) for y in years]
    flat = [m for row in months for m in row if m]
    cuts = stats.bands([{"count": m} for m in flat]) if flat else (1, 1, 1)
    shades = ["#161b22", "#123d1f", "#1f7a33", "#39d353", "#00ff41"]

    out = [svg.svg_open(W, h, "Contributions by year and month: one row per "
                              "year, twelve monthly cells in four bands"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "contributions.years"),
           svg.text(PAD, TOP - 12, "J F M A M J J A S O N D   "
                                   "year   total", theme.DIM, 9)]

    for yi, y in enumerate(years):
        row_y = TOP + yi * PITCH
        total = y["total"]
        out.append(svg.text(LEFT - 8, row_y + CELL, str(y["year"]),
                            theme.FG if total else theme.DIM, 10,
                            anchor="end"))
        for mi, m in enumerate(months[yi]):
            lvl = stats.band_index(m, cuts) if m else 0
            out.append(svg.rect(LEFT + mi * (CELL + GAP), row_y,
                                CELL, CELL, shades[lvl], rx=2))
        color = theme.GREEN if total and yi == len(years) - 1 else theme.DIM
        out.append(svg.text(W - PAD - 4, row_y + CELL, str(total),
                            color, 10, anchor="end"))

    if not years:
        out.append(svg.text(PAD, TOP + 14, "no contribution history yet",
                            theme.DIM, 11))
    out.append(svg.svg_close())
    return "".join(out)
