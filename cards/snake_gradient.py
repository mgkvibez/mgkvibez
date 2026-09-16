"""Post-process snk SVGs: paint the snake blue -> green along its journey.

snk's grid animation lights each cell briefly as the snake passes. The
flash colour is normally the contribution colour (light theme) or a flat
snake colour (dark theme). This rewrites every flash so the colour
interpolates from blue at the start of the run to the profile's terminal
green by the end — the snake literally turns green as it eats commits.
"""
import re
import sys

# flash keyframe: "<percent>%{fill:<value>}"
FLASH = re.compile(r"([\d.]+)%\{fill:([^}]+)\}")

# journey colours per theme: (start blue, end green)
PALETTES = {
    "light": ((9, 105, 218), (38, 174, 74)),    # GitHub blue -> GitHub green
    "dark": ((0, 198, 255), (0, 255, 65)),       # electric blue -> #00ff41
}


def _hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def journey_color(frac, theme="dark"):
    """Colour of the snake at 0..1 along its run."""
    start, end = PALETTES[theme]
    c = tuple(round(a + (b - a) * frac) for a, b in zip(start, end))
    return _hex(c)


def paint(svg, theme="dark"):
    """Rewrite every snake flash in an snk SVG's keyframes.

    Turn-on keyframes carry the flash colour (a literal or a var(--cN));
    turn-off keyframes always reference var(--ce) and stay untouched.
    """
    flashes = [m for m in FLASH.finditer(svg)
               if m.group(2).strip() != "var(--ce)"]
    if flashes:
        ts = [float(f.group(1)) for f in flashes]
        lo, hi = min(ts), max(ts)
        if hi - lo < 1e-9:
            lo, hi = 0.0, 1.0

        def repl(mo):
            if mo.group(2).strip() == "var(--ce)":
                return mo.group(0)        # turn-off keyframe: leave it
            t = float(mo.group(1))
            frac = (t - lo) / (hi - lo)
            return "{}%{{fill:{}}}".format(mo.group(1), journey_color(frac, theme))

        svg = FLASH.sub(repl, svg)
    return paint_body(svg, theme)


def paint_body(svg, theme="dark"):
    """Make the snake body itself shift blue -> green over its run.

    The body segments share one fill: the --cs custom property. We register
    it with @property (so it interpolates), add an `eat` animation on
    :root that walks the same journey palette as the cell flashes, and
    normalise the base value so a browser without @property support still
    shows the end colour instead of snk's defaults.
    """
    start, end = PALETTES[theme]
    # normalise the base body colour (snk default is purple on light)
    svg = svg.replace("--cs:purple", "--cs:" + _hex(end))

    m = re.search(r"animation:none (?:[\w-]+ )*?(\d+)ms infinite", svg)
    dur = m.group(1) if m else "16700"
    body_end = 99.4                       # body segments finish here
    stops = "".join(
        "{}%{{--cs:{}}}".format(i, journey_color(min(1.0, i / body_end), theme))
        for i in range(0, 101, 5))

    # the stops string already ends with "}" closing eat; assemble cleanly
    # NOTE: '<color>' must be XML-escaped inside the SVG's <style> text —
    # raw angle brackets make the whole document malformed and GitHub
    # will refuse to render it. Browsers decode the entities back to
    # plain <color> before handing the style text to the CSS engine.
    inject = (
        "@property --cs{{syntax:'&lt;color&gt;';inherits:true;"
        "initial-value:{}}}".format(_hex(end)) +
        "@keyframes eat{{".format() + stops + "}" +
        ":root{{animation:eat {}ms linear infinite}}".format(dur)
    )
    return svg.replace("</style>", inject + "</style>", 1)


def main(argv):
    if len(argv) != 3 or argv[2] not in PALETTES:
        sys.exit("usage: snake_gradient.py <snk.svg> <light|dark>")
    path, theme = argv[1], argv[2]
    svg = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write(paint(svg, theme))
    print(f"painted {path} ({theme}) blue -> green")


if __name__ == "__main__":
    main(sys.argv)
