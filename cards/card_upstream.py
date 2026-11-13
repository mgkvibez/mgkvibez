"""Upstream rail — the projects I contribute to that are not mine.

Every other card here measures repos under my own account. This one faces the
other direction: the upstream projects where I have a pull request open, or
landed one inside the window, drawn as nodes hanging off a single rail with
their PR numbers. Open work sits at the top in amber, freshly merged work in
green, and everything I have stopped touching fades into the rail.
"""
from . import svg, theme

W = 920
ROW_H = 24
TOP = 132
BOTTOM_PAD = 64
NODE_X = 40
NAME_X = 58
CHIP_X = 430
CHIP_W = 92
CHIPS = 3            # PR chips per row before the "+n" collapse
RECENT_DAYS = 14


def _chip(pr):
    label = "#%d" % pr["number"]
    if pr["state"] == "merged":
        return f"{label} merged", theme.GREEN
    if pr["state"] == "open":
        return f"{label} open", theme.AMBER
    return f"{label} closed", theme.DIM


def _node(row):
    """Colour of the rail node: what kind of attention this repo needs."""
    if row["open"]:
        return theme.AMBER, "open"
    if row["last_days"] <= RECENT_DAYS:
        return theme.GREEN, "landed"
    return theme.DIM, "quiet"


def render(data):
    rows = data.get("upstream") or []
    window = data.get("upstream_window_days", 120)
    login = data.get("login", "me")
    shown = max(1, len(rows))
    h = TOP + shown * ROW_H + BOTTOM_PAD

    open_total = sum(r["open"] for r in rows)
    merged_total = sum(r["merged"] for r in rows)
    cmd = (f"$ gh pr list --author @{login} --state all "
           f"--window {window}d --not-owner")

    out = [svg.svg_open(W, h, "Upstream rail: repositories outside this account "
                             "where pull requests are open or recently merged"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "upstream --track"),
           svg.text(30, 62, cmd, theme.GREEN, 13),
           svg.cursor(30 + svg.text_w(cmd, 13) + 6, 50),
           svg.text(30, 84, f"{len(rows)} upstream repos · {open_total} open · "
                            f"{merged_total} merged", theme.DIM, 12)]

    if not rows:
        out.append(svg.text(W // 2, TOP + 40,
                            "no upstream activity in the window",
                            theme.DIM, 13, "end"))
        out.append(svg.svg_close())
        return "".join(out)

    rail_top = TOP - 6
    rail_bottom = TOP + len(rows) * ROW_H - ROW_H + 10
    out.append(svg.line(NODE_X, rail_top, NODE_X, rail_bottom,
                        theme.BORDER, 1))

    y = TOP + 8
    for i, row in enumerate(rows):
        if i % 2 == 1:
            out.append(svg.rect(24, y - ROW_H + 6, W - 48, ROW_H,
                                "#11151c", opacity="0.6"))
        colour, _ = _node(row)
        out.append(f'<circle cx="{NODE_X}" cy="{y - 4}" r="3.6" fill="{colour}"/>')
        out.append(svg.line(NODE_X + 4, y - 4, NAME_X, y - 4, theme.BORDER, 1))

        owner_w = svg.text_w(row["owner"], 12)
        out.append(svg.text(NAME_X, y, row["owner"], theme.DIM, 12))
        out.append(svg.text(NAME_X + owner_w, y, "/" + row["name"],
                            theme.FG, 12, weight="bold"))

        x = CHIP_X
        for pr in row["prs"][:CHIPS]:
            label, ink = _chip(pr)
            out.append(svg.text(x, y, label, ink, 11))
            x += CHIP_W
        extra = len(row["prs"]) - CHIPS
        if extra > 0:
            out.append(svg.text(x, y, f"+{extra}", theme.DIM, 11))

        out.append(svg.text(W - 30, y, f"{row['last_days']}d", theme.DIM, 12, "end"))
        y += ROW_H

    out.append(svg.line(30, y - 6, W - 30, y - 6, theme.BORDER, 1))
    out.append(svg.text(30, y + 18,
                        f"{open_total} open · {merged_total} merged · "
                        f"window {window}d · node = open / landed ≤"
                        f"{RECENT_DAYS}d / quiet · repos outside "
                        f"github.com/{login}",
                        theme.DIM, 11))
    out.append(svg.svg_close())
    return "".join(out)


def readme_block(data):
    """The same list as plain markdown, so the names are clickable."""
    rows = data.get("upstream") or []
    window = data.get("upstream_window_days", 120)
    if not rows:
        return f"_No upstream pull requests in the last {window} days._"
    open_total = sum(r["open"] for r in rows)
    merged_total = sum(r["merged"] for r in rows)
    lines = [f"{len(rows)} projects · {open_total} open · "
             f"{merged_total} merged in the last {window} days", ""]
    for i, row in enumerate(rows, 1):
        bits = []
        if row["open"]:
            bits.append(f"{row['open']} open")
        if row["merged"]:
            bits.append(f"{row['merged']} merged")
        bits.append(f"last {row['last_days']}d")
        nums = " ".join(f"[#{pr['number']}]({row['url']}/pull/{pr['number']})"
                        for pr in row["prs"][:4])
        lines.append(f"{i}. [{row['repo']}]({row['url']}) — "
                     f"{' · '.join(bits)} — {nums}")
    return "\n".join(lines)


START = "<!-- upstream:start -->"
END = "<!-- upstream:end -->"


def update_readme(readme, block):
    if START not in readme or END not in readme:
        return readme
    head = readme[:readme.index(START)]
    tail = readme[readme.index(END) + len(END):]
    return f"{head}{START}\n{block}\n{END}{tail}"
