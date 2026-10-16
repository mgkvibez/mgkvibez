"""Drift — what the language mix is turning into.

Every other card is a level; this is the only derivative. The
interesting thing about a language mix is not its shape today but which
way it is moving, and nobody can infer "Python is up four points since
last month" from anything but a record kept on purpose. Form: one
dumbbell per language — a hollow dot for then, a filled dot for now,
the connector carrying the direction, the signed change in points at
the right. Points, not percent-of-percent: 40 to 44 is four points,
and billing it as "10% growth" is a much weaker claim.

Until the snapshot archive is about a month old there is no honest
"then" to draw, and the card says exactly that.
"""
from . import history, stats, svg, theme

W = 460
PAD = 18
PLOT_TOP = 86
PITCH = 26
PLOT_H = 128


def render(data, entries=None):
    entries = entries or []
    langs = stats.lang_shares(data.get("repo_langs", {}))
    ago = history.days_ago(entries, 28)

    pairs = []
    if ago:
        then = ago.get("langs", {})
        for name, _, share in langs:
            old = then.get(name, 0.0)
            pairs.append((name, old, share))
        pairs.sort(key=lambda p: abs(p[2] - p[1]), reverse=True)
        pairs = pairs[:7]

    h = PLOT_TOP + max(len(pairs), 1) * PITCH + 24
    out = [svg.svg_open(W, h, "Language drift: a dumbbell per language, share "
                               "a month ago versus now, change in points"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, "langs.drift"),
           svg.text(PAD, 56, "share of tracked bytes, then → now",
                    theme.DIM, 10)]

    if not ago:
        out.append(svg.text(
            PAD, PLOT_TOP + 6,
            "archive started %s — drift needs a month of snapshots."
            % (entries[0]["date"] if entries else "today"),
            theme.DIM, 11))
        out.append(svg.text(PAD, PLOT_TOP + 24,
                            "check back in ~4 weeks; no invented numbers.",
                            theme.DIM, 11))
        out.append(svg.svg_close())
        return "".join(out)

    scale = max((max(p[1], p[2]) for p in pairs), default=1.0)
    track_w = W - PAD - 76 - (PAD + 104)
    x0 = PAD + 104
    for i, (name, old, now) in enumerate(pairs):
        y = PLOT_TOP + i * PITCH + 8
        out.append(svg.text(PAD, y + 4, name[:16], theme.FG, 10))
        x_then, x_now = x0 + old / scale * track_w, x0 + now / scale * track_w
        out.append(svg.line(x_then, y, x_now, y, theme.BORDER, 2))
        out.append(f'<circle cx="{x_then:.1f}" cy="{y}" r="4" '
                   f'fill="{theme.PANEL}" stroke="{theme.DIM}" '
                   f'stroke-width="1.5"/>\n')
        out.append(f'<circle cx="{x_now:.1f}" cy="{y}" r="4" '
                   f'fill="{theme.GREEN}"/>\n')
        d = now - old
        color = theme.GREEN if d > 0 else theme.RED if d < 0 else theme.DIM
        glyph = "▲" if d > 0 else "▼" if d < 0 else "·"
        out.append(svg.text(W - PAD - 4, y + 4,
                            f"{glyph} {abs(d) * 100:.1f} pt", color, 9,
                            anchor="end"))
    out.append(svg.svg_close())
    return "".join(out)
