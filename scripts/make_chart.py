"""Render the capability vs blended-price chart as a standalone SVG.

Every scored model as a point, capability on x and blended price on a log y
axis, coloured by weight class, tier bands shaded behind, and a step line per
class tracing the cheapest model that clears each capability floor.

Prices are the model author's own standard-tier list price, taken from
data/price_verification.csv, not OpenRouter's headline price. The headline is
the cheapest endpoint across every provider, which for an open-weight model
is usually a third-party reseller at reduced precision and for a closed model
is the author. Comparing those two is not like for like and the bias runs one
way: on 2026-10-30 the headline made the open advantage at the mid floor look
like 4.4x when the authors' own prices make it 1.5x.

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
VERIFIED = "data/price_verification.csv"
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
    "minimax/minimax-m3.1-flash": ("cheapest open above the mid floor", -1, -14),
    "anthropic/claude-haiku-5.5": ("cheaper than every open model\n"
                                   "that scores above it", 1, -14),
    "z-ai/glm-5.3": ("best open model", -1, -13),
    "openai/gpt-6.1-terra": ("cheapest above the frontier floor", 1, -13),
}


def blend(p, R):
    return p["out"] if R is None else (R * p["inp"] + p["out"]) / (R + 1)


def load(date=None):
    with open(CLASSES, newline="", encoding="utf-8") as fh:
        crows = list(csv.DictReader(fh))
    date = date or max(r["date"] for r in crows)
    cls = {r["model_id"]: r for r in crows if r["date"] == date}

    pts, excluded = [], []
    with open(VERIFIED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["date"] != date:
                continue
            c = cls.get(r["model_id"])
            if not c or not c["tier"]:
                continue
            if not r["first_party_output"]:
                excluded.append((r["model_id"], r["weight_class"], r["flag"]))
                continue
            pts.append({"id": r["model_id"],
                        "idx": float(c["intelligence_index"]),
                        "inp": float(r["first_party_input"]),
                        "out": float(r["first_party_output"]),
                        "cls": r["weight_class"], "tier": c["tier"],
                        "flag": r["flag"]})
    return date, pts, excluded


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


def render(date, pts, excluded, identity, bands, R, sens):
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
      'At list prices, the open discount is small and ends at the mid tier'
      '</text>' % (PAD_L, INK))
    a('<text x="%d" y="67" font-size="13.5" fill="%s">Blended price per '
      'million tokens at %d input tokens per output token, charged by each '
      'model&#8217;s own maker. Lines trace the</text>' % (PAD_L, INK_2, R))
    a('<text x="%d" y="86" font-size="13.5" fill="%s">cheapest model of each '
      'kind clearing a capability floor. OpenRouter endpoints and Artificial '
      'Analysis index, %s.</text>' % (PAD_L, INK_2, escape(date)))

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
      'Sensitivity to the token mix</text>' % (PAD_L, sy - 6, INK))
    scols = [PAD_L, PAD_L + 220, PAD_L + 470, PAD_L + 700]
    for cx_, head in zip(scols, ["Input : output ratio",
                                 "Open advantage at the mid floor",
                                 "Crossover index", "Open model above it"]):
        a('<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
          % (cx_, sy + 16, MUTED, head))
    a('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
      % (PAD_L, sy + 23, W - PAD_R, sy + 23, GRID))
    srow = sy + 43
    for rr, label in sens:
        o, c = cheapest(pts, OPEN, 25.0, rr), cheapest(pts, CLOSED, 25.0, rr)
        adv = blend(c, rr) / blend(o, rr) if o and c else 0
        xo_ = crossover(pts, rr)
        weight = "600" if rr == R else "400"
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">%s'
          '</text>' % (scols[0], srow, weight, INK_2, escape(label)))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">'
          '%.2fx cheaper</text>' % (scols[1], srow, weight, INK_2, adv))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">%s'
          '</text>' % (scols[2], srow, weight, INK_2,
                       "%.1f" % xo_ if xo_ else "none"))
        a('<text x="%d" y="%d" font-size="12" font-weight="%s" fill="%s">none'
          '</text>' % (scols[3], srow, weight, INK_2))
        srow += 20

    notes = [
        ("%d scored base SKUs priced at the author's own standard tier. %d "
         "excluded because their author does not serve them; all were open "
         "weights and all scored below 25."
         % (len(pts), len(excluded))),
        ("The crossover is set by open models running out of capability, not "
         "by the token mix, which is why it does not move with the ratio. "
         "Capability index may lag recent releases."),
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
        ("%d:1 blended%s" % (r, "  (base)" if r == R else ""), r)
        for r in ratios]
    sens = [(None, "output only")] + [(r, "%d:1%s" % (r, " (base)" if r == R
                                                      else "")) for r in ratios]

    identity = load_identity()
    date, pts, excluded = load(args.date)

    os.makedirs(OUT_DIR, exist_ok=True)
    svg = os.path.join(OUT_DIR, "%s-capability-vs-price.svg" % date)
    with open(svg, "w", encoding="utf-8") as fh:
        fh.write(render(date, pts, excluded, identity, bands, R, sens))

    med = os.path.join(OUT_DIR, "%s-tier-medians.csv" % date)
    rows = tier_medians(pts)
    with open(med, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["tier", "weight_class", "n",
                                           "median_input", "median_output"])
        w.writeheader()
        w.writerows(rows)

    print("date %s: %d models at author list prices, %d excluded"
          % (date, len(pts), len(excluded)))
    for mid, wc, flag in excluded:
        print("   excluded %-36s %-15s %s" % (mid, wc, flag))
    print("\nfrontier at author list prices, blended %d:1" % R)
    for floor in (25.0, 30.0, 45.0):
        o, c = cheapest(pts, OPEN, floor, R), cheapest(pts, CLOSED, floor, R)
        print("  index >= %-4g open %-32s closed %s" % (
            floor,
            "%s $%.3f" % (o["id"], blend(o, R)) if o else "none",
            "%s $%.3f" % (c["id"], blend(c, R)) if c else "none"))
    print("\nsensitivity")
    print("  %-16s %-26s %s" % ("ratio", "open advantage at index 25",
                                "crossover"))
    for rr, label in sens:
        o, c = cheapest(pts, OPEN, 25.0, rr), cheapest(pts, CLOSED, 25.0, rr)
        xo = crossover(pts, rr)
        print("  %-16s %-26s %s" % (
            label, "%.2fx cheaper" % (blend(c, rr) / blend(o, rr)),
            "%.1f" % xo if xo else "none"))
    print("\nwrote %s\n      %s" % (svg, med))


if __name__ == "__main__":
    main()
