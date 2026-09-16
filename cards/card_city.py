"""Contribution city — every repo is a skyscraper in a night skyline.

Height ranks the building (commits + codebase size + stars + push
recency), window lights track how recently it was pushed, the facade is
tinted by the repo's primary language, and the tallest tower wears a
blinking beacon. Self-rendered like the rest of the cards — no
third-party widget APIs.
"""
from . import svg, theme

W, H = 920, 470
GROUND = 352                     # buildings stand on this baseline
LEFT, RIGHT = 34, W - 34
MAX_H, MIN_H = 252, 48
TOP_N = 10                       # city limits: tallest ten towers

# facade (dark) + cap (bright) per primary language
LANG = {
    "Python":     ("#122b41", "#3776ab"),
    "TypeScript": ("#10263f", "#3178c6"),
    "JavaScript": ("#3d3512", "#f1e05a"),
    "Dart":       ("#0d3f3d", "#00b4ab"),
    "HTML":       ("#3a1c10", "#e34c26"),
    "CSS":        ("#241a38", "#563d7c"),
    "Shell":      ("#1e3b12", "#89e051"),
    "Jupyter":    ("#3b2a10", "#da5b0b"),
    "Go":         ("#0d3a4a", "#00add8"),
    "Rust":       ("#3f2f24", "#dea584"),
    "C++":        ("#3f1226", "#f34b7d"),
    "Java":       ("#3a2410", "#b07219"),
    "C":          ("#2b2b2b", "#656565"),
    "Vue":        ("#1e2f42", "#41b883"),
    "Svelte":     ("#3a2d33", "#ff3e00"),
    "Flutter":    ("#0d3f3d", "#00b4ab"),
}
DEFAULT_FACADE = ("#152238", "#3b5f8f")
LIT, UNLIT = "#f5c56b", "#0c1420"


def _hash(s):
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) % 9973
    return h


def _score(r):
    """City rank: commits carry the skyline, size and stars add floors,
    recent pushes brighten it, retirement dims it."""
    # commits carry the skyline; size enters on a square root so a huge
    # binary-heavy repo cannot outrank an actively-committed one
    s = (r.get("commits", 0) * 5.0 + (r["size_kb"] ** 0.5)
         + r["stars"] * 20.0)
    if r["pushed_days_ago"] <= 30:
        s += 15
    elif r["pushed_days_ago"] <= 90:
        s += 8
    if r["archived"]:
        s -= 25
    return max(1.0, s)


def _lit_frac(r):
    if r["archived"]:
        return 0.10
    if r["pushed_days_ago"] <= 30:
        return 0.75
    if r["pushed_days_ago"] <= 90:
        return 0.50
    return 0.25


def _size(r):
    kb = r["size_kb"]
    return f"{kb / 1024:.1f}MB" if kb >= 1024 else f"{kb}KB"


def _ago(r):
    d = r["pushed_days_ago"]
    return f"{d}d" if d < 30 else f"{d // 30}mo"


