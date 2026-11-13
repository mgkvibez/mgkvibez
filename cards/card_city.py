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

W, H = 920, 600
GROUND = 470                     # buildings stand on this baseline
LEFT, RIGHT = 34, W - 34
MAX_H, MIN_H = 292, 56
TOP_N = 10                       # front row: the ten tallest
BACK_MAX = 18                    # middle tier, in perspective
FAR_MAX = 24                     # far tier: everything else
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
    # one name per line, stacked up the edge of the cluster
    for k, nm in enumerate(names):
        nm = nm if len(nm) <= 24 else nm[:23] + "…"
        out.append(svg.text(right - 2, GROUND - 10 - k * 10, nm, txt,
                            8.5, "end"))


def _tower(out, r, x, bw, h, phase, season, rank, lit_mult, dim=1.0, floors=3):
    """One building: stepped setbacks, a window grid per setback, rooftop cap.

    Setbacks are what stop a tower reading as a coloured rectangle: each
    segment up is narrower than the one below it, in proportion, so even a
    short building still looks like a building. `dim` fades a tower for the
    back row, where distance should read as haze rather than as a smaller
    copy of the same thing.
    """
    facade, cap = LANG.get(r["language"], DEFAULT_FACADE)
    frac = _lit_frac(r) * lit_mult

    segs = []
    heights = [0.56, 0.28, 0.16] if floors == 3 else [0.62, 0.38]
    cw = bw
    cy = GROUND
    for share in heights:
        sh = h * share
        cy -= sh
        segs.append((x + (bw - cw) / 2, cy, cw, sh))
        cw *= 0.82

    for sx, sy, sw, sh in segs:
        out.append(svg.rect(sx, sy, sw, sh, facade, opacity=dim))
        # light falls from the top-left, so the far edge of every face sits in
        # shadow: one gradient over the whole face, not per-window decoration
        out.append(f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" '
                   f'height="{sh:.1f}" fill="url(#tlit)" '
                   f'opacity="{0.55 * dim:.2f}"/>\n')
        out.append(svg.line(sx, sy, sx + sw, sy, theme.BORDER, 1, opacity=dim))

        cols = max(2, int(sw / 9))
        rows = max(2, int(sh / 11))
        gx = sw / (cols + 0.4)
        gy = sh / (rows + 0.4)
        for ci in range(cols):
            for ri in range(rows):
                lit = (_hash(r["name"] + str(ci) + "x" + str(ri)
                             + str(int(sy))) % 100) < frac * 100
                out.append(svg.rect(sx + gx * (ci + 0.5) - 1.8,
                                    sy + gy * (ri + 0.5) - 2.4,
                                    3.6, 4.8, LIT if lit else UNLIT,
                                    opacity=dim))

    tx, ty, tw, _ = segs[-1]
    out.append(svg.rect(tx, ty, tw, 3, cap, opacity=dim))
    if season == "winter":
        out.append(svg.rect(tx, ty + 3, tw, 2.2, "#eef4fb",
                            opacity=0.75 * dim))
    # roof furniture: the landmark aerial, a plant room for the next two, and
    # a rank badge only where a rank is being claimed (never on the back row)
    if rank == 1:
        mx = tx + tw / 2
        out.append(svg.line(mx, ty, mx, ty - 22, cap, 2, opacity=dim))
        out.append(f'<circle cx="{mx}" cy="{ty - 26}" r="3" fill="#ff5f57">'
                   f'<animate attributeName="opacity" values="1;0.1;1" '
                   f'dur="1.6s" repeatCount="indefinite"/></circle>\n')
    elif rank is not None and rank <= 3:
        out.append(svg.rect(tx + tw * 0.3, ty - 7, tw * 0.22, 7, facade,
                            opacity=dim))
    if rank is not None:
        out.append(svg.rect(tx + 2, ty - 15, 12, 11, theme.PANEL, rx=2))
        out.append(svg.text(tx + 8, ty - 6, str(rank), theme.DIM, 8, "middle"))


