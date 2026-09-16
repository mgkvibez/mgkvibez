"""Model registry — every repo is a model in production.

VERSION = stars, PARAMS = disk footprint, STATUS by last-deploy recency:
serving (< 30d), canary (30-90d), deprecated (older or archived).
"""
from . import svg, theme

W = 920
ROW_H = 26
TOP = 118
BOTTOM_PAD = 58

COLUMNS = [(30, "MODEL"), (260, "VERSION"), (360, "STATUS"),
           (500, "PARAMS"), (620, "LAST DEPLOY")]


def _status(repo):
    if repo["archived"] or repo["pushed_days_ago"] > 90:
        return "deprecated", theme.RED
    if repo["pushed_days_ago"] > 30:
        return "canary", theme.AMBER
    return "serving", theme.GREEN


def _params(kb):
    if kb >= 1024:
        return f"{kb / 1024:.1f}M"
    return f"{kb}K"


def render(data):
    repos = data["repos"]
    h = TOP + len(repos) * ROW_H + BOTTOM_PAD
    out = [svg.svg_open(W, h, "Model registry: repositories as deployed models "
                               "with version, status and size"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "model registry"),
           svg.text(30, 62, "$ model-registry list --owner "
                            f"github.com/{data['login']}", theme.GREEN, 13),
           svg.cursor(30 + svg.text_w(
               "$ model-registry list --owner github.com/" + data["login"],
               13) + 6, 50),
           svg.text(30, 84, f"{len(repos)} models registered",
                    theme.DIM, 12)]

    # header row
    out.append(svg.rect(24, TOP - 20, W - 48, 22, "#161b22"))
    for x, label in COLUMNS:
        out.append(svg.text(x, TOP - 5, label, theme.DIM, 11))
    out.append(svg.text(W - 30, TOP - 5, "TRAIN LOSS", theme.DIM, 11, "end"))

    y = TOP + 8
    for i, r in enumerate(repos):
        if i % 2 == 1:
            out.append(svg.rect(24, y - ROW_H + 6, W - 48, ROW_H,
                                "#11151c", opacity="0.6"))
        status, color = _status(r)
        out.append(svg.text(30, y, r["name"], theme.FG, 12, weight="bold"))
        out.append(svg.text(260, y, f"v{r['stars']}.{r['pushed_days_ago']}",
                            theme.DIM, 12))
        out.append(svg.text(360, y, status, color, 12))
        out.append(svg.text(500, y, f"{_params(r['size_kb'])} params",
                            theme.DIM, 12))
        out.append(svg.text(620, y, r["pushed_at"][:10], theme.DIM, 12))
        days = r["pushed_days_ago"]
        loss = f"{min(0.99, days / 365):.2f}"   # days idle = drift/loss
        out.append(svg.text(W - 30, y, loss, theme.DIM, 12, "end"))
        y += ROW_H

    serving = sum(1 for r in repos if _status(r)[0] == "serving")
    out.append(svg.line(30, y - 6, W - 30, y - 6, theme.BORDER, 1))
    out.append(svg.text(30, y + 18,
                        f"{serving} serving · registry: github.com/"
                        f"{data['login']} · version=stars, params=disk, "
                        f"train loss=days since last deploy",
                        theme.DIM, 11))
    out.append(svg.svg_close())
    return "".join(out)
