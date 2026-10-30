"""Build three price bases per model, and the provider price spread.

Multi-provider competition on an open-weight model is a real, purchasable
advantage and is central to the thesis: anyone can serve the weights, so the
price falls towards the cost of compute. Pricing open models at their
author's list price throws that away. The problem with the cheapest endpoint
was never that it came from a reseller, it was that the cheapest endpoint is
often a 4-bit build competing against a closed model served at full
precision.

So three bases rather than one, and the gap between them is itself the
finding:

  cheapest_any    cheapest endpoint at any precision        lower bound
  cheapest_fp8    cheapest endpoint at 8-bit or better      base case
  author_list     the model author's own standard tier      upper bound

Precision rule. Endpoints declaring fp4, nvfp4, mxfp4 or int4 are below
8-bit and are excluded from the fp8 basis. Endpoints declaring fp8, fp16,
bf16 or fp32 qualify. Endpoints that declare nothing are treated as
qualifying, because closed providers almost never disclose quantization: of
94 closed endpoints seen on 2026-10-30, 92 declared nothing. Excluding
undeclared endpoints would empty the closed side entirely. The cost of that
choice is that an undeclared endpoint could be running a lower-precision
build, which would understate the fp8 basis.

Service tiers (flex, priority, ultrafast) are excluded from every basis:
they are speed or latency variants, not the standard product. Batch is a
separate model SKU and is excluded upstream.

Also writes the provider price spread for every open-weight model to
data/scorecard/open_source_share.csv, since the spread is a direct measure
of how much competition the open weights actually attract.

Usage:
    python scripts/price_bases.py
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

CLASSES = "data/model_classification.csv"
RAW = "data/raw/openrouter/%s.json"
CACHE = "data/raw/openrouter_endpoints"
DEST = "data/price_bases.csv"
PILLAR = "data/scorecard/open_source_share.csv"
API = "https://openrouter.ai/api/v1/models/%s/endpoints"
UA = "ai-infra-scorecard research collector"

SUB_8_BIT = {"fp4", "nvfp4", "mxfp4", "int4", "int3", "fp3", "mxfp6", "int2"}

FIELDS = ["date", "model_id", "org", "weight_class", "intelligence_index",
          "tier", "provider_count", "endpoint_count",
          "cheapest_any_input", "cheapest_any_output", "cheapest_any_provider",
          "cheapest_any_quantization",
          "cheapest_fp8_input", "cheapest_fp8_output", "cheapest_fp8_provider",
          "cheapest_fp8_quantization",
          "author_input", "author_output", "author_provider",
          "output_price_min", "output_price_max", "output_price_spread_ratio"]

PILLAR_FIELDS = ["date", "entity", "entity_class", "metric", "value", "unit",
                 "source", "source_url", "notes"]

PROVIDER_ALIASES = {
    "z-ai": "zai", "x-ai": "xai", "moonshotai": "moonshot",
    "bytedance-seed": "bytedance", "meta": "meta", "mistralai": "mistral",
    "qwen": "alibaba", "inclusionai": "alibaba",
    "thinkingmachines": "thinkingmachines", "aion-labs": "aionlabs",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch(slug):
    path = os.path.join(CACHE, "%s.json"
                        % hashlib.sha1(slug.encode("utf-8")).hexdigest()[:16])
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    req = urllib.request.Request(API % slug, headers={"User-Agent": UA})
    data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as fh:
                data = json.loads(fh.read().decode("utf-8"))
            break
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2 * (attempt + 1))
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    return data


def endpoints_of(data):
    """Standard-tier, non-zero-priced endpoints as tuples."""
    out = []
    for e in (data or {}).get("data", {}).get("endpoints", []):
        if e.get("service_tier") not in (None, "", "standard"):
            continue
        pr = e.get("pricing") or {}
        try:
            pi, po = float(pr.get("prompt")), float(pr.get("completion"))
        except (TypeError, ValueError):
            continue
        if pi < 0 or po <= 0:
            continue
        out.append({"provider": e.get("provider_name") or "",
                    "inp": pi * 1e6, "out": po * 1e6,
                    "quant": (e.get("quantization") or "unknown").lower()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()
    date = args.date

    with open(CLASSES, newline="", encoding="utf-8") as fh:
        cls = {r["model_id"]: r for r in csv.DictReader(fh)
               if r["date"] == date}

    with open(RAW % date, encoding="utf-8") as fh:
        payload = {m["id"]: m for m in json.load(fh)["data"]}

    # Everything scored (for the frontier) plus every open-weight model
    # (for the spread metric, which is what the pillar is about).
    targets = sorted(m for m, c in cls.items()
                     if ":" not in m
                     and (c["tier"] or c["weight_class"] == "open_weights"))
    print("fetching endpoints for %d models" % len(targets))

    rows, pillar_rows, failed = [], [], []
    for i, mid in enumerate(targets, 1):
        if i % 25 == 0:
            print("  %d/%d" % (i, len(targets)))
        data = fetch(mid)
        eps = endpoints_of(data)
        if not eps:
            failed.append(mid)
            continue
        c = cls[mid]
        org = mid.split("/")[0]
        want = PROVIDER_ALIASES.get(org, norm(org))

        cheap_any = min(eps, key=lambda e: e["out"])
        fp8 = [e for e in eps if e["quant"] not in SUB_8_BIT]
        cheap_fp8 = min(fp8, key=lambda e: e["out"]) if fp8 else None
        author = [e for e in eps if want and want in norm(e["provider"])]
        auth = min(author, key=lambda e: e["out"]) if author else None

        outs = [e["out"] for e in eps]
        providers = {e["provider"] for e in eps}
        row = {
            "date": date, "model_id": mid, "org": org,
            "weight_class": c["weight_class"],
            "intelligence_index": c["intelligence_index"], "tier": c["tier"],
            "provider_count": len(providers), "endpoint_count": len(eps),
            "cheapest_any_input": "%.6f" % cheap_any["inp"],
            "cheapest_any_output": "%.6f" % cheap_any["out"],
            "cheapest_any_provider": cheap_any["provider"],
            "cheapest_any_quantization": cheap_any["quant"],
            "cheapest_fp8_input": "%.6f" % cheap_fp8["inp"] if cheap_fp8 else "",
            "cheapest_fp8_output": "%.6f" % cheap_fp8["out"] if cheap_fp8 else "",
            "cheapest_fp8_provider": cheap_fp8["provider"] if cheap_fp8 else "",
            "cheapest_fp8_quantization": cheap_fp8["quant"] if cheap_fp8 else "",
            "author_input": "%.6f" % auth["inp"] if auth else "",
            "author_output": "%.6f" % auth["out"] if auth else "",
            "author_provider": auth["provider"] if auth else "",
            "output_price_min": "%.6f" % min(outs),
            "output_price_max": "%.6f" % max(outs),
            "output_price_spread_ratio": "%.3f" % (max(outs) / min(outs)),
        }
        rows.append(row)

        if c["weight_class"] == "open_weights":
            note = ("standard-tier endpoints only, any precision; "
                    "cheapest %s at %s, dearest %.3f"
                    % (cheap_any["provider"], row["cheapest_any_output"],
                       max(outs)))
            for metric, value, unit in (
                    ("provider_competition_count", len(providers), "count"),
                    ("provider_price_spread_ratio",
                     round(max(outs) / min(outs), 3), "ratio"),
                    ("provider_price_min", round(min(outs), 6), "usd_per_mtok"),
                    ("provider_price_max", round(max(outs), 6), "usd_per_mtok")):
                pillar_rows.append({
                    "date": date, "entity": mid,
                    "entity_class": "open_weights", "metric": metric,
                    "value": value, "unit": unit,
                    "source": "OpenRouter endpoints API",
                    "source_url": API % mid, "notes": note})

    for path, fields, data_rows in ((DEST, FIELDS, rows),
                                    (PILLAR, PILLAR_FIELDS, pillar_rows)):
        exists = os.path.exists(path)
        if exists:
            with open(path, newline="", encoding="utf-8") as fh:
                rdr = csv.DictReader(fh)
                seen = {r["date"] for r in rdr
                        if not fields == PILLAR_FIELDS
                        or r.get("metric", "").startswith("provider_")}
            if date in seen:
                sys.exit("%s already has rows for %s. Existing rows are never "
                         "modified." % (path, date))
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            if not exists or os.path.getsize(path) == 0:
                w.writeheader()
            w.writerows(data_rows)

    scored = [r for r in rows if r["tier"]]
    print("\n%d models priced, %d scored, %d with no usable endpoint"
          % (len(rows), len(scored), len(failed)))
    missing_fp8 = [r for r in scored if not r["cheapest_fp8_output"]]
    missing_auth = [r for r in scored if not r["author_output"]]
    print("scored models missing an fp8+ endpoint: %d %s"
          % (len(missing_fp8), [r["model_id"] for r in missing_fp8]))
    print("scored models missing an author endpoint: %d" % len(missing_auth))
    print("\nwrote %s (%d rows)" % (DEST, len(rows)))
    print("wrote %s (+%d rows)" % (PILLAR, len(pillar_rows)))

    op = [r for r in rows if r["weight_class"] == "open_weights"]
    cl = [r for r in rows if r["weight_class"] == "closed_weights"]
    for label, group in (("open", op), ("closed", cl)):
        if not group:
            continue
        sp = sorted(float(r["output_price_spread_ratio"]) for r in group)
        pc = sorted(int(r["provider_count"]) for r in group)
        print("%-7s median providers %2d, median spread %.2fx, max spread %.1fx"
              % (label, pc[len(pc) // 2], sp[len(sp) // 2], sp[-1]))


if __name__ == "__main__":
    main()
