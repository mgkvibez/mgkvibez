"""Tiny SVG helpers — enough to hand-roll cards without a dependency.

Everything renders as plain strings; xml.etree can parse the result, which
the unit tests rely on.
"""
from xml.sax.saxutils import escape

from . import theme


def esc(s):
    return escape(str(s))


def svg_open(w, h, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">\n'
        f'<title>{esc(title)}</title>\n'
        f'<defs>\n'
        f'<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">\n'
        f'<stop offset="0" stop-color="{theme.PANEL}"/>\n'
        f'<stop offset="1" stop-color="{theme.PANEL}"/>\n'
        f'</linearGradient>\n'
        f'</defs>\n'
        f'<rect width="{w}" height="{h}" rx="10" fill="{theme.BG}"/>\n'
    )


def panel(x, y, w, h):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
            f'fill="{theme.PANEL}" stroke="{theme.BORDER}" stroke-width="1"/>\n')


def dots(x, y):
    """macOS-style window dots."""
    out = []
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        out.append(f'<circle cx="{x + i * 18}" cy="{y}" r="5" fill="{c}"/>')
    return "".join(out) + "\n"


def bar(x, y, w, title):
    """Card title bar with window dots and a centred title."""
    return (
        f'<text x="{x + w / 2}" y="{y + 14}" fill="{theme.DIM}" font-family="{theme.MONO}" '
        f'font-size="11" text-anchor="middle">{esc(title)}</text>\n'
        + dots(x + 16, y + 10)
    )


def text(x, y, s, fill=None, size=13, anchor="start", weight="normal", opacity=None):
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<text x="{x}" y="{y}" fill="{fill or theme.FG}" '
            f'font-family="{theme.MONO}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{op}>{esc(s)}</text>\n')


def rect(x, y, w, h, fill, opacity=None, rx=0):
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{op}/>\n'


def line(x1, y1, x2, y2, stroke, width=1, opacity=None, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{width}"{d}{op}/>\n')


def polyline(points, stroke, width=1.5, opacity=None):
    op = f' opacity="{opacity}"' if opacity is not None else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline fill="none" stroke="{stroke}" stroke-width="{width}" points="{pts}"{op}/>\n'


def svg_close():
    return "</svg>\n"


def text_w(s, size):
    """Approx monospace advance width — good enough for cursor placement."""
    return len(s) * size * 0.6


def cursor(x, y, color=None, w=8, h=14):
    """Blinking terminal cursor. SMIL, because GitHub serves README SVGs
    via <img> (where CSS animation is unreliable and SMIL is not)."""
    c = color or theme.GREEN
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}">'
            '<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" '
            'calcMode="discrete" dur="1.1s" repeatCount="indefinite"/>'
            '</rect>\n')
