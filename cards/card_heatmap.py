"""Contribution heatmap — a year of contributions, one cell per day.

One quantitative value over a two-dimensional time index is a heatmap;
365 bars would be two pixels wide and a line would claim continuity that
daily counts do not have. The four shades are quartiles of this profile's
own active days rather than fractions of the busiest one, so a single
heroic day cannot flatten the year into one colour. The legend prints
the numeric range of every band, so the reading survives greyscale.
"""
from . import stats, svg, theme

W = 920
TOP = 96                       # grid top
CELL, GAP = 13, 3              # cell size and gap
LEFT = 30


def render(data):
    days = data["days"]
    cuts = stats.bands(days)

    # weekday rows, Monday-first, matching the rhythm card
    by_week = {}
    for d in days:
        y, m, dd = map(int, d["date"].split("-"))
        week = __import__("datetime").date(y, m, dd).isocalendar()[1]
        by_week.setdefault((y, week), []).append(d)
    weeks = sorted(by_week)

    shades = ["#161b22", "#123d1f", "#1f7a33", "#39d353", "#00ff41"]
    labels = ["0", stats.band_label(1, cuts), stats.band_label(2, cuts),
              stats.band_label(3, cuts), stats.band_label(4, cuts)]

    grid_w = len(weeks) * (CELL + GAP) - GAP
    h = TOP + 7 * (CELL + GAP) + 74

    out = [svg.svg_open(W, h, "Contribution calendar: 53 weeks by 7 days, "
                                 "shaded in four bands by daily count"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "contributions.heatmap")]

    # month labels where the month changes along the grid
    out.append(svg.text(LEFT, TOP - 12, "2026 →", theme.DIM, 10))
    seen_month = None
    for i, wk in enumerate(weeks):
        first = by_week[wk][0]
        month = first["date"][:7]
        if month != seen_month:
            seen_month = month
            out.append(svg.text(LEFT + i * (CELL + GAP), TOP - 12,
                                first["date"][5:7], theme.DIM, 9))

    for row in range(7):
        out.append(svg.text(LEFT - 4, TOP + row * (CELL + GAP) + CELL - 2,
                            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][row],
                            theme.DIM, 9, anchor="end"))
        for i, wk in enumerate(weeks):
            d = next((x for x in by_week[wk]
                      if __import__("datetime").date(*map(int, x["date"].split("-"))).weekday() == row),
                     None)
            lvl = stats.band_index(d["count"], cuts) if d else 0
            x = LEFT + i * (CELL + GAP)
            y = TOP + row * (CELL + GAP)
            out.append(svg.rect(x, y, CELL, CELL, shades[lvl], rx=2))

    active = sum(1 for d in days if d["count"])
    quiet = len(days) - active
    out.append(svg.line(LEFT, h - 44, W - 30, h - 44, theme.BORDER, 1))
    out.append(svg.text(LEFT, h - 22,
                       f"{data['total']} contributions — {active} active days, "
                       f"{quiet} quiet. Bands are this year's own quartiles.",
                       theme.DIM, 11))
    lx = W - 30 - sum(svg.text_w(f"{l} ", 9) + CELL + 8 for l in labels)
    for i, l in enumerate(labels):
        out.append(svg.rect(lx, h - 32, CELL, CELL, shades[i], rx=2))
        lx += CELL + 4
        out.append(svg.text(lx, h - 22, l, theme.DIM, 9))
        lx += svg.text_w(l, 9) + 6
    out.append(svg.svg_close())
    return "".join(out)
