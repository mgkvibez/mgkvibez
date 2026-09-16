"""Contribution city — every repo is a skyscraper in a living skyline.

The sky follows the real clock in West African Time (WAT, UTC+1): dawn,
day, dusk and night each get their own sky, sun or moon, and window
lights. The seasons pass through it — snow in winter, blossom petals in
spring, falling leaves in autumn. Height ranks the building (commits +
codebase size + stars), the facade is tinted by primary language, and
the tallest tower wears a blinking beacon.

Private repos rise as dark towers on the far edge of the skyline —
anonymous silhouettes, names only, no stats.

Re-rendered hourly by the cards workflow, so the sky keeps real time
and a new repo gets its skyscraper within the hour. Self-rendered — no
third-party widget APIs.
"""
import datetime as dt

from . import svg, theme

W, H = 920, 470
GROUND = 352                     # buildings stand on this baseline
LEFT, RIGHT = 34, W - 34
MAX_H, MIN_H = 252, 48
TOP_N = 10                       # city limits: tallest ten towers
WAT = dt.timezone(dt.timedelta(hours=1))   # West African Time, UTC+1

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
DARK_TOWER = "#0d1117"           # private silhouettes

# sky gradients and window-lit multipliers per phase
SKY = {
    "night": ("#04070d", "#0b1626"),
    "dawn":  ("#241c38", "#8a4a4c"),
    "day":   ("#5d96cf", "#aecbee"),
    "dusk":  ("#2b1a30", "#c06a3a"),
}
HEADER = {"night": theme.GREEN, "dawn": theme.GREEN,
          "dusk": theme.GREEN, "day": "#16324a"}
WINDOW_LIT = {"night": 1.0, "dusk": 0.85, "dawn": 0.6, "day": 0.12}
PARTICLE = {"winter": ("#eef4fa", "circle"), "spring": ("#f2a9c0", "circle"),
            "autumn": ("#d7843c", "leaf")}


def _hash(s):
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) % 9973
    return h


def _clock(data):
    """Render clock: the data snapshot time, in WAT."""
    s = data.get("fetched_at") or "2026-09-16T11:45:00+00:00"
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.astimezone(WAT)


def _phase(now):
    h = now.hour + now.minute / 60
    if 5 <= h < 7:
        return "dawn"
    if 7 <= h < 17:
        return "day"
    if 17 <= h < 19:
        return "dusk"
    return "night"


def _season(now):
    m = now.month
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


def _score(r):
    """City rank: commits carry the skyline; size and stars add floors,
    recent pushes brighten it, retirement dims it."""
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


def _particles(out, login, season):
    """Seasonal weather falling over the skyline (SMIL, deterministic)."""
    if season not in PARTICLE:
        return
    color, shape = PARTICLE[season]
    for i in range(14):
        px = 40 + ((_hash(login + "pp") + i * 137) % (W - 130))
        py = -30 + ((i * 53 + _hash(login)) % 60)
        fall = GROUND - 30 - py
        dur = f"{9 + (i % 6)}.{i % 10}s"
        begin = f"-{(i * 1.7) % 9:.1f}s"
        if shape == "circle":
            out.append(f'<circle cx="{px}" cy="{py}" r="1.6" fill="{color}" '
                       f'opacity="0.85">'
                       f'<animateTransform attributeName="transform" '
                       f'type="translate" from="0 0" to="0 {fall}" '
                       f'dur="{dur}" begin="{begin}" '
                       f'repeatCount="indefinite"/></circle>\n')
        else:
            out.append(f'<rect x="{px}" y="{py}" width="2.5" height="4" '
                       f'fill="{color}" opacity="0.85">'
                       f'<animateTransform attributeName="transform" '
                       f'type="translate" from="0 0" to="0 {fall}" '
                       f'dur="{dur}" begin="{begin}" '
                       f'repeatCount="indefinite"/></rect>\n')


