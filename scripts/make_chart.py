"""Render the token price chart as a standalone SVG.

Reads data/scorecard/elasticity.csv, which is the canonical record, so this
runs on a fresh clone without building the database first.

No plotting library. The output is a single SVG file: it diffs in git, it
scales without blurring, and it drops straight into Substack or X.

The footer credit comes from config/identity.json. Nothing about identity is
hardcoded here.

Usage:
    python scripts/make_chart.py
    python scripts/make_chart.py --date 2026-10-30
"""

import argparse
import csv
import datetime as dt
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project_config import load_identity, credit_line  # noqa: E402

SRC = "data/scorecard/elasticity.csv"
OUT_DIR = "notes/charts"

# Categorical slots 1 and 2 from the reference palette, in fixed order.
# Those first slots are the validated ones; do not substitute by eye.
SERIES = [
    ("openrouter_price_input", "Input", "#2a78d6"),
    ("openrouter_price_output", "Output", "#eb6834"),
]
GROUPS = [
    ("open_weights", "Open weights"),
    ("closed_weights", "Closed weights"),
    ("unclassified", "Unclassified"),
]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

W, H = 920, 540
PAD_L, PAD_R, PAD_T, PAD_B = 68, 32, 118, 104
FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "'Helvetica Neue', Arial, sans-serif")


def median(values):
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def load(date=None):
    if not os.path.exists(SRC):
        sys.exit("%s not found" % SRC)
    with open(SRC, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["metric"].startswith("openrouter_price_")]
    if not rows:
        sys.exit("no OpenRouter price rows in %s" % SRC)
    date = date or max(r["date"] for r in rows)
    rows = [r for r in rows if r["date"] == date]

    stats, counts = {}, {}
    for cls, _ in GROUPS:
        counts[cls] = len({r["entity"] for r in rows
                           if r["entity_class"] == cls})
        for metric, _, _ in SERIES:
            # Zero-priced promotional endpoints are excluded from the median.
            # They are real published prices and stay in the CSV, but they
            # describe a free tier rather than the cost of serving a model.
            vals = [float(r["value"]) for r in rows
                    if r["entity_class"] == cls and r["metric"] == metric
                    and float(r["value"]) > 0]
            stats[(cls, metric)] = median(vals)
    return date, stats, counts


def nice_max(v):
    """A round axis maximum just above v, leaving room for the bar labels.

    Kept tight on purpose. Rounding 6.5 up to 10 would throw away a third of
    the plot height, and the small bars in this data cannot spare it.
    """
    import math
    target = v * 1.12
    mag = 10 ** math.floor(math.log10(target))
    for mult in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        step = mult * mag
        if target <= step:
            return step
    return target


def fmt(v):
    if v is None:
        return "n/a"
    return ("%.2f" % v).rstrip("0").rstrip(".") if v < 10 else "%.0f" % v


def rounded_top_bar(x, y, w, h, r=4):
    """Bar with rounded data-end, square where it meets the baseline."""
    r = min(r, w / 2, h) if h > 0 else 0
    return ("M%g %g V%g Q%g %g %g %g H%g Q%g %g %g %g V%g Z"
            % (x, y + h, y + r, x, y, x + r, y, x + w - r,
               x + w, y, x + w, y + r, y + h))


