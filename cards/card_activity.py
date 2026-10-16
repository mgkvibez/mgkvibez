"""Activity — the headline numbers and a 30-day sparkline.

A handful of headline numbers is a KPI row of stat tiles, not a grouped
bar chart. Deltas come from the day windows (or the snapshot archive,
where a trend needs history); where the archive is too young to answer,
the delta is simply absent — no invented numbers.
"""
from . import history, stats, svg, theme

W = 460
PAD = 18
SPARK_H = 34


def _delta(now, before, unit="30d"):
    if now > before:
        return f"▲ {now - before} in {unit}", theme.GREEN
    if now < before:
        return f"▼ {before - now} in {unit}", theme.RED
    return f"flat over {unit}", theme.DIM


def _trend(entries, key, now_value):
    """Movement line from the archive, or '' when it cannot answer yet."""
    ago = history.days_ago(entries, 28)
    if not ago:
        return ""
    before = ago.get(key, 0)
    d, _ = _delta(now_value, before)
    return d


def render(data, entries=None):
    entries = entries or []
    days = data["days"]
    recent = days[-30:]
    prior = days[-60:-30]
    cur_streak, long_streak = stats.streaks(days)

    hero_label_y, hero_val_y = 56, 96
    tiles_top = hero_val_y + 22
    tile_h = 48
    spark_top = tiles_top + tile_h + 22
    h = spark_top + SPARK_H + 26

    collab = data.get("collab", {})
    stars = sum(r["stars"] for r in data["repos"])
    tiles = [
        ("current streak", f"{cur_streak}d", ""),
        ("longest streak", f"{long_streak}d", ""),
        ("commits", str(collab.get("commits", 0)),
         _trend(entries, "commits", collab.get("commits", 0))),
        ("stars earned", str(stars),
         _trend(entries, "stars", stars)),
    ]

    out = [svg.svg_open(W, h, "Contribution activity: totals, streaks and a "
                              "30-day sparkline"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "contributions.activity · last 365 days"),
           svg.text(PAD, hero_label_y, "contributions", theme.DIM, 10)]
    hero = f"{data['total']}"
    out.append(svg.text(PAD, hero_val_y, hero, theme.FG, 34, weight="700"))
    if recent and prior:
        d, color = _delta(sum(d["count"] for d in recent),
                          sum(d["count"] for d in prior))
        out.append(svg.text(PAD + svg.text_w(hero, 34) + 12, hero_val_y - 4,
                            d, color, 11))

    tw = (W - 2 * PAD - 3 * 10) / 4
    for i, (label, value, delta) in enumerate(tiles):
        x = PAD + i * (tw + 10)
        out.append(svg.rect(x, tiles_top, tw, tile_h, theme.BORDER, rx=6))
        out.append(svg.text(x + 8, tiles_top + 16, label, theme.DIM, 9))
        out.append(svg.text(x + 8, tiles_top + 34, value, theme.FG, 15,
                            weight="700"))
        if delta:
            out.append(svg.text(x + 8, tiles_top + 45, delta[:18], theme.DIM, 8))

    peak = max((d["count"] for d in recent), default=0) or 1
    out.append(svg.text(PAD, spark_top - 8, "last 30 days", theme.DIM, 10))
    bw = (W - 2 * PAD) / 30
    for i, d in enumerate(recent):
        bh = max(2, d["count"] / peak * SPARK_H)
        out.append(svg.rect(PAD + i * bw, spark_top + SPARK_H - bh,
                            max(bw - 2, 1.5), bh,
                            theme.GREEN if d["count"] else "#12331d", rx=1))
    out.append(svg.svg_close())
    return "".join(out)
