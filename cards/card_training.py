"""Training log — the contribution year as a training run.

Loss is honest: the fraction of the year's total contributions still owed at
each week boundary. Commit and the curve converges; go dark and it plateaus.
"""
from . import svg, theme

W, H = 920, 330
PLOT_X0, PLOT_X1 = 50, 610
PLOT_Y0, PLOT_Y1 = 78, 248          # top, baseline of the plot


def render(data):
    total = max(data["total"], 1)
    days = data["days"][-364:]          # exactly 52 full weeks
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    cum = 0
    points = []
    for i, wk in enumerate(weeks):
        cum += sum(d["count"] for d in wk)
        loss = 1.0 - cum / total
        x = PLOT_X0 + (PLOT_X1 - PLOT_X0) * i / max(len(weeks) - 1, 1)
        y = PLOT_Y0 + (PLOT_Y1 - PLOT_Y0) * (1.0 - loss)
        points.append((x, y))

    cmd = "$ python train_contributor.py --epochs=52 --optimizer=streak"
    out = [svg.svg_open(W, H, "Training log: a year of contributions as a "
                              "converging loss curve"),
           svg.panel(10, 10, W - 20, H - 20),
           svg.bar(10, 10, W - 20, "train_contributor.py"),
           svg.text(30, 62, cmd, theme.GREEN, 13),
           svg.cursor(30 + svg.text_w(cmd, 13) + 6, 50)]

    # gridlines + loss axis
    for frac, label in ((0.0, "1.00"), (0.25, "0.75"), (0.5, "0.50"),
                        (0.75, "0.25"), (1.0, "0.00")):
        y = PLOT_Y0 + (PLOT_Y1 - PLOT_Y0) * frac
        out.append(svg.line(PLOT_X0, y, PLOT_X1, y, theme.BORDER,
                            1, dash="4 4"))
        out.append(svg.text(PLOT_X0 - 8, y + 4, label, theme.DIM, 10, "end"))
    out.append(svg.text(PLOT_X0 - 8, PLOT_Y0 + 4, "loss", theme.DIM, 10, "end"))
    for i in (0, 13, 26, 39, 51):
        x = PLOT_X0 + (PLOT_X1 - PLOT_X0) * i / 52
        out.append(svg.line(x, PLOT_Y0, x, PLOT_Y1, theme.BORDER, 1, dash="2 6"))
        out.append(svg.text(x, PLOT_Y1 + 16, f"e{i + 1}", theme.DIM, 10, "middle"))

    # loss curve: glow underlay + crisp core
    out.append(svg.polyline(points, theme.GREEN, 6, opacity=0.22))
    # the loss curve draws itself in once, then holds (dash offset trick —
    # 2000px is longer than the path will ever be)
    pts_s = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    out.append(f'<polyline fill="none" stroke="{theme.GREEN}" '
                f'stroke-width="1.6" points="{pts_s}" stroke-dasharray="2000" '
                f'stroke-dashoffset="2000"><animate '
                f'attributeName="stroke-dashoffset" values="2000;0" '
                f'dur="2.2s" fill="freeze"/></polyline>\n')
    # last point marker — heartbeates while status is converging
    lx, ly = points[-1]
    out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" '
               f'fill="{theme.GREEN}"><animate attributeName="r" '
               f'values="3.5;6;3.5" dur="2.4s" repeatCount="indefinite"/>'
               f'<animate attributeName="opacity" values="1;0.35;1" '
               f'dur="2.4s" repeatCount="indefinite"/></circle>\n')

    # right-hand log column
    log_x, log_y = 648, 92
    final_loss = points[-1][1]
    loss_val = 1.0 - (final_loss - PLOT_Y0) / (PLOT_Y1 - PLOT_Y0)
    streak = _current_streak(data["days"])
    lines = [
        ("epoch", f"{len(weeks)}/52", theme.FG),
        ("loss", f"{loss_val:.4f}", theme.GREEN),
        ("val_loss(streak)", f"{streak}d", theme.FG),
        ("optimizer", "streak", theme.DIM),
        ("checkpoint", "github.com/" + data["login"], theme.CYAN),
        ("status", "converging" if streak > 0 else "resuming", theme.AMBER),
    ]
    out.append(svg.text(log_x, log_y - 14, "TRAINING LOG", theme.DIM, 11))
    for i, (k, v, c) in enumerate(lines):
        y = log_y + i * 24
        out.append(svg.text(log_x, y, f"{k:>15}", theme.DIM, 11))
        out.append(svg.text(log_x + 112, y, v, c, 11))

    out.append(svg.text(
        PLOT_X0, 292,
        f"loss = share of the year's {data['total']} contributions still owed "
        f"— commits drive it to zero", theme.DIM, 11))
    out.append(svg.text(PLOT_X0, 310, "no third-party badge APIs: rendered from "
        "the live GitHub GraphQL API and committed by cards.yml",
        theme.DIM, 10, opacity="0.75"))
    out.append(svg.svg_close())
    return "".join(out)


def _current_streak(days):
    streak = 0
    for d in reversed(days):
        if d["count"] > 0:
            streak += 1
        else:
            break
    return streak
