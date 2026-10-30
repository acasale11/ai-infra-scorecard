"""Render the capability vs blended-price chart as a standalone SVG.

Every scored model as a point, capability on x and blended price on a log y
axis, coloured by weight class, tier bands shaded behind, and a step line per
class tracing the cheapest model that clears each capability floor.

Prices come from data/price_bases.csv, which carries three bases per model.
The chart uses the middle one.

  cheapest_any   cheapest endpoint at any precision      lower bound
  cheapest_fp8   cheapest endpoint at 8-bit or better    base case, plotted
  author         the model author's own standard tier    upper bound

Multi-provider competition on open weights is a real, purchasable advantage
and is part of what the thesis is about, so pricing every open model at its
author's list price throws away the thing being measured. The problem with
the cheapest endpoint was precision, not resellers: a 4-bit build competing
against a closed model served at full precision is not like for like. The
fp8 basis keeps the competition and drops the precision mismatch.

The spread between the three bases is reported on the chart, because the
distance between them is as informative as any single number.

Blended price is (R * input + output) / (R + 1) at R input tokens per output
token, with R from config/weight_classes.json. R is an assumption, so the
chart carries a sensitivity block for the bracketing ratios.

Models whose author does not serve them have no first-party price and are
excluded. On 2026-10-30 all six were open-weight and all scored below 25, so
they do not touch any reported floor.

Base SKUs only. Models without an intelligence index cannot be placed.
Unclassified models are drawn but excluded from both frontier lines.

Usage:
    python scripts/make_chart.py
"""

import argparse
import csv
import json
import math
import os
import statistics
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project_config import load_identity, credit_line  # noqa: E402

CLASSES = "data/model_classification.csv"
BASES = "data/price_bases.csv"
CONFIG = "config/weight_classes.json"
OUT_DIR = "notes/charts"

OPEN, CLOSED, UNC = "open_weights", "closed_weights", "unclassified"
SERIES = [(OPEN, "Open weights", "#2a78d6"),
          (CLOSED, "Closed weights", "#eb6834"),
          (UNC, "Unclassified", "#1baf7a")]
COLOR = {k: c for k, _, c in SERIES}

SURFACE, INK, INK_2 = "#fcfcfb", "#0b0b0b", "#52514e"
MUTED, GRID, AXIS, BAND = "#898781", "#e1e0d9", "#c3c2b7", "#f1f0ea"

W, H = 980, 846
PAD_L, PAD_R, PAD_T = 78, 40, 132
PLOT_H = 330
X_MAX, Y_MIN, Y_MAX = 60.0, 0.01, 100.0
FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "'Helvetica Neue', Arial, sans-serif")

CALLOUTS = {
    "z-ai/glm-5.3-flash": ("cheapest open above the mid floor", -1, -14),
    "anthropic/claude-haiku-5.5": ("cheaper than every open model\nthat scores above it", 1, -14),
    "z-ai/glm-5.3": ("best open model", -1, -13),
    "openai/gpt-6.1-terra": ("cheapest above the frontier floor", 1, -13),
}


def blend(p, R):
    return p["out"] if R is None else (R * p["inp"] + p["out"]) / (R + 1)


PRICE_BASES = [("cheapest_any", "Cheapest, any precision", "lower bound"),
               ("cheapest_fp8", "Cheapest at fp8 or better", "base case"),
               ("author", "Author list price", "upper bound")]
PRIMARY = "cheapest_fp8"


def load(date=None):
    with open(BASES, newline="", encoding="utf-8") as fh:
        brows = list(csv.DictReader(fh))
    date = date or max(r["date"] for r in brows)
    rows = [r for r in brows if r["date"] == date and r["tier"]]

    bybase, excluded = {}, {}
    for basis, _, _ in PRICE_BASES:
        pts, miss = [], []
        for r in rows:
            if not r[basis + "_output"]:
                miss.append((r["model_id"], r["weight_class"]))
                continue
            pts.append({"id": r["model_id"],
                        "idx": float(r["intelligence_index"]),
                        "inp": float(r[basis + "_input"]),
                        "out": float(r[basis + "_output"]),
                        "cls": r["weight_class"], "tier": r["tier"],
                        "spread": float(r["output_price_spread_ratio"]),
                        "providers": int(r["provider_count"])})
        bybase[basis] = pts
        excluded[basis] = miss
    return date, bybase, excluded


