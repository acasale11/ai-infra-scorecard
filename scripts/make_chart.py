"""Render the capability-tier price chart as a standalone SVG.

Joins prices in data/scorecard/elasticity.csv to the classification in
data/model_classification.csv. Both are canonical CSVs, so this runs on a
fresh clone without building the database first.

The join is deliberate. elasticity.csv keeps the classification that was in
force when each row was collected and is never rewritten; the classification
table is the current, revisable view. Charts read the current view.

No plotting library. The output is one SVG: it diffs in git, scales without
blurring, and drops straight into Substack or X.

Comparison rules, so the chart is like for like:

  - Base SKUs only. ":batch" and ":free" are the same model at a discounted
    or promotional price and would double count.
  - Only models carrying an intelligence_index, since a tier cannot be
    assigned without one.
  - Unclassified models are excluded from the bars and reported separately.
    They are not folded into either side.

Usage:
    python scripts/make_chart.py
    python scripts/make_chart.py --date 2026-10-30
"""

import argparse
import csv
import os
import statistics
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project_config import load_identity, credit_line  # noqa: E402

PRICES = "data/scorecard/elasticity.csv"
CLASSES = "data/model_classification.csv"
OUT_DIR = "notes/charts"

TIERS = [("frontier", "Frontier"), ("mid", "Mid"), ("entry", "Entry")]
SERIES = [("open_weights", "Open weights", "#2a78d6"),
          ("closed_weights", "Closed weights", "#eb6834")]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

W, H = 940, 648
PAD_L, PAD_R, PAD_T = 70, 34, 126
PLOT_H = 288
FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "'Helvetica Neue', Arial, sans-serif")


def load(date=None):
    if not (os.path.exists(PRICES) and os.path.exists(CLASSES)):
        sys.exit("need both %s and %s" % (PRICES, CLASSES))

    with open(CLASSES, newline="", encoding="utf-8") as fh:
        crows = list(csv.DictReader(fh))
    date = date or max(r["date"] for r in crows)
    cls = {r["model_id"]: r for r in crows if r["date"] == date}

    price = {}
    with open(PRICES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] != date or not r["metric"].startswith(
                    "openrouter_price_"):
                continue
            price.setdefault(r["entity"], {})[
                r["metric"].replace("openrouter_price_", "")] = float(r["value"])

    buckets, skipped = {}, {"unclassified": 0, "no_tier": 0}
    for mid, c in cls.items():
        if ":" in mid:
            continue
        if not c["tier"]:
            skipped["no_tier"] += 1
            continue
        if c["weight_class"] == "unclassified":
            skipped["unclassified"] += 1
            continue
        p = price.get(mid)
        if not p:
            continue
        b = buckets.setdefault((c["tier"], c["weight_class"]),
                               {"input": [], "output": []})
        b["input"].append(p["input"])
        b["output"].append(p["output"])

    stats = {}
    for k, v in buckets.items():
        stats[k] = {"n": len(v["output"]),
                    "input": statistics.median(v["input"]),
                    "output": statistics.median(v["output"])}
    return date, stats, skipped


def nice_max(v):
    import math
    target = v * 1.14
    mag = 10 ** math.floor(math.log10(target))
    for mult in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if target <= mult * mag:
            return mult * mag
    return target


def fmt(v):
    if v is None:
        return "n/a"
    return ("%.2f" % v).rstrip("0").rstrip(".") if v < 10 else "%.0f" % v


def bar_path(x, y, w, h, r=4):
    r = min(r, w / 2, h) if h > 0 else 0
    return ("M%g %g V%g Q%g %g %g %g H%g Q%g %g %g %g V%g Z"
            % (x, y + h, y + r, x, y, x + r, y, x + w - r,
               x + w, y, x + w, y + r, y + h))