def render(data):
    login = data["login"]
    now = _clock(data)
    phase, season = _phase(now), _season(now)
    pub = [r for r in data["repos"] if not r.get("private", False)]
    dark = [r for r in data["repos"] if r.get("private", False)]
    ranked = sorted(pub, key=_score, reverse=True)
    repos = ranked[:TOP_N]

    # the directory below the skyline names every repo, so the canvas is sized
    # to the list rather than the list being cut to the canvas
    dcols = 4
    drows = max(1, (len(pub) + dcols - 1) // dcols)
    height = max(600, GROUND + 52 + drows * 13 + 34)
    out = [svg.svg_open(W, height, f"Contribution city ({season}, {phase}): "
                                   f"{len(pub)} repos as a ranked skyline ({login})")]

    # sky
    top, bottom = SKY[phase]
    out.append(f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="{top}"/>'
               f'<stop offset="1" stop-color="{bottom}"/></linearGradient>\n')
    out.append(svg.rect(12, 12, W - 24, GROUND - 12, "url(#sky)", rx=8))
    # one light direction for the whole city: bright edge, shaded edge
    out.append('<linearGradient id="tlit" x1="0" y1="0" x2="1" y2="0">'
               '<stop offset="0" stop-color="#ffffff" stop-opacity="0.16"/>'
               '<stop offset="0.55" stop-color="#ffffff" stop-opacity="0.02"/>'
               '<stop offset="1" stop-color="#000000" stop-opacity="0.30"/>'
               '</linearGradient>\n')

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

    # public skyscrapers in three depth tiers, so every repo stands on the
    # canvas: the ten tallest in front at full height, the next tier behind at
    # 0.66, the remainder at 0.40. Drawn far to near, each tier hazed, so
    # depth reads as distance instead of as a row of shrunken copies.
    cluster_w = min(210, 30 * min(len(dark), 8) + 26) if dark else 0
    cluster_left = RIGHT - cluster_w
    public_right = cluster_left - 16 if dark else RIGHT
    max_score = _score(repos[0]) if repos else 1.0
    lit_mult = WINDOW_LIT[phase]

    front = ranked[:TOP_N]
    mid = ranked[TOP_N:TOP_N + BACK_MAX]
    far = ranked[TOP_N + BACK_MAX:TOP_N + BACK_MAX + FAR_MAX]
    overflow = max(0, len(ranked) - TOP_N - BACK_MAX - FAR_MAX)

    def _row(buildings, scale, dim, floors, badges):
        """One tier: shared slot maths, then one _tower per building."""
        if not buildings:
            return
        slot = (public_right - LEFT) / len(buildings)
        bw_cap = 60 * scale
        for i, r in enumerate(buildings):
            h = (MIN_H + (MAX_H - MIN_H) * (_score(r) / max_score) ** 0.5) * scale
            bw = min(slot * (0.6 if badges else 0.56), bw_cap)
            x = LEFT + i * slot + (slot - bw) / 2
            rank = i + 1 if badges else None
            _tower(out, r, x, bw, h, phase, season, rank, lit_mult,
                   dim=dim, floors=floors)

    def _haze(density):
        out.append(f'<linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">'
                   f'<stop offset="0" stop-color="{bottom}" stop-opacity="0.06"/>'
                   f'<stop offset="1" stop-color="{bottom}" '
                   f'stop-opacity="{density}"/></linearGradient>\n')
        out.append(svg.rect(12, GROUND - MAX_H * 0.72, W - 24,
                            MAX_H * 0.72, "url(#haze)"))

    _row(far, 0.40, 0.34, 2, False)
    _haze(0.34)
    _row(mid, 0.66, 0.55, 2, False)
    _haze(0.22)
    _row(front, 1.0, 1.0, 3, True)

    # wet asphalt: a short column of the cap colour under each front tower
    slot = (public_right - LEFT) / max(1, len(front))
    for i, r in enumerate(front):
        bw = min(slot * 0.6, 60)
        x = LEFT + i * slot + (slot - bw) / 2
        _, cap = LANG.get(r["language"], DEFAULT_FACADE)
        out.append(svg.rect(x, GROUND, bw, 20, cap, opacity=0.09))
        out.append(svg.rect(x, GROUND + 20, bw, 10, cap, opacity=0.04))

    if overflow:
        out.append(svg.text(public_right, GROUND - 8,
                            f"+{overflow} more in the directory", theme.DIM,
                            9, "end"))

    if dark:
        dark_txt = "#16324a" if phase == "day" else theme.DIM
        _dark_towers(out, dark, cluster_left, RIGHT, dark_txt)

    # ground and city directory — every public repo, not the first ten
    out.append(svg.rect(12, GROUND, W - 24, height - GROUND - 12, theme.PANEL))
    out.append(svg.line(12, GROUND, W - 12, GROUND, theme.BORDER))
    dcmd = ("$ city directory --rank commits+size+stars+recency"
            f" -- {len(pub)} public")
    out.append(svg.text(30, GROUND + 20, dcmd, theme.GREEN, 11))

    for j, r in enumerate(ranked):
        col, row = j // drows, j % drows
        dx = 30 + col * ((W - 60) / dcols)
        dy = GROUND + 40 + row * 13
        name = r["name"] if len(r["name"]) <= 17 else r["name"][:16] + "…"
        c = r.get("commits", 0)
        line = (f"{j + 1}. {name} — {c}c · ★{r['stars']} · {_ago(r)}")
        out.append(svg.text(dx, dy, line, theme.DIM, 9))

    total_commits = sum(x.get("commits", 0) for x in pub)
    pop = (f"population: {total_commits} commits across {len(pub)} repos"
           + (f" · {min(len(dark), 8)} dark towers (private, names only)"
              if dark else "")
           + f" · {season} · {phase} · rendered hourly in WAT")
    out.append(svg.text(W / 2, height - 18, pop, theme.DIM, 10, "middle"))
    out.append(svg.svg_close())
    return "".join(out)
