"""Port scan — every repo is a service on host github.com/mgkvibez.

Port number is a stable hash of the repo name, so a repo keeps its port
across days. State by recency: open = pushed in the last 30 days,
filtered = 90 days, closed = older or archived.
"""
from . import svg, theme

W = 920
ROW_H = 24
TOP = 118                     # first port line y
BOTTOM_PAD = 58


def _port(name):
    return 1024 + (sum(ord(c) * (i + 1) for i, c in enumerate(name)) % 64000)


def _state(repo):
    if repo["archived"] or repo["pushed_days_ago"] > 90:
        return "closed", theme.DIM
    if repo["pushed_days_ago"] > 30:
        return "filtered", theme.AMBER
    return "open", theme.GREEN


def render(data):
    repos = data["repos"]
    h = TOP + len(repos) * ROW_H + BOTTOM_PAD
    cmd = f"$ nmap -sV --profile github.com/{data['login']}"
    out = [svg.svg_open(W, h, "Port scan: repositories as nmap services, "
                               "state by last-push recency"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "nmap profile-scan"),
           svg.text(30, 62, cmd, theme.GREEN, 13),
           svg.cursor(30 + svg.text_w(cmd, 13) + 6, 50),
           svg.text(30, 84, f"Starting NMAP 7.95 ( github.com/{data['login']} ) "
                            f"at {data['fetched_at'][:10]}",
                    theme.DIM, 12),
           svg.text(30, TOP - 14, "PORT      STATE     SERVICE      VERSION "
                                  "(repo, stars, size)", theme.DIM, 11)]

    y = TOP
    for r in repos:
        state, color = _state(r)
        size = (f"{r['size_kb'] / 1024:.1f} MB" if r["size_kb"] >= 1024
                else f"{r['size_kb']} KB")
        svc = r["language"].lower()
        out.append(svg.text(30, y, f"{_port(r['name'])}/tcp", theme.FG, 12))
        out.append(svg.text(120, y, state, color, 12))
        out.append(svg.text(220, y, svc, theme.CYAN, 12))
        out.append(svg.text(330, y,
                            f"{r['name']} ({r['stars']}\u2605, {size})",
                            theme.DIM, 12))
        y += ROW_H

    open_n = sum(1 for r in repos if _state(r)[0] == "open")
    out.append(svg.line(30, y - 4, W - 30, y - 4, theme.BORDER, 1))
    out.append(svg.text(30, y + 20,
                        f"Nmap done: 1 host up — {len(repos)} services "
                        f"fingerprinted, {open_n} open in the last 30 days",
                        theme.DIM, 11))
    out.append(svg.svg_close())
    return "".join(out)