def render(date, stats, skipped, identity):
    plot_w = W - PAD_L - PAD_R
    base_y = PAD_T + PLOT_H
    vmax = max(s["output"] for s in stats.values())
    axis_max = nice_max(vmax)

    p = []
    a = p.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
      'viewBox="0 0 %d %d" role="img" aria-label="Median output token price '
      'by capability tier and weight class, %s">' % (W, H, W, H, date))
    a('<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE))
    a('<g font-family="%s">' % FONT)

    a('<text x="%d" y="42" font-size="21.5" font-weight="600" fill="%s">'
      'Open weights are cheaper, and absent from the frontier</text>'
      % (PAD_L, INK))
    a('<text x="%d" y="67" font-size="13.5" fill="%s">Median published price '
      'per million output tokens, by capability tier. OpenRouter catalogue, '
      '%s.</text>' % (PAD_L, INK_2, escape(date)))
    a('<text x="%d" y="86" font-size="13.5" fill="%s">Tiers come from the '
      'Artificial Analysis intelligence index, not from price.</text>'
      % (PAD_L, INK_2))

    lx = PAD_L
    for _, label, color in SERIES:
        a('<rect x="%d" y="100" width="11" height="11" rx="2.5" fill="%s"/>'
          % (lx, color))
        a('<text x="%d" y="110" font-size="12.5" fill="%s">%s</text>'
          % (lx + 17, INK_2, label))
        lx += 26 + len(label) * 7.4

    for i in range(5):
        val = axis_max * i / 4
        y = base_y - val / axis_max * PLOT_H
        if i:
            a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
              'stroke-width="1"/>' % (PAD_L, y, W - PAD_R, y, GRID))
        a('<text x="%d" y="%.1f" font-size="11.5" fill="%s" '
          'text-anchor="end">%s</text>' % (PAD_L - 11, y + 4, MUTED, fmt(val)))
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">USD per million output '
      'tokens</text>' % (PAD_L - 11, PAD_T - 16, MUTED))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5"/>'
      % (PAD_L, base_y, W - PAD_R, base_y, AXIS))

    group_w = plot_w / len(TIERS)
    bar_w = 72
    gap = 2
    for gi, (tier, tlabel) in enumerate(TIERS):
        cx = PAD_L + group_w * (gi + 0.5)
        x0 = cx - (bar_w * len(SERIES) + gap) / 2
        for si, (wcls, _, color) in enumerate(SERIES):
            s = stats.get((tier, wcls))
            x = x0 + si * (bar_w + gap)
            if not s:
                a('<rect x="%.1f" y="%d" width="%d" height="%d" fill="none" '
                  'stroke="%s" stroke-width="1" stroke-dasharray="3 3" '
                  'rx="4"/>' % (x, base_y - 54, bar_w, 54, AXIS))
                a('<text x="%.1f" y="%d" font-size="12" font-weight="600" '
                  'fill="%s" text-anchor="middle">none</text>'
                  % (x + bar_w / 2, base_y - 30, MUTED))
                a('<text x="%.1f" y="%d" font-size="11" fill="%s" '
                  'text-anchor="middle">n = 0</text>'
                  % (x + bar_w / 2, base_y - 14, MUTED))
                continue
            h = s["output"] / axis_max * PLOT_H
            a('<path d="%s" fill="%s"/>'
              % (bar_path(x, base_y - h, bar_w, h), color))
            a('<text x="%.1f" y="%.1f" font-size="13" font-weight="600" '
              'fill="%s" text-anchor="middle">%s</text>'
              % (x + bar_w / 2, base_y - h - 9, INK, fmt(s["output"])))
            a('<text x="%.1f" y="%d" font-size="11" fill="%s" '
              'text-anchor="middle">n = %d</text>'
              % (x + bar_w / 2, base_y + 19, MUTED, s["n"]))
        a('<text x="%.1f" y="%d" font-size="14" font-weight="500" fill="%s" '
          'text-anchor="middle">%s</text>' % (cx, base_y + 40, INK, tlabel))

    # Table: the input prices the bars do not show, plus the counts.
    ty = base_y + 76
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, ty - 18, W - PAD_R, ty - 18, GRID))
    cols = [PAD_L, PAD_L + 210, PAD_L + 330, PAD_L + 460, PAD_L + 590]
    for cx_, head in zip(cols, ["", "Models", "Median input",
                                "Median output", "Closed / open, output"]):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (cx_, ty, MUTED, head))
    row = ty + 20
    for tier, tlabel in TIERS:
        o, c = stats.get((tier, "open_weights")), stats.get(
            (tier, "closed_weights"))
        for wcls, label, color in SERIES:
            s = stats.get((tier, wcls))
            a('<rect x="%d" y="%d" width="9" height="9" rx="2" fill="%s"/>'
              % (cols[0], row - 9, color))
            a('<text x="%d" y="%d" font-size="12" fill="%s">%s %s</text>'
              % (cols[0] + 15, row, INK_2, escape(tlabel), escape(label.lower())))
            a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
              % (cols[1], row, INK_2, s["n"] if s else 0))
            a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
              % (cols[2], row, INK_2, fmt(s["input"]) if s else "n/a"))
            a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
              % (cols[3], row, INK_2, fmt(s["output"]) if s else "n/a"))
            if wcls == "closed_weights":
                ratio = ("%.1fx" % (c["output"] / o["output"])
                         if o and c else "no open model")
                a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
                  % (cols[4], row, INK_2, ratio))
            row += 19
        row += 5

    notes = [
        ("Base SKUs only; batch and free variants excluded. %d classified "
         "models carry an index. A further %d are unclassified and are in "
         "neither bar." % (sum(s["n"] for s in stats.values()),
                           skipped["unclassified"])),
        ("Samples are small, so read the counts. Compare open against closed "
         "within a tier, not one tier against another: price tracks serving "
         "cost, not capability."),
    ]
    for i, note in enumerate(notes):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (PAD_L, H - 64 + i * 16, MUTED, escape(note)))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, H - 34, W - PAD_R, H - 34, GRID))
    a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
      % (PAD_L, H - 15, INK_2, escape(credit_line(identity))))
    a('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">'
      'Sources: OpenRouter models API, Artificial Analysis</text>'
      % (W - PAD_R, H - 15, MUTED))
    a('</g></svg>')
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    identity = load_identity()
    date, stats, skipped = load(args.date)
    svg = render(date, stats, skipped, identity)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = args.out or os.path.join(
        OUT_DIR, "%s-token-price-by-tier.svg" % date)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)

    print("date %s" % date)
    print("%-9s %-15s %3s %9s %9s" % ("tier", "class", "n", "med in", "med out"))
    for tier, _ in TIERS:
        for wcls, _, _ in SERIES:
            s = stats.get((tier, wcls))
            print("%-9s %-15s %3d %9s %9s"
                  % (tier, wcls, s["n"] if s else 0,
                     fmt(s["input"]) if s else "-",
                     fmt(s["output"]) if s else "-"))
    print("\nexcluded: %d unclassified, %d without an index"
          % (skipped["unclassified"], skipped["no_tier"]))
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
