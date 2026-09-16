"""Ubuntu terminal — the intro card as a Yaru GNOME Terminal window.

Same command list as the old code block (contents unchanged), but now
drawn to look like an actual Ubuntu terminal: aubergine #300A24 canvas,
GNOME headerbar with the orange close button on the right, bold green
user@host prompt, bold blue path, and a blinking block cursor.
"""
from . import svg, theme

W = 830
HEADER_H = 44
LINE_H = 27
TEXT_X = 26
TEXT_Y0 = HEADER_H + 34          # first line baseline

# Yaru / Ubuntu palette
WINDOW_BG = "#300A24"            # the canonical Ubuntu terminal purple
HEADER_BG = "#3D1225"            # aubergine headerbar
BORDER = "#1F0815"
TITLE = "#E6E6E6"
GREEN = "#26A269"                 # Ubuntu accent green (prompt user@host)
BLUE = "#739FCF"                  # Tango bright blue (prompt path)
WHITE = "#EEEEEC"
DIM = "#A898A5"                   # muted mauve for secondary text
AMBER = "#E9AD0C"                 # status warnings
CLOSE = "#E95420"                 # Ubuntu orange close button

MONO = theme.MONO


def _segments_out(out, x, y, segments, size=14):
    """Draw a run of (text, color, bold) segments left to right."""
    for text, color, bold in segments:
        out.append(svg.text(x, y, text, color, size, weight="bold" if bold else "normal"))
        x += svg.text_w(text, size)
    return x


def _prompt(out, x, y, login, cmd=None, size=14):
    segs = [(login, GREEN, True), ("@", GREEN, True),
            ("github", GREEN, True), (":", WHITE, False),
            ("~", BLUE, True), ("$ ", WHITE, False)]
    if cmd:
        segs.append((cmd, WHITE, False))
    return _segments_out(out, x, y, segs, size)


def _body_line(out, x, y, segs, size=14):
    return _segments_out(out, x, y, segs, size)


def render(data=None):
    login = (data or {}).get("login", "mgkvibez")
    lines = []                    # (kind, payload)
    lines.append(("prompt", "whoami"))
    lines.append(("body", [(login, WHITE, True), (" — ML engineer", WHITE, False)]))
    lines.append(("blank", None))
    lines.append(("prompt", "cat interests.txt"))
    lines.append(("body", [("fast inference · clean pipelines · "
                            "breaking my own infra on purpose", WHITE, False)]))
    lines.append(("blank", None))
    lines.append(("prompt", "./status.sh --check"))
    for ok in ("models serving", "pipelines green",
               "profile cards + snake self-rendered daily via Actions"):
        lines.append(("body", [("[OK]", GREEN, True), ("  " + ok, WHITE, False)]))
    lines.append(("body", [("[..]", AMBER, True), ("  coffee: low", WHITE, False)]))
    lines.append(("blank", None))
    lines.append(("prompt", "echo $CURRENTLY_BUILDING"))
    lines.append(("body", [("Project Omega — vision models + FastAPI serving "
                            "+ observability", WHITE, False)]))
    lines.append(("blank", None))
    lines.append(("prompt", None))          # trailing prompt + cursor

    h = TEXT_Y0 + (len(lines) - 1) * LINE_H + 30

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" role="img" aria-label="Ubuntu terminal: whoami">\n'
        f'<title>Ubuntu terminal: whoami</title>\n',
        # window
        f'<rect width="{W}" height="{h}" rx="12" fill="{WINDOW_BG}" '
        f'stroke="{BORDER}" stroke-width="1"/>\n',
        # headerbar (top corners rounded, bottom square)
        f'<path d="M1 12 a11 11 0 0 1 11 -11 h{W - 24} a11 11 0 0 1 11 11 '
        f'v{HEADER_H - 12} h-{W - 2} z" fill="{HEADER_BG}"/>\n',
        f'<line x1="1" y1="{HEADER_H}" x2="{W - 1}" y2="{HEADER_H}" '
        f'stroke="{BORDER}" stroke-width="1"/>\n',
        # centered title
        svg.text(W / 2, HEADER_H / 2 + 5, f"{login}@github: ~", TITLE, 12,
                 "middle", weight="bold"),
    ]
    # window controls, right side (GNOME: glyphs for min/max, orange circle close)
    cy = HEADER_H / 2
    out.append(f'<line x1="{W - 86}" y1="{cy}" x2="{W - 74}" y2="{cy}" '
               f'stroke="{TITLE}" stroke-width="1.6"/>\n')                 # minimize
    out.append(f'<rect x="{W - 58}" y="{cy - 6}" width="12" height="12" '
               f'rx="2" fill="none" stroke="{TITLE}" stroke-width="1.6"/>\n')  # maximize
    out.append(f'<circle cx="{W - 26}" cy="{cy}" r="9" fill="{CLOSE}"/>\n')
    out.append(f'<path d="M{W - 30} {cy - 4} l8 8 m0 -8 l-8 8" '
               f'stroke="#FFF" stroke-width="1.8" fill="none"/>\n')

    # terminal lines
    y = TEXT_Y0
    for kind, payload in lines:
        if kind == "prompt":
            end_x = _prompt(out, TEXT_X, y, login, payload)
            if payload is None:               # trailing prompt: blinking cursor
                out.append(svg.cursor(end_x + 2, y - 13, WHITE, w=8, h=15))
        elif kind == "body":
            _body_line(out, TEXT_X, y, payload)
        y += LINE_H

    out.append(f'<text x="{W - 26}" y="{h - 12}" fill="{DIM}" '
               f'font-family="{MONO}" font-size="10" text-anchor="end">'
               f'Yaru · #300A24</text>\n')
    out.append("</svg>\n")
    return "".join(out)
