"""Render the capability vs price chart as a standalone SVG.

Primary chart: every scored model as a point, capability on x and output
price on a log y axis, coloured by weight class, with the frozen tier bands
shaded behind. Over the top, the price-performance frontier for each class:
for a given capability floor, the cheapest model that clears it.

This replaced a bar chart of median price by tier. The medians hid the thing
that matters. Buyers do not purchase the median model in a tier, they
purchase the cheapest one that clears their quality bar, and the cheapest
closed model in the mid tier is cheaper than most open models in it. A
median is the wrong statistic for a procurement question. The tier medians
are kept as a companion CSV beside the chart and in methodology.md.

Joins prices in data/scorecard/elasticity.csv to the classification in
data/model_classification.csv. Both are canonical CSVs, so this runs on a
fresh clone without building the database first.

Base SKUs only: ":batch" and ":free" are the same model at a discounted or
promotional price. Models without an intelligence index cannot be placed and
are excluded. Unclassified models are drawn but excluded from both frontier
lines.

Usage:
    python scripts/make_chart.py
    python scripts/make_chart.py --date 2026-10-30
"""

import argparse
import csv
import math
import os
import statistics
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project_config import load_identity, credit_line  # noqa: E402

PRICES = "data/scorecard/elasticity.csv"
CLASSES = "data/model_classification.csv"
CONFIG = "config/weight_classes.json"
OUT_DIR = "notes/charts"

OPEN, CLOSED, UNC = "open_weights", "closed_weights", "unclassified"
SERIES = [(OPEN, "Open weights", "#2a78d6"),
          (CLOSED, "Closed weights", "#eb6834"),
          (UNC, "Unclassified", "#1baf7a")]
COLOR = {k: c for k, _, c in SERIES}
LABEL = {k: l for k, l, _ in SERIES}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BAND = "#f1f0ea"

W, H = 980, 772
PAD_L, PAD_R, PAD_T = 78, 40, 132
PLOT_H = 340
X_MAX = 60.0
Y_MIN, Y_MAX = 0.1, 100.0
FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "'Helvetica Neue', Arial, sans-serif")

# Points to call out by name. Chosen as the ends of each frontier and the one
# known-suspect index, not as a sample of whatever looked interesting.
CALLOUTS = {
    "z-ai/glm-5.3-flash": ("cheapest above the mid floor", -1, -14),
    "anthropic/claude-haiku-5.5": ("cheapest closed, and cheaper than\n"
                                   "every open model above index 29", 1, -14),
    "z-ai/glm-5.3": ("best open model", -1, -13),
    "openai/gpt-6.1-terra": ("cheapest above the frontier floor", 1, -13),
    "moonshotai/kimi-k3": ("index likely stale", 1, -13),
}


def load(date=None):
    with open(CLASSES, newline="", encoding="utf-8") as fh:
        crows = list(csv.DictReader(fh))
    date = date or max(r["date"] for r in crows)
    cls = {r["model_id"]: r for r in crows if r["date"] == date}

    price = {}
    with open(PRICES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] == date and r["metric"].startswith("openrouter_price_"):
                price.setdefault(r["entity"], {})[
                    r["metric"].replace("openrouter_price_", "")] = float(r["value"])

    pts = []
    for mid, c in cls.items():
        if ":" in mid or not c["tier"]:
            continue
        p = price.get(mid)
        if not p or p["output"] <= 0:
            continue
        pts.append({"id": mid, "idx": float(c["intelligence_index"]),
                    "out": p["output"], "inp": p["input"],
                    "cls": c["weight_class"], "tier": c["tier"]})
    return date, pts


def frontier(pts, wcls, thresholds):
    """Cheapest model at or above each capability floor. Steps upward."""
    pool = [p for p in pts if p["cls"] == wcls]
    out = []
    for t in thresholds:
        elig = [p for p in pool if p["idx"] >= t]
        if not elig:
            break
        out.append((t, min(elig, key=lambda p: p["out"])))
    return out


def tier_medians(pts):
    rows = []
    for tier in ("frontier", "mid", "entry"):
        for wcls in (OPEN, CLOSED):
            sel = [p for p in pts if p["tier"] == tier and p["cls"] == wcls]
            if not sel:
                rows.append({"tier": tier, "weight_class": wcls, "n": 0,
                             "median_input": "", "median_output": ""})
                continue
            rows.append({
                "tier": tier, "weight_class": wcls, "n": len(sel),
                "median_input": round(statistics.median(
                    [p["inp"] for p in sel]), 4),
                "median_output": round(statistics.median(
                    [p["out"] for p in sel]), 4)})
    return rows