def render(data):
    login = data["login"]
    repos = sorted(data["repos"], key=_score, reverse=True)[:TOP_N]
    n = len(repos)
    out = [svg.svg_open(W, H, f"Contribution city: repos as ranked skyscrapers "
                              f"({login})")]

    # night sky
    out.append(f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="#04070d"/>'
               f'<stop offset="1" stop-color="#0b1626"/></linearGradient>\n')
    out.append(svg.rect(12, 12, W - 24, GROUND - 12, "url(#sky)", rx=8))
    out.append(svg.rect(12, 12, W - 24, GROUND - 12, theme.PANEL, opacity=0.0))
    out.append(f'<circle cx="{W - 84}" cy="66" r="16" fill="#e8edf5"/>'
               f'<circle cx="{W - 84}" cy="66" r="26" fill="#e8edf5" opacity="0.07"/>\n')
    for i in range(26):                       # stars, seeded by login
        sx = 40 + ((_hash(login) + i * 97) % (W - 130))
        sy = 28 + ((i * 53 + _hash(login)) % 170)
        if i % 6 == 0:
            out.append(f'<circle cx="{sx}" cy="{sy}" r="1.2" fill="#c9d1d9">'
                       f'<animate attributeName="opacity" values="0.9;0.2;0.9" '
                       f'dur="{2.4 + (i % 3) * 0.7:.1f}s" repeatCount="indefinite"/>'
                       f'</circle>\n')
        else:
            out.append(f'<circle cx="{sx}" cy="{sy}" r="1" fill="#c9d1d9" '
                       f'opacity="0.55"/>\n')

    # header line, in card tradition
    cmd = f"$ skyline --owner github.com/{login}"
    out.append(svg.text(30, 34, cmd, theme.GREEN, 13))
    out.append(svg.cursor(30 + svg.text_w(cmd, 13) + 4, 21, theme.GREEN))

    # skyscrapers
    max_score = _score(repos[0]) if repos else 1.0
    slot = (RIGHT - LEFT) / max(1, n)
    for i, r in enumerate(repos):
        h = MIN_H + (MAX_H - MIN_H) * (_score(r) / max_score) ** 0.5
        bw = min(slot * 0.62, 84)
        x = LEFT + i * slot + (slot - bw) / 2
        y = GROUND - h
        facade, cap = LANG.get(r["language"], DEFAULT_FACADE)
        out.append(svg.rect(x, y, bw, h, facade))
        out.append(svg.rect(x, y, bw, 3, cap))                    # rooftop cap
        out.append(svg.line(x, y + h, x + bw, y + h, theme.BORDER))

        # window grid, lit deterministically by recency
        cols = max(2, int(bw / 10))
        rows = max(2, int(h / 12))
        gx = bw / (cols + 0.5)
        gy = h / (rows + 0.5)
        frac = _lit_frac(r)
        for ci in range(cols):
            for ri in range(rows):
                lit = (_hash(r["name"] + str(ci) + "x" + str(ri)) % 100) < frac * 100
                wx = x + gx * (ci + 0.5) - 2.5
                wy = y + gy * (ri + 0.5) - 3
                out.append(svg.rect(wx, wy, 5, 6, LIT if lit else UNLIT))

        # rank badge on the rooftop corner
        out.append(svg.rect(x + 2, y - 15, 11, 11, theme.PANEL,
                            rx=2))
        out.append(svg.text(x + 7.5, y - 6, str(i + 1), theme.DIM, 8, "middle"))

        # the tallest tower wears the blinking beacon
        if i == 0:
            mx = x + bw / 2
            out.append(svg.line(mx, y, mx, y - 20, cap, 2))
            out.append(f'<circle cx="{mx}" cy="{y - 24}" r="3" fill="#ff5f57">'
                       f'<animate attributeName="opacity" values="1;0.1;1" '
                       f'dur="1.6s" repeatCount="indefinite"/></circle>\n')

    # ground and city directory
    out.append(svg.rect(12, GROUND, W - 24, H - GROUND - 12, theme.PANEL))
    out.append(svg.line(12, GROUND, W - 12, GROUND, theme.BORDER))
    dcmd = "$ city directory --rank commits+size+stars+recency"
    out.append(svg.text(30, GROUND + 20, dcmd, theme.GREEN, 11))

    shown = repos[:10]
    for j, r in enumerate(shown):
        col, row = j // 5, j % 5
        dx = 30 + col * ((W - 60) / 2)
        dy = GROUND + 38 + row * 13
        name = r["name"] if len(r["name"]) <= 18 else r["name"][:17] + "…"
        c = r.get("commits", 0)
        line = (f"{j + 1}. {name} — {c} commit{'s' if c != 1 else ''} · "
                f"{_size(r)} · ★{r['stars']} · {_ago(r)}")
        out.append(svg.text(dx, dy, line, theme.DIM, 10))

    total_commits = sum(x.get("commits", 0) for x in data["repos"])
    pop = (f"population: {total_commits} commits across {len(data['repos'])} "
           f"repos · tallest {TOP_N} built by cards/render.py")
    out.append(svg.text(W / 2, H - 20, pop, theme.DIM, 10, "middle"))
    out.append(svg.svg_close())
    return "".join(out)