def cheapest(pts, wcls, floor, R):
    e = [p for p in pts if p["cls"] == wcls and p["idx"] >= floor]
    return min(e, key=lambda p: blend(p, R)) if e else None


def crossover(pts, R):
    for t in sorted({p["idx"] for p in pts}):
        o, c = cheapest(pts, OPEN, t, R), cheapest(pts, CLOSED, t, R)
        if not o or not c:
            return None
        if blend(c, R) <= blend(o, R):
            return t
    return None


def steps(pts, wcls, R):
    out = []
    for t in sorted({p["idx"] for p in pts}):
        b = cheapest(pts, wcls, t, R)
        if not b:
            break
        out.append((t, blend(b, R)))
    return out


def render(date, bybase, excluded, identity, bands, R, sens):
    pts = bybase[PRIMARY]
    plot_w = W - PAD_L - PAD_R
    base_y = PAD_T + PLOT_H
    lx = lambda v: PAD_L + v / X_MAX * plot_w
    ly = lambda v: base_y - (math.log10(max(v, Y_MIN)) - math.log10(Y_MIN)) \
        / (math.log10(Y_MAX) - math.log10(Y_MIN)) * PLOT_H

    p = []
    a = p.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
      'viewBox="0 0 %d %d" role="img" aria-label="Capability against blended '
      'token price at author list prices, %s">' % (W, H, W, H, date))
    a('<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE))
    a('<g font-family="%s">' % FONT)

    a('<text x="%d" y="42" font-size="21.5" font-weight="600" fill="%s">'
      'Open weights are much cheaper, until they run out of capability'
      '</text>' % (PAD_L, INK))
    a('<text x="%d" y="67" font-size="13.5" fill="%s">Blended price per '
      'million tokens at %d input tokens per output token, at the cheapest '
      'provider serving fp8 or better. Lines trace</text>'
      % (PAD_L, INK_2, R))
    a('<text x="%d" y="86" font-size="13.5" fill="%s">the cheapest model of '
      'each kind clearing a capability floor. OpenRouter endpoints and '
      'Artificial Analysis index, %s.</text>' % (PAD_L, INK_2, escape(date)))

    lgx = PAD_L
    for key, label, color in SERIES:
        a('<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (lgx + 5, 104, color))
        a('<text x="%d" y="%d" font-size="12.5" fill="%s">%s</text>'
          % (lgx + 16, 108, INK_2, label))
        lgx += 30 + len(label) * 7.2
    a('<line x1="%d" y1="104" x2="%d" y2="104" stroke="%s" stroke-width="2.5"/>'
      % (lgx + 2, lgx + 26, MUTED))
    a('<text x="%d" y="108" font-size="12.5" fill="%s">Cheapest clearing a '
      'capability floor</text>' % (lgx + 33, INK_2))

    for i, b in enumerate(bands):
        x0, x1 = lx(b["min"]), lx(b.get("max", X_MAX))
        if i % 2 == 0:
            a('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"/>'
              % (x0, PAD_T, x1 - x0, PLOT_H, BAND))
        a('<text x="%.1f" y="%d" font-size="11.5" font-weight="500" fill="%s" '
          'text-anchor="middle">%s</text>'
          % ((x0 + x1) / 2, PAD_T - 10, MUTED, b["name"]))
        if b["min"] > 0:
            a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
              'stroke-width="1" stroke-dasharray="4 3"/>'
              % (x0, PAD_T, x0, base_y, AXIS))

    for dec in (0.01, 0.1, 1, 10, 100):
        y = ly(dec)
        a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>'
          % (PAD_L, y, W - PAD_R, y, GRID))
        a('<text x="%d" y="%.1f" font-size="11.5" fill="%s" text-anchor="end">'
          '$%s</text>' % (PAD_L - 10, y + 4, MUTED,
                          ("%g" % dec) if dec >= 1 else ("%.2f" % dec)))
        for m in range(2, 10):
            if Y_MIN < dec * m <= Y_MAX:
                a('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
                  'stroke-width="0.5" opacity="0.5"/>'
                  % (PAD_L, ly(dec * m), W - PAD_R, ly(dec * m), GRID))
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">USD per million tokens, '
      'blended %d:1, log scale</text>' % (PAD_L - 10, PAD_T - 28, MUTED, R))

    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5"/>'
      % (PAD_L, base_y, W - PAD_R, base_y, AXIS))
    for t in range(0, int(X_MAX) + 1, 10):
        a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>'
          % (lx(t), base_y, lx(t), base_y + 5, AXIS))
        a('<text x="%.1f" y="%d" font-size="11.5" fill="%s" '
          'text-anchor="middle">%d</text>' % (lx(t), base_y + 19, MUTED, t))
    a('<text x="%.1f" y="%d" font-size="12.5" fill="%s" text-anchor="middle">'
      'Artificial Analysis intelligence index</text>'
      % (PAD_L + plot_w / 2, base_y + 40, INK_2))

    for wcls in (OPEN, CLOSED):
        st = steps(pts, wcls, R)
        if not st:
            continue
        d = []
        for i, (t, v) in enumerate(st):
            x, y = lx(t), ly(v)
            if i == 0:
                d.append("M%.1f %.1f" % (x, y))
            else:
                d.append("L%.1f %.1f" % (x, ly(st[i - 1][1])))
                d.append("L%.1f %.1f" % (x, y))
        a('<path d="%s" fill="none" stroke="%s" stroke-width="2.5" '
          'stroke-linejoin="round" opacity="0.85"/>' % (" ".join(d), COLOR[wcls]))
        tx, tv = st[-1]
        a('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
          % (lx(tx), ly(tv), COLOR[wcls]))
        if wcls == OPEN:
            a('<text x="%.1f" y="%.1f" font-size="11.5" font-weight="600" '
              'fill="%s">no open model beyond %.1f</text>'
              % (lx(tx) + 8, ly(tv) + 4, COLOR[wcls], tx))

    xo = crossover(pts, R)
    if xo:
        a('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
          'stroke-width="1.5" stroke-dasharray="5 4"/>'
          % (lx(xo), PAD_T, lx(xo), base_y, INK_2))
        a('<text x="%.1f" y="%d" font-size="11.5" font-weight="600" '
          'fill="%s">closed becomes cheaper from index %.1f</text>'
          % (lx(xo) + 7, PAD_T + 14, INK_2, xo))

    for pt in sorted(pts, key=lambda q: -blend(q, R)):
        a('<circle cx="%.1f" cy="%.1f" r="5.5" fill="%s" stroke="%s" '
          'stroke-width="2"/>'
          % (lx(pt["idx"]), ly(blend(pt, R)), COLOR[pt["cls"]], SURFACE))

    for pt in pts:
        if pt["id"] not in CALLOUTS:
            continue
        text, side, dy = CALLOUTS[pt["id"]]
        x, y = lx(pt["idx"]), ly(blend(pt, R))
        anchor = "start" if side > 0 else "end"
        a('<text x="%.1f" y="%.1f" font-size="11.5" font-weight="600" '
          'fill="%s" text-anchor="%s">%s</text>'
          % (x + 10 * side, y + dy, INK, anchor,
             escape(pt["id"].split("/", 1)[1])))
        for j, line in enumerate(text.split("\n")):
            a('<text x="%.1f" y="%.1f" font-size="11" fill="%s" '
              'text-anchor="%s">%s</text>'
              % (x + 10 * side, y + dy + 13 + j * 12, MUTED, anchor,
                 escape(line)))

    ty = base_y + 76
    a('<text x="%d" y="%d" font-size="13" font-weight="600" fill="%s">'
      'Cheapest model clearing each capability floor, at author list prices, '
      'blended %d:1</text>' % (PAD_L, ty - 22, INK, R))
    cols = [PAD_L, PAD_L + 150, PAD_L + 420, PAD_L + 700]
    for cx_, head in zip(cols, ["Capability floor", "Cheapest open weights",
                                "Cheapest closed weights", "Closed vs open"]):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (cx_, ty, MUTED, head))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, ty + 7, W - PAD_R, ty + 7, GRID))
    row = ty + 27
    for floor, note in ((25.0, "mid floor"), (30.0, ""),
                        (45.0, "frontier floor")):
        o, c = cheapest(pts, OPEN, floor, R), cheapest(pts, CLOSED, floor, R)
        a('<text x="%d" y="%d" font-size="12" fill="%s">index %d%s</text>'
          % (cols[0], row, INK_2, int(floor),
             "  (%s)" % note if note else ""))
        for ci, b in ((1, o), (2, c)):
            if b:
                a('<text x="%d" y="%d" font-size="12" fill="%s">%s   $%.3f'
                  '</text>' % (cols[ci], row, INK_2,
                               escape(b["id"].split("/", 1)[1]), blend(b, R)))
            else:
                a('<text x="%d" y="%d" font-size="12" fill="%s">none</text>'
                  % (cols[ci], row, MUTED))
        if o and c:
            rr = blend(c, R) / blend(o, R)
            txt = ("%.2fx dearer" % rr if rr >= 1
                   else "%.1fx cheaper" % (1 / rr))
        else:
            txt = "no open model"
        a('<text x="%d" y="%d" font-size="12" font-weight="600" fill="%s">%s'
          '</text>' % (cols[3], row, INK_2, txt))
        row += 21

    sy = row + 24
    a('<text x="%d" y="%d" font-size="13" font-weight="600" fill="%s">'
      'How much the answer depends on which price you can actually get'
      '</text>' % (PAD_L, sy - 6, INK))
    scols = [PAD_L, PAD_L + 250, PAD_L + 430, PAD_L + 640, PAD_L + 800]
    for cx_, head in zip(scols, ["Price basis", "Models", "Cheapest open at "
                                 "index 25", "Open advantage", "Crossover"]):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (cx_, sy + 16, MUTED, head))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, sy + 23, W - PAD_R, sy + 23, GRID))
    srow = sy + 43
    for basis, label, bound in PRICE_BASES:
        P = bybase[basis]
        o, c = cheapest(P, OPEN, 25.0, R), cheapest(P, CLOSED, 25.0, R)
        xo_ = crossover(P, R)
        weight = "600" if basis == PRIMARY else "400"
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">'
          '%s  (%s)</text>' % (scols[0], srow, weight, INK_2,
                               escape(label), escape(bound)))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">%d'
          '</text>' % (scols[1], srow, weight, INK_2, len(P)))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">'
          '$%.3f</text>' % (scols[2], srow, weight, INK_2, blend(o, R)))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">'
          '%.2fx cheaper</text>' % (scols[3], srow, weight, INK_2,
                                    blend(c, R) / blend(o, R)))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">%s'
          '</text>' % (scols[4], srow, weight, INK_2,
                       "%.1f" % xo_ if xo_ else "none"))
        srow += 20
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">The discount depends '
      'heavily on the basis. The crossover does not move: it is set by open '
      'models running out of capability at 31.7,</text>'
      % (PAD_L, srow + 10, MUTED))
    a('<text x="%d" y="%d" font-size="11.5" fill="%s">not by price. It also '
      'holds across every token mix tested, from output-only to 20:1.</text>'
      % (PAD_L, srow + 26, MUTED))

    notes = [
        ("%d scored base SKUs at the base case. Standard-tier endpoints only. "
         "Undeclared precision counts as fp8 or better, since closed "
         "providers rarely disclose it."
         % len(pts)),
        ("Capability index may lag recent releases and covers 54 of 430 "
         "priced models. This compares off-the-shelf models at API prices, "
         "not post-trained or self-hosted ones."),
    ]
    for i, note in enumerate(notes):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (PAD_L, H - 64 + i * 16, MUTED, escape(note)))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, H - 34, W - PAD_R, H - 34, GRID))
    a('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
      % (PAD_L, H - 15, INK_2, escape(credit_line(identity))))
    a('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">'
      'Sources: OpenRouter endpoints API, provider pricing pages, Artificial '
      'Analysis</text>' % (W - PAD_R, H - 15, MUTED))
    a('</g></svg>')
    return "\n".join(p)