def render(date, stats, counts, identity):
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    base_y = PAD_T + plot_h

    vmax = max(v for v in stats.values() if v is not None)
    axis_max = nice_max(vmax)
    scale = lambda v: v / axis_max * plot_h

    group_w = plot_w / len(GROUPS)
    bar_w = 58
    gap = 2  # 2px surface gap between adjacent fills

    p = []
    a = p.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
      'viewBox="0 0 %d %d" role="img" aria-label="Median published token '
      'price by weight class, %s">' % (W, H, W, H, date))
    a('<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE))
    a('<g font-family="%s">' % FONT)

    # Titles
    a('<text x="%d" y="40" font-size="21" font-weight="600" fill="%s">'
      'Open-weight models are priced far below closed</text>' % (PAD_L, INK))
    a('<text x="%d" y="65" font-size="13.5" fill="%s">Median published price '
      'per million tokens, OpenRouter catalogue, %s</text>'
      % (PAD_L, INK_2, escape(date)))

    # Legend
    lx = PAD_L
    for _, label, color in SERIES:
        a('<rect x="%d" y="82" width="11" height="11" rx="2.5" fill="%s"/>'
          % (lx, color))
        a('<text x="%d" y="92" font-size="12.5" fill="%s">%s</text>'
          % (lx + 17, INK_2, label))
        lx += 24 + len(label) * 7.6

    # Gridlines and y axis
    ticks = 4
    for i in range(ticks + 1):
        val = axis_max * i / ticks
        y = base_y - scale(val)
        if i:
            a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
              'stroke-width="1"/>' % (PAD_L, y, W - PAD_R, y, GRID))
        a('<text x="%d" y="%.1f" font-size="11.5" fill="%s" '
          'text-anchor="end">%s</text>' % (PAD_L - 11, y + 4, MUTED, fmt(val)))
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">USD per million tokens'
      '</text>' % (PAD_L - 11, PAD_T - 14, MUTED))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5"/>'
      % (PAD_L, base_y, W - PAD_R, base_y, AXIS))

    # Bars
    for gi, (cls, glabel) in enumerate(GROUPS):
        cx = PAD_L + group_w * (gi + 0.5)
        total_w = bar_w * len(SERIES) + gap
        x0 = cx - total_w / 2
        for si, (metric, _, color) in enumerate(SERIES):
            v = stats[(cls, metric)]
            x = x0 + si * (bar_w + gap)
            if v is None:
                a('<text x="%.1f" y="%d" font-size="12" fill="%s" '
                  'text-anchor="middle">n/a</text>'
                  % (x + bar_w / 2, base_y - 8, MUTED))
                continue
            h = scale(v)
            a('<path d="%s" fill="%s"/>'
              % (rounded_top_bar(x, base_y - h, bar_w, h), color))
            # Direct label on every bar: the relief rule, and the small bars
            # are unreadable without it.
            a('<text x="%.1f" y="%.1f" font-size="12.5" font-weight="600" '
              'fill="%s" text-anchor="middle">%s</text>'
              % (x + bar_w / 2, base_y - h - 8, INK, fmt(v)))
        a('<text x="%.1f" y="%d" font-size="13" font-weight="500" fill="%s" '
          'text-anchor="middle">%s</text>'
          % (cx, base_y + 24, INK, escape(glabel)))
        a('<text x="%.1f" y="%d" font-size="11.5" fill="%s" '
          'text-anchor="middle">%d models</text>'
          % (cx, base_y + 41, MUTED, counts[cls]))

    # Caveat and footer
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">Weights classified by '
      'rule, not by hand. Unclassified models are flagged rather than guessed, '
      'so open weights is a floor and not a count.</text>'
      % (PAD_L, H - 46, MUTED))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
      % (PAD_L, H - 34, W - PAD_R, H - 34, GRID))
    a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
      % (PAD_L, H - 15, INK_2, escape(credit_line(identity))))
    a('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">'
      'Source: OpenRouter models API</text>' % (W - PAD_R, H - 15, MUTED))
    a('</g></svg>')
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    identity = load_identity()
    date, stats, counts = load(args.date)
    svg = render(date, stats, counts, identity)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = args.out or os.path.join(
        OUT_DIR, "%s-token-price-by-weight-class.svg" % date)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)

    print("date        %s" % date)
    for cls, label in GROUPS:
        print("  %-16s %2d models   input %-7s output %s"
              % (label, counts[cls],
                 fmt(stats[(cls, "openrouter_price_input")]),
                 fmt(stats[(cls, "openrouter_price_output")])))
    print("footer      %s" % credit_line(identity))
    print("wrote       %s" % out)


if __name__ == "__main__":
    main()
