"""Language mix — share of code by tracked bytes, ranked.

Magnitude comparison, so bars scale to the leader and one hue carries all
of them; identity and value live in the direct labels, never in colour.
Only the folded "Other" bucket wears gray. The scope line says what the
token could see rather than claiming "public repositories" — a card that
overstates its own scope is a wrong number wearing a caption.
"""
from . import stats, svg, theme

W = 460
PAD = 18
LABEL_W = 104
VALUE_W = 58
PITCH = 24
BAR_H = 10
PLOT_TOP = 66


def render(data):
    langs = stats.lang_shares(data.get("repo_langs", {}))
    if not langs:
        langs = [("no tracked code yet", None, 1.0)]
    n = len(langs)
    track_x = PAD + LABEL_W
    track_w = W - PAD - VALUE_W - 10 - track_x
    h = PLOT_TOP + n * PITCH + 20

    repos = data["repos"]
    private = sum(1 for r in repos if r["private"])
    scope = f"{len(repos)} repos" + (f", {private} private" if private else "")

    out = [svg.svg_open(W, h, "Language share by tracked bytes across every "
                              "owned non-fork repository"),
           svg.panel(10, 10, W - 20, h - 20),
           svg.bar(10, 10, W - 20, f"langs.mix · {scope}"),
           svg.text(PAD, PLOT_TOP - 14,
                    "share of code by tracked bytes", theme.DIM, 10)]
    top_share = langs[0][2] or 1
    y = PLOT_TOP
    for name, size, share in langs:
        color = theme.GREEN if not name.startswith("Other") else theme.DIM
        bar_w = max(2, (share / top_share) * track_w)
        out.append(svg.text(PAD, y + BAR_H, name[:16], theme.FG, 11))
        out.append(svg.rect(track_x, y, bar_w, BAR_H, color, rx=2))
        value = f"{stats.fmt_share(share)}" + (
            f" · {stats.fmt_bytes(size)}" if size else "")
        out.append(svg.text(W - PAD - 4, y + BAR_H, value, theme.DIM, 10,
                            anchor="end"))
        y += PITCH
    out.append(svg.svg_close())
    return "".join(out)
