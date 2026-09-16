"""Oscilloscope — a year of contributions as a phosphor waveform.

One sample per day, sample-and-hold style: the trace rides the centerline
and jumps to the day's count. Glow = same polyline twice.
"""
from . import svg, theme

W, H = 920, 330
SX0, SX1, SY0, SY1 = 60, 640, 60, 250     # screen area
DIVS_X, DIVS_Y = 10, 6
V_PER_DIV = 10                            # commits per vertical division


def render(data):
    days = data["days"]
    max_c = max((d["count"] for d in days), default=0)
    peak = max(max_c, 1)
    span = SY0 + (SY1 - SY0) / 2            # centerline
    div_px = (SY1 - SY0) / DIVS_Y           # pixels per division
    # scale so the peak fits the upper three divisions (half the screen)
    px_per_commit = div_px / V_PER_DIV * min(1.0, (2.6 * V_PER_DIV) / peak)

    out = [svg.svg_open(W, H, "Oscilloscope: daily contribution counts as a "
                              "phosphor waveform"),
           svg.panel(10, 10, W - 20, H - 20),
           svg.bar(10, 10, W - 20, "contributions.scope"),
           # screen
           svg.rect(SX0 - 8, SY0 - 8, SX1 - SX0 + 16, SY1 - SY0 + 16,
                    theme.BORDER, rx=6),
           svg.rect(SX0, SY0, SX1 - SX0, SY1 - SY0, theme.SCOPE_BG)]

    # graticule
    dw = (SX1 - SX0) / DIVS_X
    dh = (SY1 - SY0) / DIVS_Y
    for i in range(1, DIVS_X):
        out.append(svg.line(SX0 + i * dw, SY0, SX0 + i * dw, SY1,
                            "#0f3a1f", 1))
    for i in range(1, DIVS_Y):
        if i == DIVS_Y // 2:
            continue
        out.append(svg.line(SX0, SY0 + i * dh, SX1, SY0 + i * dh, "#0f3a1f", 1))
    out.append(svg.line(SX0, span, SX1, span, "#1d5c33", 1, dash="6 6"))

    # waveform: sample-and-hold over the last 365 days
    pts = []
    n = len(days)
    for i, d in enumerate(days):
        x = SX0 + (SX1 - SX0) * i / max(n - 1, 1)
        amp = d["count"] * px_per_commit
        if d["count"] > 0:
            pts.append((x, span))       # sample edge
            pts.append((x, span - amp))  # held level
        else:
            pts.append((x, span))
    if pts:
        out.append(svg.polyline(pts, theme.PHOSPHOR, 6, opacity=0.18))
        out.append(svg.polyline(pts, theme.PHOSPHOR, 1.4))

    # phosphor sweep — a scan line running across the screen
    for sw, op in ((1.5, 0.55), (6, 0.14)):
        out.append(
            f'<line x1="{SX0}" y1="{SY0}" x2="{SX0}" y2="{SY1}" '
            f'stroke="{theme.PHOSPHOR}" stroke-width="{sw}" opacity="{op}">'
            f'<animate attributeName="x1" values="{SX0};{SX1}" dur="7s" '
            f'repeatCount="indefinite"/>'
            f'<animate attributeName="x2" values="{SX0};{SX1}" dur="7s" '
            f'repeatCount="indefinite"/></line>\n')

    # readouts
    mean = sum(d["count"] for d in days) / max(n, 1)
    out.append(svg.text(SX0 + 12, SY0 + 20, "CH1: CONTRIBUTIONS", theme.GREEN, 11))
    out.append(svg.text(SX0 + 12, SY0 + 36, f"V/DIV: {V_PER_DIV} commits", theme.GREEN, 11))
    out.append(svg.text(SX0 + 12, SY1 - 12, f"T/DIV: {365 // DIVS_X} days", theme.GREEN, 11))
    out.append(svg.text(SX1 - 12, SY0 + 20,
                        f"pk-pk: {peak} · mean: {mean:.2f} · {data['total']} samples",
                        theme.GREEN, 11, "end"))
    out.append(svg.text(SX1 - 12, SY1 - 12, "TRIG: RUN", theme.AMBER, 11, "end"))

    # right column: beam stats
    rx, ry = 680, 92
    streak = _streak(days)
    busy = sum(1 for d in days if d["count"] > 0)
    out.append(svg.text(rx, ry - 14, "BEAM", theme.DIM, 11))
    rows = [("samples", str(data["total"]), theme.FG),
            ("peak", str(peak), theme.FG),
            ("mean", f"{mean:.2f}/day", theme.FG),
            ("duty cycle", f"{busy * 100 // max(n, 1)}%", theme.FG),
            ("hold", f"{streak}d", theme.GREEN)]
    for i, (k, v, c) in enumerate(rows):
        out.append(svg.text(rx, ry + i * 22, f"{k:>10}", theme.DIM, 12))
        out.append(svg.text(rx + 84, ry + i * 22, v, c, 12))

    out.append(svg.text(SX0, 296,
                        "one sample per day over the rolling 365-day window — "
                        "idle days hold the beam on the baseline", theme.DIM, 11))
    out.append(svg.svg_close())
    return "".join(out)


def _streak(days):
    s = 0
    for d in reversed(days):
        if d["count"] > 0:
            s += 1
        else:
            break
    return s