def render(date, pts, identity, bands):
    plot_w = W - PAD_L - PAD_R
    base_y = PAD_T + PLOT_H
    lx_ = lambda v: PAD_L + v / X_MAX * plot_w
    ly = lambda v: base_y - (math.log10(max(v, Y_MIN)) - math.log10(Y_MIN)) \
        / (math.log10(Y_MAX) - math.log10(Y_MIN)) * PLOT_H

    p = []
    a = p.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
      'viewBox="0 0 %d %d" role="img" aria-label="Capability against output '
      'token price by weight class with price-performance frontiers, %s">'
      % (W, H, W, H, date))
    a('<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE))
    a('<g font-family="%s">' % FONT)

    a('<text x="%d" y="42" font-size="21.5" font-weight="600" fill="%s">'
      'Open weights win on price only below the mid tier</text>'
      % (PAD_L, INK))
    a('<text x="%d" y="67" font-size="13.5" fill="%s">Each point is a model: '
      'measured capability against published output price. The lines trace '
      'the cheapest model of each kind</text>' % (PAD_L, INK_2))
    a('<text x="%d" y="86" font-size="13.5" fill="%s">that clears a given '
      'capability floor. OpenRouter catalogue and Artificial Analysis index, '
      '%s.</text>' % (PAD_L, INK_2, escape(date)))

    lgx = PAD_L
    for key, label, color in SERIES:
        a('<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (lgx + 5, 104, color))
        a('<text x="%d" y="%d" font-size="12.5" fill="%s">%s</text>'
          % (lgx + 16, 108, INK_2, label))
        lgx += 30 + len(label) * 7.2
    a('<line x1="%d" y1="104" x2="%d" y2="104" stroke="%s" stroke-width="2.5"/>'
      % (lgx + 2, lgx + 26, MUTED))
    a('<text x="%d" y="108" font-size="12.5" fill="%s">Cheapest at or above a '
      'capability floor</text>' % (lgx + 33, INK_2))

    # Tier bands behind everything in the plot.
    for i, b in enumerate(bands):
        x0, x1 = lx_(b["min"]), lx_(b.get("max", X_MAX))
        if i % 2 == 0:
            a('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"/>'
              % (x0, PAD_T, x1 - x0, PLOT_H, BAND))
        a('<text x="%.1f" y="%d" font-size="11.5" font-weight="500" '
          'fill="%s" text-anchor="middle">%s</text>'
          % ((x0 + x1) / 2, PAD_T - 10, MUTED, b["name"]))
        if b["min"] > 0:
            a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
              'stroke-width="1" stroke-dasharray="4 3"/>'
              % (x0, PAD_T, x0, base_y, AXIS))

    for dec in (0.1, 1, 10, 100):
        y = ly(dec)
        a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>'
          % (PAD_L, y, W - PAD_R, y, GRID))
        a('<text x="%d" y="%.1f" font-size="11.5" fill="%s" '
          'text-anchor="end">$%s</text>'
          % (PAD_L - 10, y + 4, MUTED,
             ("%g" % dec) if dec >= 1 else "0.10"))
        for m in range(2, 10):
            v = dec * m
            if Y_MIN < v <= Y_MAX:
                a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
                  'stroke-width="0.5" opacity="0.55"/>'
                  % (PAD_L, ly(v), W - PAD_R, ly(v), GRID))
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">USD per million output '
      'tokens, log scale</text>' % (PAD_L - 10, PAD_T - 28, MUTED))

    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5"/>'
      % (PAD_L, base_y, W - PAD_R, base_y, AXIS))
    for t in range(0, int(X_MAX) + 1, 10):
        a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>'
          % (lx_(t), base_y, lx_(t), base_y + 5, AXIS))
        a('<text x="%.1f" y="%d" font-size="11.5" fill="%s" '
          'text-anchor="middle">%d</text>' % (lx_(t), base_y + 19, MUTED, t))
    a('<text x="%.1f" y="%d" font-size="12.5" fill="%s" text-anchor="middle">'
      'Artificial Analysis intelligence index</text>'
      % (PAD_L + plot_w / 2, base_y + 40, INK_2))

    # Frontier step lines, drawn under the points.
    thresholds = sorted({p["idx"] for p in pts})
    for wcls in (OPEN, CLOSED):
        steps = frontier(pts, wcls, thresholds)
        if not steps:
            continue
        d = []
        for i, (t, best) in enumerate(steps):
            x, y = lx_(t), ly(best["out"])
            if i == 0:
                d.append("M%.1f %.1f" % (x, y))
            else:
                d.append("L%.1f %.1f" % (x, ly(steps[i - 1][1]["out"])))
                d.append("L%.1f %.1f" % (x, y))
        a('<path d="%s" fill="none" stroke="%s" stroke-width="2.5" '
          'stroke-linejoin="round" opacity="0.85"/>' % (" ".join(d), COLOR[wcls]))
        tx, tbest = steps[-1]
        a('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
          % (lx_(tx), ly(tbest["out"]), COLOR[wcls]))
        if wcls == OPEN:
            a('<text x="%.1f" y="%.1f" font-size="11.5" font-weight="600" '
              'fill="%s">no open model beyond %.1f</text>'
              % (lx_(tx) + 8, ly(tbest["out"]) + 4, COLOR[wcls], tx))

    for pt in sorted(pts, key=lambda q: -q["out"]):
        a('<circle cx="%.1f" cy="%.1f" r="5.5" fill="%s" stroke="%s" '
          'stroke-width="2"/>'
          % (lx_(pt["idx"]), ly(pt["out"]), COLOR[pt["cls"]], SURFACE))

    for pt in pts:
        if pt["id"] not in CALLOUTS:
            continue
        text, side, dy = CALLOUTS[pt["id"]]
        x, y = lx_(pt["idx"]), ly(pt["out"])
        anchor = "start" if side > 0 else "end"
        ox = 10 * side
        name = pt["id"].split("/", 1)[1]
        a('<text x="%.1f" y="%.1f" font-size="11.5" font-weight="600" '
          'fill="%s" text-anchor="%s">%s</text>'
          % (x + ox, y + dy, INK, anchor, escape(name)))
        for j, line in enumerate(text.split("\n")):
            a('<text x="%.1f" y="%.1f" font-size="11" fill="%s" '
              'text-anchor="%s">%s</text>'
              % (x + ox, y + dy + 13 + j * 12, MUTED, anchor, escape(line)))

    # Frontier table: the numbers the chart is making a claim about.
    ty = base_y + 76
    a('<text x="%d" y="%d" font-size="13" font-weight="600" fill="%s">'
      'Cheapest model clearing each capability floor</text>'
      % (PAD_L, ty - 22, INK))
    cols = [PAD_L, PAD_L + 150, PAD_L + 420, PAD_L + 700]
    for cx_, head in zip(cols, ["Capability floor", "Cheapest open weights",
                                "Cheapest closed weights", "Closed / open"]):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (cx_, ty, MUTED, head))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, ty + 7, W - PAD_R, ty + 7, GRID))
    row = ty + 27
    for floor, note in ((25.0, "mid floor"), (30.0, ""),
                        (45.0, "frontier floor")):
        o = frontier(pts, OPEN, [floor])
        c = frontier(pts, CLOSED, [floor])
        a('<text x="%d" y="%d" font-size="12" fill="%s">index %d%s</text>'
          % (cols[0], row, INK_2, int(floor),
             "  (%s)" % note if note else ""))
        for ci, res in ((1, o), (2, c)):
            if res:
                b = res[0][1]
                a('<text x="%d" y="%d" font-size="12" fill="%s">'
                  '%s   $%.2f</text>'
                  % (cols[ci], row, INK_2,
                     escape(b["id"].split("/", 1)[1]), b["out"]))
            else:
                a('<text x="%d" y="%d" font-size="12" fill="%s">none</text>'
                  % (cols[ci], row, MUTED))
        if o and c:
            ratio = c[0][1]["out"] / o[0][1]["out"]
            txt = ("%.1fx dearer" % ratio if ratio >= 1
                   else "%.1fx cheaper" % (1 / ratio))
        else:
            txt = "no open model"
        a('<text x="%d" y="%d" font-size="12" font-weight="600" fill="%s">'
          '%s</text>' % (cols[3], row, INK_2, txt))
        row += 21

    notes = [
        ("%d scored base SKUs; batch and free variants excluded. Models "
         "without an index cannot be placed and are not shown."
         % len(pts)),
        ("Capability is a third-party index that may lag recent releases. "
         "Price is output only; open weights hold a wider advantage on input "
         "price."),
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
    args = ap.parse_args()

    import json
    with open(CONFIG, encoding="utf-8") as fh:
        bands_cfg = json.load(fh)["tiers"]["bands"]
    bands = sorted([b for b in bands_cfg], key=lambda b: b["min"])
    for i, b in enumerate(bands):
        b["max"] = bands[i + 1]["min"] if i + 1 < len(bands) else X_MAX

    identity = load_identity()
    date, pts = load(args.date)

    os.makedirs(OUT_DIR, exist_ok=True)
    svg_path = os.path.join(OUT_DIR, "%s-capability-vs-price.svg" % date)
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(render(date, pts, identity, bands))

    med_path = os.path.join(OUT_DIR, "%s-tier-medians.csv" % date)
    rows = tier_medians(pts)
    with open(med_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["tier", "weight_class", "n",
                                           "median_input", "median_output"])
        w.writeheader()
        w.writerows(rows)

    print("date %s, %d scored base SKUs" % (date, len(pts)))
    print("\nprice-performance frontier (cheapest clearing each floor):")
    for floor in (25.0, 30.0, 45.0):
        print("  index >= %-4g" % floor)
        for wcls in (OPEN, CLOSED):
            res = frontier(pts, wcls, [floor])
            if res:
                b = res[0][1]
                print("    %-15s %-34s idx=%-5s $%.2f"
                      % (LABEL[wcls], b["id"], b["idx"], b["out"]))
            else:
                print("    %-15s none" % LABEL[wcls])
        o, c = frontier(pts, OPEN, [floor]), frontier(pts, CLOSED, [floor])
        if o and c:
            r = c[0][1]["out"] / o[0][1]["out"]
            print("    closed / open = %.2fx (%s)"
                  % (r, "closed dearer" if r >= 1 else "closed CHEAPER"))
    print("\ntier medians, retained as data:")
    for r in rows:
        print("  %-9s %-15s n=%-3s in=%-8s out=%s"
              % (r["tier"], r["weight_class"], r["n"],
                 r["median_input"], r["median_output"]))
    print("\nwrote %s\n      %s" % (svg_path, med_path))


if __name__ == "__main__":
    main()