def _dark_towers(out, dark, left, right, txt):
    """Private repos: anonymous silhouette towers, names only — no
    windows, no rank badges, no stats."""
    shown = sorted(dark, key=_score, reverse=True)[:8]
    n = len(shown)
    slot = (right - left) / max(1, n)
    for i, r in enumerate(shown):
        h = MAX_H * (0.62 + 0.38 * (i / max(1, n - 1)))
        bw = min(slot * 0.6, 22)
        x = left + i * slot + (slot - bw) / 2
        y = GROUND - h
        out.append(svg.rect(x, y, bw, h, DARK_TOWER))
        out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{h}" '
                   f'fill="none" stroke="{theme.BORDER}" stroke-width="1" '
                   f'rx="1"/>\n')
        out.append(svg.line(x + bw / 2, y, x + bw / 2, y - 12,
                            theme.BORDER, 1))
    names = [r["name"] for r in shown]
    if len(dark) > 8:
        names[-1] = f"+{len(dark) - 7} more"
    txt_size = 9
    rows = [" · ".join(names[:4]), " · ".join(names[4:8])]
    if rows[1]:
        out.append(svg.text(right, GROUND - 22, rows[1], txt, txt_size,
                            "end"))
    out.append(svg.text(right, GROUND - 10, rows[0], txt, txt_size, "end"))