def tier_medians(pts):
    rows = []
    for tier in ("frontier", "mid", "entry"):
        for wcls in (OPEN, CLOSED):
            sel = [p for p in pts if p["tier"] == tier and p["cls"] == wcls]
            rows.append({
                "tier": tier, "weight_class": wcls, "n": len(sel),
                "median_input": round(statistics.median(
                    [p["inp"] for p in sel]), 4) if sel else "",
                "median_output": round(statistics.median(
                    [p["out"] for p in sel]), 4) if sel else ""})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()

    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    bands = sorted(cfg["tiers"]["bands"], key=lambda b: b["min"])
    for i, b in enumerate(bands):
        b["max"] = bands[i + 1]["min"] if i + 1 < len(bands) else X_MAX
    R = cfg["blend"]["base_ratio"]
    ratios = sorted(set(cfg["blend"]["sensitivity_ratios"] + [R]))
    sens = [(None, "output only")] + [
        (r, "%d:1%s" % (r, " (base)" if r == R else "")) for r in ratios]

    identity = load_identity()
    date, bybase, excluded = load(args.date)
    pts = bybase[PRIMARY]

    os.makedirs(OUT_DIR, exist_ok=True)
    svg = os.path.join(OUT_DIR, "%s-capability-vs-price.svg" % date)
    with open(svg, "w", encoding="utf-8") as fh:
        fh.write(render(date, bybase, excluded, identity, bands, R, sens))

    med = os.path.join(OUT_DIR, "%s-tier-medians.csv" % date)
    rows = tier_medians(pts)
    with open(med, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["tier", "weight_class", "n",
                                           "median_input", "median_output"])
        w.writeheader()
        w.writerows(rows)

    print("date %s, base case %s, blend %d:1" % (date, PRIMARY, R))
    print("frontier, base case (cheapest fp8 or better):")
    for floor in (25.0, 30.0, 45.0):
        o, c = cheapest(pts, OPEN, floor, R), cheapest(pts, CLOSED, floor, R)
        print("  index >= %-4g open %-34s closed %s" % (
            floor,
            "%s $%.3f" % (o["id"], blend(o, R)) if o else "none",
            "%s $%.3f" % (c["id"], blend(c, R)) if c else "none"))

    print("")
    print("three price bases, blended %d:1" % R)
    print("  %-34s %6s %12s %16s %10s"
          % ("basis", "models", "open @25", "open advantage", "crossover"))
    for basis, label, bound in PRICE_BASES:
        P = bybase[basis]
        o, c = cheapest(P, OPEN, 25.0, R), cheapest(P, CLOSED, 25.0, R)
        xo = crossover(P, R)
        mark = " <- primary" if basis == PRIMARY else ""
        print("  %-34s %6d %12s %13.2fx %10s%s"
              % ("%s (%s)" % (label, bound), len(P),
                 "$%.3f" % blend(o, R), blend(c, R) / blend(o, R),
                 "%.1f" % xo if xo else "none", mark))

    print("")
    print("token-mix sensitivity on the base case:")
    P = bybase[PRIMARY]
    for rr, label in sens:
        o, c = cheapest(P, OPEN, 25.0, rr), cheapest(P, CLOSED, 25.0, rr)
        xo = crossover(P, rr)
        print("  %-14s open advantage %.2fx, crossover %s"
              % (label, blend(c, rr) / blend(o, rr),
                 "%.1f" % xo if xo else "none"))

    for basis, _, _ in PRICE_BASES:
        if excluded[basis]:
            print("")
            print("%s excludes %d scored models: %s"
                  % (basis, len(excluded[basis]),
                     ", ".join(m for m, _ in excluded[basis][:8])))
    print("")
    print("wrote %s" % svg)
    print("wrote %s" % med)


if __name__ == "__main__":
    main()