def render(data):
    login = data["login"]
    now = _clock(data)
    phase, season = _phase(now), _season(now)
    pub = [r for r in data["repos"] if not r.get("private", False)]
    dark = [r for r in data["repos"] if r.get("private", False)]
    repos = sorted(pub, key=_score, reverse=True)[:TOP_N]
    n = len(repos)
    out = [svg.svg_open(W, H, f"Contribution city ({season}, {phase}): "
                              f"repos as ranked skyscrapers ({login})")]

    # sky
    top, bottom = SKY[phase]
    out.append(f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="{top}"/>'
               f'<stop offset="1" stop-color="{bottom}"/></linearGradient>\n')
    out.append(svg.rect(12, 12, W - 24, GROUND - 12, "url(#sky)", rx=8))

    # celestial body: sun by day, moon by night
    if phase == "night":
        out.append(f'<circle cx="{W - 84}" cy="66" r="16" fill="#e8edf5"/>'
                   f'<circle cx="{W - 84}" cy="66" r="26" fill="#e8edf5" '
                   f'opacity="0.07"/>\n')
        for i in range(26):                       # stars, seeded by login
            sx = 40 + ((_hash(login) + i * 97) % (W - 130))
            sy = 28 + ((i * 53 + _hash(login)) % 170)
            if i % 6 == 0:
                out.append(f'<circle cx="{sx}" cy="{sy}" r="1.2" '
                           f'fill="#c9d1d9">'
                           f'<animate attributeName="opacity" '
                           f'values="0.9;0.2;0.9" '
                           f'dur="{2.4 + (i % 3) * 0.7:.1f}s" '
                           f'repeatCount="indefinite"/></circle>\n')
            else:
                out.append(f'<circle cx="{sx}" cy="{sy}" r="1" '
                           f'fill="#c9d1d9" opacity="0.55"/>\n')
    else:
        sy = 64 if phase == "day" else 128       # low sun at dawn/dusk
        out.append(f'<circle cx="{W - 84}" cy="{sy}" r="20" '
                   f'fill="#ffd75e"/>'
                   f'<circle cx="{W - 84}" cy="{sy}" r="34" fill="#ffd75e" '
                   f'opacity="0.25"/>\n')
        if season == "summer":
            out.append(f'<circle cx="{W - 84}" cy="{sy}" r="48" '
                       f'fill="#ffd75e" opacity="0.12"/>\n')

    _particles(out, login, season)

    # header line, in card tradition
    hdr = HEADER[phase]
    cmd = f"$ skyline --owner github.com/{login}"
    out.append(svg.text(30, 34, cmd, hdr, 13))
    out.append(svg.cursor(30 + svg.text_w(cmd, 13) + 4, 21, hdr))

    # public skyscrapers get the main skyline; dark towers the far edge
    cluster_w = min(230, 34 * min(len(dark), 8) + 30) if dark else 0
    cluster_left = RIGHT - cluster_w
    public_right = cluster_left - 14 if dark else RIGHT

    max_score = _score(repos[0]) if repos else 1.0
    slot = (public_right - LEFT) / max(1, n)
    lit_mult = WINDOW_LIT[phase]
    for i, r in enumerate(repos):
        h = MIN_H + (MAX_H - MIN_H) * (_score(r) / max_score) ** 0.5
        bw = min(slot * 0.62, 84)
        x = LEFT + i * slot + (slot - bw) / 2
        y = GROUND - h
        facade, cap = LANG.get(r["language"], DEFAULT_FACADE)
        out.append(svg.rect(x, y, bw, h, facade))
        out.append(svg.rect(x, y, bw, 3, cap))                    # rooftop cap
        if season == "winter":                       # snow settles on roofs
            out.append(svg.rect(x, y + 3, bw, 2.5, "#eef4fb", opacity=0.8))
        out.append(svg.line(x, y + h, x + bw, y + h, theme.BORDER))

        # window grid, lit deterministically by recency and time of day
        cols = max(2, int(bw / 10))
        rows = max(2, int(h / 12))
        gx = bw / (cols + 0.5)
        gy = h / (rows + 0.5)
        frac = _lit_frac(r) * lit_mult
        for ci in range(cols):
            for ri in range(rows):
                lit = (_hash(r["name"] + str(ci) + "x" + str(ri))
                       % 100) < frac * 100
                wx = x + gx * (ci + 0.5) - 2.5
                wy = y + gy * (ri + 0.5) - 3
                out.append(svg.rect(wx, wy, 5, 6, LIT if lit else UNLIT))

        # rank badge on the rooftop corner
        out.append(svg.rect(x + 2, y - 15, 11, 11, theme.PANEL, rx=2))
        out.append(svg.text(x + 7.5, y - 6, str(i + 1), theme.DIM, 8,
                            "middle"))

        # the tallest tower wears the blinking beacon
        if i == 0:
            mx = x + bw / 2
            out.append(svg.line(mx, y, mx, y - 20, cap, 2))
            out.append(f'<circle cx="{mx}" cy="{y - 24}" r="3" '
                       f'fill="#ff5f57">'
                       f'<animate attributeName="opacity" values="1;0.1;1" '
                       f'dur="1.6s" repeatCount="indefinite"/></circle>\n')

    if dark:
        dark_txt = "#16324a" if phase == "day" else theme.DIM
        _dark_towers(out, dark, cluster_left, RIGHT, dark_txt)

    # ground and city directory
    out.append(svg.rect(12, GROUND, W - 24, H - GROUND - 12, theme.PANEL))
    out.append(svg.line(12, GROUND, W - 12, GROUND, theme.BORDER))
    dcmd = "$ city directory --rank commits+size+stars+recency"
    out.append(svg.text(30, GROUND + 20, dcmd, theme.GREEN, 11))

    for j, r in enumerate(repos[:10]):
        col, row = j // 5, j % 5
        dx = 30 + col * ((W - 60) / 2)
        dy = GROUND + 38 + row * 13
        name = r["name"] if len(r["name"]) <= 18 else r["name"][:17] + "…"
        c = r.get("commits", 0)
        line = (f"{j + 1}. {name} — {c} commit{'s' if c != 1 else ''} · "
                f"{_size(r)} · ★{r['stars']} · {_ago(r)}")
        out.append(svg.text(dx, dy, line, theme.DIM, 10))

    total_commits = sum(x.get("commits", 0) for x in pub)
    pop = (f"population: {total_commits} commits across {len(pub)} repos"
           + (f" · {min(len(dark), 8)} dark towers (private, names only)"
              if dark else "")
           + f" · {season} · {phase} · rendered hourly in WAT")
    out.append(svg.text(W / 2, H - 20, pop, theme.DIM, 10, "middle"))
    out.append(svg.svg_close())
    return "".join(out)
